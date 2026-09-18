Contact-level data, never committed and denied to agents in `.claude/settings.json`.
`top50_contacts.csv` (owner names, real mobiles, the Arabic opener) is written on demand by
`uv run python scripts/08_export.py --private`. Anything leaving this folder for `output/public/` goes through masking.
