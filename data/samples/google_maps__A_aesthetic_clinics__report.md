# Source validation — google_maps × A_aesthetic_clinics

Runs included (glob `2026-09-17__full_*`): `2026-09-17__full_A_aesthetic_clinics__jeddah`, `2026-09-17__full_A_aesthetic_clinics__riyadh`

Thresholds (set 2026-09-16, before data): icp_relevance ≥ 0.6, contactable ≥ 0.5

| metric | all | jeddah | riyadh |
|---|---|---|---|
| n_records | 360 | 180 | 180 |
| fill_phone_any | 0.7 | 0.694 | 0.706 |
| fill_phone_mobile | 0.503 | 0.561 | 0.444 |
| fill_own_site | 0.686 | 0.656 | 0.717 |
| fill_instagram | 0.528 | 0.556 | 0.5 |
| contactable_rate | 0.789 | 0.856 | 0.722 |
| closed_rate | 0.0 | 0.0 | 0.0 |
| chain_rate | 0.0 | 0.0 | 0.0 |
| sample_size | 20 | 10 | 10 |
| labeled | 20 | 10 | 10 |
| fit | 16 | 7 | 9 |
| not_fit | 2 | 1 | 1 |
| unclear | 2 | 2 | 0 |
| icp_relevance | 0.8 | 0.7 | 0.9 |

**Verdict:** recommend: accept

Fill rates over all ingested records of the included runs; icp_relevance over the hand-labelled sample, stratified equally per run.
