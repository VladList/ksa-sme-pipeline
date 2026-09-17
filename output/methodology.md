# Methodology

Definitions this project holds itself to. Written before collection (2026-09-16);
any later change is appended with a date, not edited in place.

## Units
- **record** — one row from one source run (`record_id = source_id:native_id`).
- **merchant** — one business after entity resolution (Day 2). A merchant can have
  records from Maps, Instagram and a store; they are linked when they share any
  identifier: `phone_e164`, `website_domain`, `instagram_handle`, `store_key`, `google_place_id`.

## Source validation protocol
- Unit of validation: **source × segment**.
- Sample: 20 records, random seed 42, drawn from all ingested records of that pair.
- Label per sample row: `fit` | `not_fit` | `unclear`, with a short note.
- `icp_relevance = fit / labeled`. `unclear` counts against the source.
- `contactable_rate` = share of records with a mobile number, an Instagram handle, or a WhatsApp link.
- Accept if `icp_relevance ≥ 0.60` and `contactable_rate ≥ 0.50`. Thresholds were set
  before any data and are not tuned to make a source pass.
- The script recommends; the status change in `data/sources.yaml` is a manual, dated decision.

## Phone types
`mobile` (+9665…) is treated as the strongest owner-reachability signal for SMEs.
`landline`, `unified` (92…), `tollfree` (800…) are business lines. Eastern Arabic
digits are normalised before parsing.

## Evidence and inference
- Every record carries `evidence_url`.
- Columns produced by an LLM end with `_inferred` and are never used as the only
  basis for an exclusion.
- A factor that is empty means "not checked", not "checked and absent", unless the
  column says otherwise (e.g. `bnpl_status=unknown`).

## Personal data
Phone numbers, owner names and bio text are flagged `pii: true` in `config/schema.yaml`.
They stay in `data/interim/` and `data/private/` (not committed) and are masked in
`data/samples/` and `output/public/`.

---

## Additions and amendments — 2026-09-17

Appended after the probe and full runs. The sections above are kept as written on 2026-09-16.

### Search location
Text location ("Riyadh, Saudi Arabia") was dropped: it resolved to Riyadh Province and filled sparse categories
with towns hundreds of km away. Every run uses a circle instead: GeoJSON `Point`, coordinates in
`[longitude, latitude]` order, radius 25 km around the city centre (`config/queries.yaml`).

### Keyword selection (probe runs)
- Each candidate keyword is probed on its top 10 Google Maps results; every place is labelled.
- Rule, fixed before the probe: drop keywords with `fit < 5`; keep the 3 with the highest `fit`;
  ties go to the keyword that adds diversity (language or sub-category), then to lower overlap.
- **Overlap** = `skipped_by_dedupe` = last rank − places returned. The actor skips places already found by another
  keyword in the same run, so overlap means the keyword reaches deeper, lower-ranked results; it does not mean
  paying twice. Which keyword "owns" a shared place depends on processing order, so overlap is indicative only.
- `fit_unique_brands` (branches of one brand counted once) was added after the rule was fixed; it is recorded
  and was not used for the decision.
- A keyword measured with the leaking text location is marked `superseded` and re-measured, not re-labelled.

### Labelling rules
- **fit**: a segment signal in the name or the Maps category. A: dental / orthodontic / cosmetic dentistry,
  dermatology, laser, aesthetics. B: made-to-order work (تفصيل, تنجيد, ستائر; categories Curtain supplier and maker,
  Curtain store, Blinds shop, Upholstery shop, Furniture maker).
- **not_fit**: hospitals and government facilities, multi-specialty complexes without a specialty signal, unrelated
  businesses, ready-made or used furniture, rentals, fabric wholesale, enterprise groups (Dr. Sulaiman Al Habib,
  Al Farabi, Al-Muhaidib — from general knowledge, to be verified).
- **unclear**: doctor listings not checked by hand, name/category conflict, empty listing. Counts against the source.
- **Doctor listings** (manual Google Maps check): a "Located in" line or another clinic's name in the address →
  `not_fit` (the merchant is the host clinic); a separate street address → `fit`. A separate address is not a
  verified owner.
- Labels are LLM judgements from name, category and website field unless `labeled_by = manual_maps_check`.

### Validation protocol — amendments
- Runs are selected by a glob on `run_id` (`--runs "2026-09-17__full_*"`); probe runs are excluded.
- The 20-record sample is **stratified equally per run** (10 per city), replacing "drawn from all ingested records".
  Reason: an unstratified sample can miss a city entirely.
- Every metric is also reported per run. Thresholds are unchanged and apply to source × segment; per-city results
  are reported as limitations, not used to change a verdict after the fact.

### Paid add-ons
The company contacts add-on is enabled per segment by experiment (A: on; B: off). Social profile enrichment,
business leads enrichment, place details, reviews, images and filters stay off.

### Planned for Day 2
- B exclusion rule: keep only records with a made-to-order signal in name or category. Fitted on the same
  validation sample, so its accuracy must be re-checked on other records before it is reported.
- Tabby and Tamara presence: per-lead lookup of their merchant pages plus website BNPL fingerprint.

### Entity resolution and exclusions (added 2026-09-17, stage 4)
- A merchant is one sales conversation. Records are linked (union-find) when they share a Google place id, phone,
  own website domain, Instagram handle or store key. Hosting and directory domains never link; an identifier shared by
  more than 12 records is treated as noise. `n_locations` = distinct Google places in the merchant.
- Exclusion rules live in `config/rules.yaml`; every excluded merchant keeps its row with all matching reasons.
- Each rule set is checked against existing labels (`data/samples/rules_check.md`) and marked in-sample when the rule
  was written after those labels were seen.
- Rules v2 after merge QA (2026-09-17): classifieds domains never link; B excludes merchants present in both cities
  (derived from the segment definition, not from a brand list); curated `same_as` links are allowed only with evidence
  noted next to them in `config/rules.yaml`.
