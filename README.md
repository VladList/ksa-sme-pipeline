# KSA SME Merchant Pipeline

> **Status: Day 2 of 3 — collection and source validation closed; enrichment and scoring next.**
> Numbers below are filled only for closed stages (see `notebooks/state.md`). Nothing in this
> README describes work that has not been run.

An outbound pipeline for BNPL merchant acquisition in Saudi Arabia: find SME
merchants from zero, validate every sourcing channel with numbers before
scaling it, score leads for a 100%-outbound sales motion, and hand over a
call list, not a research report.

Target segments (hypotheses with kill criteria, `config/icp.yaml`):
**A** independent aesthetic/dental clinics · **B** made-to-order majlis &
curtain workshops · **C** Salla/Zid D2C brands in oud/perfume and abaya.

## Result, in numbers

_Filled on Day 3 from `data/runs.csv`, `data/sources.yaml` and `output/public/`._

| | value |
|---|---|
| raw records collected (Google Maps, Riyadh + Jeddah) | 778 (A 360, B 418) |
| unique merchants after entity resolution | — |
| sources validated / accepted / rejected | Google Maps accepted for A and B (B with a Jeddah limitation); Salla/Zid pending |
| A-tier leads (scored, contactable, decision-maker named) | — |
| share of scored merchants with no BNPL provider | — |
| total tool cost, USD | 4.64 (Apify free credit; probes 1.01, full run 3.63) |

## Pipeline

| stage | command | reads | writes | status |
|---|---|---|---|---|
| 1. Build search inputs | `scripts/01_build_apify_inputs.py` | `config/queries.yaml` | `data/apify_inputs/` | done |
| 2. Ingest raw exports | `scripts/02_ingest.py` | `data/raw/<source>/` | `data/interim/<source>/`, `data/runs.csv` | done |
| 3. Validate source × segment | `scripts/03_source_report.py` | interim + labelled sample | `data/samples/*__report.md` | done for Google Maps |
| 4. Entity resolution + exclusions | — | | | Day 2 |
| 5. BNPL fingerprint + LLM enrichment | — | `config/bnpl_markers.yaml` | | Day 2 |
| 6. Scoring + tiers | — | `config/scoring.yaml` | | Day 2 |
| 7. Insights, outreach kit, public export | — | | `output/public/` | Day 3 |

Stages without a command have no code yet, on purpose: files are created when
the stage runs, not in advance.

## How to read this repository

- `config/icp.yaml` — segment hypotheses, each with the measurement that would reject it.
- `data/sources.yaml` — every source considered, including rejected ones, and the validation protocol (thresholds fixed before data).
- `data/samples/` — 20-record samples per source × segment, hand-labelled, phones masked, plus the metric report for each.
- `config/schema.yaml` — the data contract: column order, PII flag per column, `_inferred` suffix for LLM output.
- `data/runs.csv` — every scraping run: actor, input, record count, cost.
- `data/changelog.csv` — every manual change to a record, with a reason.
- `notebooks/observations.md` — findings as they were found, with the numbers.
- `notebooks/state.md` — project log (Russian, working language).
- `output/methodology.md` — definitions the project holds itself to.

## Quick start

```bash
uv sync
uv run pytest -q
uv run python scripts/01_build_apify_inputs.py google_maps --mode full   # refuses to write inputs over budget
# run each input in Apify, export JSON (All fields) to data/raw/google_maps/<date>__<label>.json
uv run python scripts/02_ingest.py google_maps data/raw/google_maps/2026-09-17__full_A_aesthetic_clinics__riyadh.json
uv run python scripts/03_source_report.py sample google_maps A_aesthetic_clinics --runs "2026-09-17__full_*"
# label icp_label in the sample CSV, then:
uv run python scripts/03_source_report.py report google_maps A_aesthetic_clinics --runs "2026-09-17__full_*"
```

## What changed from the previous pipeline

This is the second run of a method first used for an ICP project in AI video
(`VladList/icp-pipeline`, 5 days). Changes are deliberate:

- **Primary key is not the domain.** Most target SMEs have no website; identity is any of phone, domain, Instagram handle, store key, or Maps place id.
- **Sources are validated per segment**, not globally — the previous project found hit rate is source-dependent; here that is built into the protocol.
- **Personal data is handled, not avoided.** Outbound needs owner names and mobiles, so PII is flagged per column, kept in `data/private/`, masked in anything committed, and blocked by a pre-commit check.
- **No scaffolding ahead of use.** The previous brief listed tooling that was never used; this repository only contains code that has been run.
- **Time budget: 3 days instead of 5–7.**

## Data and privacy

Only public business listings and public business profiles are collected.
Reviewer personal data is never requested from scrapers. Contact-level data
never leaves `data/private/` unmasked. This is an interview artifact, not a
production system and not a legal review of Saudi PDPL compliance.
