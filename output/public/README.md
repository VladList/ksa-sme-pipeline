Masked deliverables of the pipeline (`scripts/08_export.py`).

- `ksa_sme_pipeline.xlsx` — README, Top-50, Reserve, Scored, Sources. Open it as a spreadsheet or upload it to Drive.
- `top50_masked.csv` — the Top-50 with the Arabic opener (AI-drafted, not native-reviewed).
- `scored_masked.csv` — every merchant after entity resolution: score, tier, exclusion reason, flags.

Phone numbers are masked (`+9665•••••123`) and owner names are not exported. `contact_note` says where the channel is,
because some leads carry a number only on their own website, which the pipeline does not store. The real numbers are
written on demand to `data/private/top50_contacts.csv` (`scripts/08_export.py --private`), which is never committed.
The pre-commit PII guard reads the workbook as well as the CSV files.
