# KSA SME Merchant Pipeline

Outbound lead generation for BNPL merchant acquisition in Saudi Arabia, built from zero in two days:
find SME merchants, validate every sourcing channel with numbers before scaling it, drop a segment when its own
kill criterion fires, score what survives, and hand over a call list instead of a research report.

**Deliverable:** [`output/public/`](output/public/) — Top-50 leads with a direct channel, the full scored list of 765
merchants, and the source log. Phone numbers are masked; real numbers are produced on demand and never committed.

Segments were hypotheses with measurements that could reject them (`config/icp.yaml`):
**A** independent aesthetic and dental clinics · **B** made-to-order majlis, sofa and curtain workshops ·
**C** Salla/Zid D2C brands in oud, perfume and abaya — **rejected on evidence**, see Findings.

## Result, in numbers

| | value |
|---|---|
| records collected (Google Maps Riyadh + Jeddah, Google dorks) | 821 (A 360, B 418, C 43) |
| unique merchants after entity resolution | 765; eligible after exclusions 579 (A 250, B 289, C 40) |
| merchants scored (eligible A and B, minus 20 already on Tabby) | 519 (A 233, B 286) |
| A-tier with a direct channel | 167 (A 75, B 92) |
| **Top-50** | A 34 / B 16, Riyadh 27 / Jeddah 23; stable under ±20% weight changes (minimum overlap 0.84) |
| decision-maker name verified (found verbatim in the source) | 48 of 519 candidates; 9 of the Top-50 |
| BNPL already present (homepages that loaded) | Tabby at 17 of 109 A clinics and 3 of 46 B workshops; all 20 detections QA-checked |
| sources validated / accepted / rejected | Google Maps accepted for A and B (B weaker in Jeddah); Salla/Zid worked as a source (contactability 1.00) but segment C was rejected by its kill criterion |
| total tool cost | **$4.88** — Apify $4.64 (free monthly credit) + OpenAI $0.24 · $0.0094 per scored merchant, $0.098 per Top-50 lead |
| elapsed | 2 days, one person |

## Findings

1. **Segment C is saturated, so it was dropped.** 14 of 20 sampled Salla/Zid stores already show a BNPL provider
   (Tabby 11), against a kill criterion of 0.60 fixed on day 1. Contactability was perfect (20/20), which would have
   looked like a green light if only one metric had been measured. `data/samples/bnpl_summary.md`
2. **Offline services are the white space.** Among clinics whose homepage loaded, Tabby is visible at 16% and any
   provider at 19%; the remaining 81% have no provider found. For workshops the web says almost nothing: 205 of 286
   have no website at all, so their BNPL status has to come from the call.
3. **Decision-maker names barely exist on SME sites.** 48 of 519 candidates (9%), and 42 of those come from the
   business name itself ("clinic of Dr X"). Promising a "decision-maker named" list before measuring would have been
   a promise the data cannot keep; the Top-50 definition was changed instead, with the number published.
4. **A quarter of merchant sites block scripts** (HTTP 403, mostly Cloudflare) and roughly 10% are broken for any
   visitor (dead domain, expired certificate, 404). Blocks were never bypassed: such merchants carry
   `bnpl_status = unchecked`, which costs them 7 points rather than being silently treated as clean.
5. **Prices are not on the page.** 12 of 519 homepages show any price, so ticket size is a segment assumption, not a
   measurement, and is documented as such rather than dressed up as a scored signal.

## Scoring

Weights, tier cuts and the sensitivity test were fixed in `config/scoring.yaml` **before the first calculation**.

| component | max | what it measures |
|---|---|---|
| Ticket fit | 30 | segment ticket range against the 12-month plan band (SAR 2,000–50,000) |
| BNPL status | 25 | not_detected 25 · unchecked 18 · competitor_only 15 · generic installments 12 · Tabby merchants excluded |
| Traction | 25 | review count by quartile **within the segment**, rating, number of locations |
| Reachability | 20 | mobile or WhatsApp with a verified name 20 · mobile or WhatsApp 15 · Instagram 10 · landline 5 |

