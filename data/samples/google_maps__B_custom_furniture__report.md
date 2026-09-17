# Source validation — google_maps × B_custom_furniture

Runs included (glob `2026-09-17__full_*`): `2026-09-17__full_B_custom_furniture__jeddah`, `2026-09-17__full_B_custom_furniture__riyadh`

Thresholds (set 2026-09-16, before data): icp_relevance ≥ 0.6, contactable ≥ 0.5

| metric | all | jeddah | riyadh |
|---|---|---|---|
| n_records | 418 | 208 | 210 |
| fill_phone_any | 0.904 | 0.841 | 0.967 |
| fill_phone_mobile | 0.88 | 0.808 | 0.952 |
| fill_own_site | 0.321 | 0.25 | 0.39 |
| fill_instagram | 0.045 | 0.058 | 0.033 |
| contactable_rate | 0.88 | 0.808 | 0.952 |
| closed_rate | 0.0 | 0.0 | 0.0 |
| chain_rate | 0.053 | 0.0 | 0.105 |
| sample_size | 20 | 10 | 10 |
| labeled | 20 | 10 | 10 |
| fit | 13 | 4 | 9 |
| not_fit | 3 | 2 | 1 |
| unclear | 4 | 4 | 0 |
| icp_relevance | 0.65 | 0.4 | 0.9 |

**Verdict:** recommend: accept

Fill rates over all ingested records of the included runs; icp_relevance over the hand-labelled sample, stratified equally per run.
