# Exclusion rules vs existing labels

Rules: `config/rules.yaml`. Labels: files in `data/samples/`; `unclear` rows are ignored.
`precision_of_kept` = fit / (fit + not_fit) among records the rules keep; `fit_retained` = share of fit records the rules keep.
**in-sample** = rule written after seeing these labels (optimistic).

| segment | label set | in-sample | kept fit | dropped fit | kept not_fit | dropped not_fit | precision of kept | fit retained |
|---|---|---|---|---|---|---|---|---|
| A_aesthetic_clinics | probe, Riyadh circle | yes | 64 | 1 | 4 | 3 | 0.94 | 0.98 |
| A_aesthetic_clinics | full-run validation sample | yes | 16 | 0 | 0 | 2 | 1.0 | 1.0 |
| B_custom_furniture | probe (labelled before the rule existed) | **no** | 45 | 0 | 1 | 4 | 0.98 | 1.0 |
| B_custom_furniture | full-run validation sample (rule fitted here) | yes | 13 | 0 | 0 | 3 | 1.0 | 1.0 |
| C_salla_zid_d2c | validation sample | yes | 13 | 0 | 1 | 1 | 0.93 | 1.0 |