Tiers are shares of the maximum (A ≥ 82.5%, B ≥ 65%). Top-50 = A-tier with a direct channel, ordered by score, then
review count. Every weight was rescaled ±20% and the unchecked-BNPL penalty tested at 15 and 21: the list keeps at
least 84% of its members in every variant (threshold 80%, set before the run). 38 leads score above the cutoff; the
last 12 places come from 26 merchants tied on score, and the 14 not selected are flagged as reserve rather than
dropped. Full breakdown: `data/samples/scoring_summary.md`.

## First steps with this list

- **31 leads can be called immediately** — their mobile is in Google Maps. 19 more have the number on their own
  website (`contact_note` says which is which); the pipeline stores the flag, not the number.
- **Openers are ready for 50 of 50 leads**, each built from a fact on the merchant's homepage (a named treatment, a
  free home measurement, same-day repair). They are AI-drafted Arabic and need a native speaker before sending.
- **14 reserve leads** are equivalent in score to the last ones selected: use them as the list continues.
- **53 workshops in A-tier have no checked website.** They are the natural second list: high mobile reachability,
  BNPL status unknown until the call, which is a discovery question rather than a blocker.
- **One decision is needed before calling 34 of the 50:** whether Risk accepts medical categories for BNPL and
  12-month plans. It is flagged per lead, never silently filtered.

## Pipeline

| stage | command | reads | writes | status |
|---|---|---|---|---|
| 1. Build search inputs | `scripts/01_build_apify_inputs.py` | `config/queries.yaml` | `data/apify_inputs/` | done |
| 2. Ingest raw exports | `scripts/02_ingest.py` | `data/raw/<source>/` | `data/interim/<source>/`, `data/runs.csv` | done |
| 3. Validate source × segment | `scripts/03_source_report.py` | interim + labelled sample | `data/samples/*__report.md` | done |
| 4. Entity resolution + exclusions | `scripts/04_resolve.py` | interim + `config/rules.yaml` | `data/interim/merchants.csv`, `resolve_summary.md`, `rules_check.md` | done (merge QA precision 0.97) |
| 5. BNPL fingerprint + LLM enrichment | `scripts/05_web_fingerprint.py --probe/--run/--manual-c/--qa-tabby`, `scripts/06_enrich.py` | `config/bnpl_markers.yaml`, `config/llm.yaml`, interim | `data/interim/bnpl.csv`, `enrich.csv`, `data/samples/bnpl_summary.md`, `bnpl_tabby_qa.md`, `enrich_summary.md` | done |
| 6. Scoring + tiers | `scripts/07_score.py` | `config/scoring.yaml`, interim | `data/interim/scored.csv`, `data/samples/scoring_summary.md` | done |
| 7. Export | `scripts/08_export.py` | `data/interim/scored.csv` | `output/public/*.csv`, `ksa_sme_pipeline.xlsx` | done; masked, private file on demand |

## How to read this repository

- `config/icp.yaml` — segment hypotheses, each with the measurement that would reject it, and what happened to it.
- `data/sources.yaml` — every source considered, including rejected ones, with the validation protocol (thresholds fixed before data).
- `data/samples/` — hand-labelled 20-record samples per source × segment, the metric report for each, and every QA file.
- `config/schema.yaml` — the data contract: columns, PII flag per column, `_inferred` suffix for LLM output.
- `config/llm.yaml`, `config/scoring.yaml` — model, prices and prompt; weights, tiers and the sensitivity test. Both fixed before use.
- `data/runs.csv` — every run: tool, input, record count, cost. `data/changelog.csv` — every manual change to a record, with its reason and evidence.
- `notebooks/observations.md` — 59 findings in the order they were found, with numbers.
- `output/methodology.md` — the definitions the project holds itself to, including the amendments made along the way and why.

## Method notes

- **Thresholds before data.** Every acceptance rule, kill criterion and weight is written down with a date before the
  measurement that uses it. Metrics discovered later are recorded but not used to justify a decision already made.
- **Nothing is deleted.** Rejected sources, dropped segments and excluded merchants keep their row with a reason.
- **`unclear` counts against the source**, and an empty field means "not checked", never "absent".
- **Blocks are not bypassed.** No User-Agent spoofing, no challenge solving; a blocked page becomes a documented gap.
- **Verification beats fluency.** LLM output is only used when it can be checked: an owner name must appear verbatim
  in the source, an Arabic opener must rest on page text. All 20 Tabby detections were reviewed by eye and then in the
  page source, and the disagreements are in `data/changelog.csv`.
