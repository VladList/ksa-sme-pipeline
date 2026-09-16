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
