# KSA SME Merchant Pipeline

> **Status: Day 2 of 3 — collection, source validation, entity resolution and BNPL fingerprint, LLM enrichment and scoring closed; segment C rejected; insights and outreach kit next.**
> Numbers below are filled only for closed stages (see `notebooks/state.md`). Nothing in this
> README describes work that has not been run.

An outbound pipeline for BNPL merchant acquisition in Saudi Arabia: find SME
merchants from zero, validate every sourcing channel with numbers before
scaling it, score leads for a 100%-outbound sales motion, and hand over a
call list, not a research report.

Target segments (hypotheses with kill criteria, `config/icp.yaml`):
**A** independent aesthetic/dental clinics · **B** made-to-order majlis &
curtain workshops · **C** Salla/Zid D2C brands in oud/perfume and abaya (rejected on Day 2: 14 of 20 sampled stores already show a BNPL provider).

## Result, in numbers

_Filled on Day 3 from `data/runs.csv`, `data/sources.yaml` and `output/public/`._

| | value |
|---|---|
| raw records collected (Google Maps, Riyadh + Jeddah) | 778 (A 360, B 418) |
| unique merchants after entity resolution | 765; eligible after exclusions 579 (A 250, B 289, C 40) |
| sources validated / accepted / rejected | Google Maps accepted for A and B (B with a Jeddah limitation); Salla/Zid worked (contactable 1.00) but segment C rejected by its kill criterion (BNPL on 14 of 20 sampled stores) |
| BNPL on merchant homepages (pages that loaded) | A: Tabby 17 of 109, competitor only 4; B: Tabby 3 of 46 (homepage only, lower bound; all 20 Tabby detections confirmed in QA) |
| A-tier leads (scored, direct channel; decision-maker name where verified) | 167 A-tier; Top-50: A 34 / B 16, all with a website and no BNPL provider found, decision-maker name 9; stable under ±20% weights (min overlap 0.84) |
| Top-50 leads in a medical category (Risk acceptance not yet confirmed) | 34 of 50 |
| decision-maker name verified (LLM, found verbatim in the source) | 48 of 519 candidates (A 43, B 5); direct channel for 461 |
| share of scored merchants with no BNPL provider | 124 of 135 with a loaded homepage (92%); 384 unchecked (no website or page blocked) |
| total tool cost, USD | 4.88: Apify 4.64 (free credit; probes 1.01, full run 3.63) + OpenAI 0.24 (enrichment of 519 merchants) |

## Pipeline

| stage | command | reads | writes | status |
|---|---|---|---|---|
| 1. Build search inputs | `scripts/01_build_apify_inputs.py` | `config/queries.yaml` | `data/apify_inputs/` | done |
| 2. Ingest raw exports | `scripts/02_ingest.py` | `data/raw/<source>/` | `data/interim/<source>/`, `data/runs.csv` | done |
| 3. Validate source × segment | `scripts/03_source_report.py` | interim + labelled sample | `data/samples/*__report.md` | done for Google Maps |
| 4. Entity resolution + exclusions | `scripts/04_resolve.py` | interim + `config/rules.yaml` | `data/interim/merchants.csv`, `data/samples/resolve_summary.md`, `rules_check.md` | done (merge QA: `merge_qa.md`) |
| 5. BNPL fingerprint + LLM enrichment | `scripts/05_web_fingerprint.py --probe <urls>` / `--run` / `--manual-c` / `--qa-tabby` | `config/bnpl_markers.yaml`, `data/interim/merchants.csv` | `data/interim/bnpl.csv`, `data/samples/bnpl_summary.md`, `data/samples/C_contact_check.csv`, `data/samples/bnpl_tabby_qa.md` | fingerprint, QA and LLM enrichment done (`scripts/06_enrich.py`, `config/llm.yaml` → `data/interim/enrich.csv`, `data/samples/enrich_summary.md`) |
| 6. Scoring + tiers | `scripts/07_score.py` | `config/scoring.yaml`, interim merchants/bnpl/enrich | `data/interim/scored.csv`, `data/samples/scoring_summary.md` | done |
| 7. Export | `scripts/08_export.py` | `data/interim/scored.csv`, merchants, enrich | `output/public/ksa_sme_pipeline.xlsx`, `top50_masked.csv`, `scored_masked.csv` | done; numbers masked, private file on demand |
| 8. README and publication | — | all of the above | `README.md`, public repository | next: findings with numbers, a short week-1 note, limitations; dashboard, outreach kit and week-1 plan dropped by decision |

Stages without a command have no code yet, on purpose: files are created when
the stage runs, not in advance.

## How to read this repository

- `config/icp.yaml` — segment hypotheses, each with the measurement that would reject it.
- `data/sources.yaml` — every source considered, including rejected ones, and the validation protocol (thresholds fixed before data).
- `data/samples/` — 20-record samples per source × segment, hand-labelled, phones masked, plus the metric report for each.
- `config/schema.yaml` — the data contract: column order, PII flag per column, `_inferred` suffix for LLM output.
- `config/llm.yaml` — LLM enrichment: model, prices with the date checked, budget stop, prompt and the rules for using its answers.
- `config/scoring.yaml` — scoring weights, tier cuts, Top-50 rule and sensitivity test, fixed before the first calculation.
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
uv run python scripts/04_resolve.py          # records -> merchants, exclusions, rules checked against labels
uv run python scripts/05_web_fingerprint.py --probe https://fashion.sa   # BNPL markers on a known page
uv run python scripts/05_web_fingerprint.py --run        # homepages of eligible merchants: BNPL + contact flags
uv run python scripts/05_web_fingerprint.py --manual-c   # pages blocked for scripts in the C sample, checked by hand
uv run python scripts/05_web_fingerprint.py --qa-tabby   # every Tabby detection in A and B checked by eye
uv run python scripts/06_enrich.py --dry-run             # free: candidates and input size; --trial / --run call the OpenAI API
uv run python scripts/07_score.py                         # scores, tiers, Top-50 and sensitivity (config/scoring.yaml)
uv run python scripts/08_export.py                        # masked export to output/public/ (--private adds real numbers)
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