- **Personal data is handled, not avoided.** Phones and owner names live in `data/interim/` and `data/private/`, are
  masked in everything committed, and a pre-commit hook scans CSV, Markdown, YAML and XLSX for unmasked numbers.

## Limitations

- BNPL status is known for 135 of 519 candidates: homepage only, and no status at all for merchants without a website.
- Ticket size is not measured (prices on 12 homepages); Ticket fit uses the segment range and therefore barely separates leads.
- Validation samples are 20 records per source × segment: the confidence intervals are wide (segment C: 0.48–0.86).
- Segment B was validated weakly in Jeddah (relevance 0.40) and is under-represented in the Top-50 because most of its merchants have no website.
- Decision-maker names mostly come from business names and are not confirmed owners; confirming a role needs a call.
- Arabic openers are AI-drafted and were not reviewed by a native speaker.
- Two clinics were kept as Tabby merchants on weak evidence (a shared booking form), which costs two leads rather than risking a pitch to an existing merchant.

## Quick start

```bash
uv sync
uv run pytest -q                                          # 65 tests
uv run python scripts/01_build_apify_inputs.py google_maps --mode full   # refuses to write inputs over budget
# run each input in Apify, export JSON (All fields) to data/raw/google_maps/<date>__<label>.json
uv run python scripts/02_ingest.py google_maps data/raw/google_maps/<file>.json
uv run python scripts/03_source_report.py sample google_maps A_aesthetic_clinics --runs "2026-09-17__full_*"
# label icp_label in the sample CSV, then:
uv run python scripts/03_source_report.py report google_maps A_aesthetic_clinics --runs "2026-09-17__full_*"
uv run python scripts/04_resolve.py                       # records -> merchants, exclusions, rules checked against labels
uv run python scripts/05_web_fingerprint.py --run         # homepages: BNPL providers + contact flags
uv run python scripts/05_web_fingerprint.py --qa-tabby    # every Tabby detection checked by hand
uv run python scripts/06_enrich.py --dry-run              # free; --trial then --run call the OpenAI API (config/llm.yaml)
uv run python scripts/07_score.py                         # scores, tiers, Top-50, sensitivity
uv run python scripts/08_export.py                        # masked export (--private adds real numbers, never committed)
```

Stages 1–3 need an Apify account and raw exports; stage 5 enrichment needs `OPENAI_API_KEY` in `.env` (about $0.24 for
519 merchants). Everything else runs offline from the local caches.

## What changed from the previous pipeline

Second run of a method first used for an ICP project in AI video (`VladList/icp-pipeline`, 5 days):

- **The primary key is not the domain.** Most target SMEs have no website; identity is any of phone, domain, Instagram handle, store key or Maps place id.
- **Sources are validated per segment**, not globally: hit rate turned out to be source- and city-dependent (B: 0.90 in Riyadh, 0.40 in Jeddah).
- **No scaffolding ahead of use.** The previous brief listed tooling that was never built; this repository contains only code that has been run.
- **Two days instead of five.**

## Author

Vladislav Listopadov — [LinkedIn](https://www.linkedin.com/in/vladleemm/) · [GitHub](https://github.com/VladList)

CV line:

> **KSA SME outbound data pipeline** — 821 records → 765 merchants (entity resolution) → Top-50 scored leads in 2 days
> for $4.88. Three ICP hypotheses tested against pre-registered kill criteria; one segment rejected on evidence (BNPL
> already present at 14 of 20 sampled stores). BNPL competitor detection on merchant sites, LLM enrichment with
> verbatim verification, scoring stable under ±20% weight changes. `github.com/VladList/ksa-sme-pipeline`

## Data and privacy

Only public business listings and public business profiles are collected; reviewer personal data is never requested
from scrapers. Contact-level data never leaves `data/private/` unmasked, and bot protections are respected rather
than bypassed. This is an interview artifact, not a production system and not a legal review of Saudi PDPL compliance.
