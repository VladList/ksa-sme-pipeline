Per source × segment: `<source>__<segment>__sample.csv` (20 rows, phones masked, labelled by hand) and `<source>__<segment>__report.md` (metrics + recommendation).

Stage 5 (step 4.2): `bnpl_summary.md` (BNPL status, fetch failures, page-contact flags, segment C verdict; counts only) and `C_contact_check.csv` (20 C sample stores: contacts and BNPL, checked by script or by hand, yes/no only).

QA (step 4.2): `bnpl_tabby_qa.csv` / `bnpl_tabby_qa.md` (every Tabby detection in A and B: eye check, then page-source reading of each `no`; overrides and reversals in `data/changelog.csv`).

LLM enrichment (step 4.3): `enrich_trial_summary.md` and `enrich_summary.md` (counts only: cost, verified names, ticket basis, gate G3 by segment; names and openers stay in data/interim/).
