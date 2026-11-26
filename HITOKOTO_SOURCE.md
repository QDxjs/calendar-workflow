# Hitokoto corpus provenance

- Upstream: [hitokoto-osc/sentences-bundle](https://github.com/hitokoto-osc/sentences-bundle)
- Pinned commit: `1ecfe5ac1550ac928396c80153efa3d342198b02`
- Files: `sentences/b.json`, `sentences/d.json`, `sentences/h.json`, `sentences/k.json`
- Categories: manga, literature, film/TV, philosophy
- Upstream rows: 111, 2,015, 198, and 307 respectively (2,631 total); 2,399 records currently meet the application's length/source rules and remain after generic-source suppression and normalized-text deduplication
- License stated by upstream: AGPL-3.0; the exact license text is included with the bundled data
- Upstream cautions that the sentences' copyrights are not wholly held by Hitokoto

The application reads the four JSON files locally and does not make runtime network requests. Records retain their `type`, `from`, `from_who`, and `uuid` metadata in the local corpus. Calendar pages and the `source` manifest field do not show `type`; they show non-generic `from` and available `from_who` values, separated by ` · `. Generic source labels such as `名人名言`, `网络`, `佚名`, and `某电视剧` are omitted; quotes left without any attribution are not used. The manifest preserves the upstream UUID in `quote_id`. Each UUID can be checked at `https://hitokoto.cn?uuid=<UUID>`.

Only records with an allowed category, a non-empty source, and a 4–58 character sentence are eligible for calendar selection. Duplicate detection ignores punctuation, whitespace, symbols and underscores; matching sentences are used only once. These category names do not guarantee that every sentence is an excerpt from a printed book. Review the upstream AGPL terms and individual quotation rights before public or commercial redistribution.
