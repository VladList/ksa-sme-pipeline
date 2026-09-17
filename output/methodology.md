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

### BNPL detection (added 2026-09-17, step 4.1)
- Markers are calibrated on known pages before the full run and not changed after it (`config/bnpl_markers.yaml`,
  dated evidence per verified marker kind).
- Marker kinds: provider domain in the page (`html`), provider name in a payment-logo file name (`icon`), provider name
  as a whole Arabic word (`text_ar`). Every detection records its kinds, so results can be reported by evidence kind.
- `bnpl_status` precedence: `tabby` > `competitor_only` > `generic_installment` (installment wording, no provider) >
  `not_detected`; `fetch_failed` when the page did not load. Only the homepage is checked, so `not_detected` does not
  mean the merchant has no BNPL.
- A marker found on >= 90% of fetched stores of one platform (Salla or Zid) is a platform template and is not counted
  for that platform.
- Bot challenges are not bypassed (no browser User-Agent spoofing); such pages are `fetch_failed`.
- Segment C contactability (phone, `wa.me` or `tel:` link, or Instagram visible on the store homepage) is measured on
  the 20-store validation sample: by script where the page loads, by hand in a browser where it does not, same
  definition. Threshold 0.50 unchanged. Amended before measuring, because Salla blocks scripted fetches.
- Network errors, rate limits and 5xx responses are not cached and are retried on the next run; 403 and 404 are cached.

### Page fetch, contacts and manual checks (added 2026-09-17, step 4.2)
- Target per eligible merchant: own website, else Salla/Zid store page; without either the merchant is `no_site` and its
  BNPL status stays empty (not checked). Own sites are tried as `https://domain`, then `https://www.domain` on a connection
  error. Plain http is not tried: on the 10 failures of the trial run no http variant served a page.
- A failed fetch is a row, grouped as blocked for scripts (401/403/429, never bypassed), page not found, site broken for
  any visitor (DNS, TLS, 5xx) or connection error.
- Contacts on the page are stored as yes/no flags only. A phone needs a national or international prefix. A phone,
  WhatsApp number or Instagram handle found on more than 2 fetched pages is a platform or agency contact and is ignored
  (`config/rules.yaml` web.contact_hub_max_pages, fixed before the run).
- Manual checks (`scripts/05_web_fingerprint.py --manual-c`) open each page the script could not load and record
  y / n / ? per question; `?` counts against the source; answers are saved per store and kept on re-runs. An icon the
  reviewer does not recognise is identified by the provider name in its image URL.
- Segment C kill criterion "stores already show a BNPL provider" is measured on the same 20-store sample and split as
  contactability: script where the page loads, by hand where it does not. Amended 2026-09-17 before the Salla BNPL check;
  the step 4.1 amendment had covered contactability only, which was an oversight.
- A rejected segment keeps its merchants; scoring excludes them with the segment's rejection reason.

### QA of Tabby detections (added 2026-09-17, step 4.2)
- Every `tabby` detection in scored segments is checked, not sampled: first by eye on the homepage
  (`scripts/05_web_fingerprint.py --qa-tabby`), then every eye-check `no` is read in the page source (LLM reading of the
  markup around the marker, recorded as such in `data/samples/bnpl_tabby_qa.csv`).
- Source-reading criteria, fixed before the snippets were read: a Tabby script or link, or rendered content (logo, banner,
  text, review, including lazy-loaded or collapsed elements) keeps the detection; a marker that is not a Tabby signal (for
  example a translation string inside a theme script) is a false positive; an ambiguous case keeps the detection, because
  pitching an existing merchant costs more than losing one lead.
- Why two steps: "is Tabby visible on the homepage" does not test what the script detects. This was noticed only after
  the eye-check answers and is recorded as a method change, not hidden.
- An eye-check `no` writes an override to `data/changelog.csv`; a detection kept by the source reading writes a reversing
  row. `data/interim/bnpl.csv` is never edited: the effective status is bnpl.csv plus the QA file.

### LLM enrichment (added 2026-09-17, step 4.3)
- Model, prices, budget stop and prompt live in `config/llm.yaml`; prices are copied from the provider's pricing page with
  the date checked. Spend is computed from token usage and recorded in `data/runs.csv`.
- Input per merchant: business name, Maps categories, city and the homepage text already fetched in step 4.2 (phone numbers
  masked before sending; nothing is fetched again). Output follows a strict JSON schema; every model field ends with
  `_inferred`. Answers are cached per merchant and prompt version; errors are not cached.
- A 20-merchant trial precedes the full run, stratified by input kind (with homepage text / name only) so that cost per
  merchant and quality are measured for both groups.
- Usage rules: an owner name counts only if it appears verbatim (Arabic-normalised) in the input; an Arabic opener is used
  only when it rests on homepage text; a ticket is used only when prices appear on the page, otherwise Ticket fit uses the
  segment range in `config/icp.yaml`. Owner names stay in `data/interim/`; committed files carry counts only.
- Arabic text written by the model is labelled AI-drafted and is not presented as native-speaker work.

### Gate G3 (added 2026-09-17)
- Question: how many candidates have a verified decision-maker name and a direct channel; is Top-50 realistic.
- Result: 47 with both, 461 with a direct channel. Decision: Top-50 = scored A-tier with a direct channel; the decision-maker
  name is a Reachability input and an output column, not a filter. Recorded in `config/icp.yaml`.
