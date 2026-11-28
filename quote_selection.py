"""Search the active corpus and recommend candidates without altering records."""

from __future__ import annotations

import random
import re
import unicodedata


def search_key(value: str) -> str:
    return re.sub(r"[\W_]+", "", unicodedata.normalize("NFKC", value).casefold())


class QuoteSearch:
    def __init__(self, quotes: list[dict[str, str]]) -> None:
        self.quotes = tuple(quotes)
        self._keys = tuple((search_key(item["quote"]), search_key(item["source"])) for item in quotes)

    def search(self, query: str) -> list[dict[str, str]]:
        if not query.strip():
            return list(self.quotes)
        terms = tuple(filter(None, (search_key(term) for term in query.split())))
        if not terms:
            return []
        phrase = search_key(query)
        matches = []
        for index, (body, source) in enumerate(self._keys):
            if not all(term in body or term in source for term in terms):
                continue
            rank = (0 if body == phrase or source == phrase else
                    1 if phrase in body else 2 if phrase in source else 3)
            matches.append((rank, index))
        return [self.quotes[index] for _rank, index in sorted(matches)]


class CandidateSampler:
    def __init__(self, seed: int | None = None) -> None:
        self.rng = random.Random(seed)
        self.seen: set[str] = set()
        self.restarted = False

    def recommend(self, quotes: list[dict[str, str]], count: int = 5) -> list[dict[str, str]]:
        if type(count) is not int or count < 1:
            raise ValueError("候选条数必须是正整数。")
        unique = {search_key(item["quote"]): item for item in reversed(quotes)}
        remaining = [item for key, item in unique.items() if key not in self.seen]
        self.restarted = not remaining and bool(unique)
        if self.restarted:
            self.seen.difference_update(unique)
            remaining = list(unique.values())
        selected = self.rng.sample(remaining, min(count, len(remaining)))
        self.seen.update(search_key(item["quote"]) for item in selected)
        return selected
