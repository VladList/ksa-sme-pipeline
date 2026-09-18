Local working tables, never committed: per-run ingest tables (`scripts/02_ingest.py`), `merchants.csv` (entity resolution),
`bnpl.csv` (web fingerprint), `enrich.csv` (LLM fields) and `scored.csv` (scoring). Columns: `config/schema.yaml`.
They hold phone numbers, bio text and owner names, and are rebuildable from `data/raw/` and the caches in one command each.
