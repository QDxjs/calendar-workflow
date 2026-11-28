"""Resolve random, single and multiple explicit calendar layouts."""

from collections.abc import Collection


def resolve_layouts(selection: str, choices: Collection[str]) -> tuple[str, ...]:
    requested = selection.strip().upper()
    if requested == "RANDOM":
        return ()
    letters = {part.strip() for part in requested.split("+")}
    if not letters or not letters.issubset(choices):
        raise ValueError("版式应为 A–I 或 RANDOM；多选版式用 + 分隔，例如 A+C+F。")
    return tuple(letter for letter in sorted(choices) if letter in letters)
