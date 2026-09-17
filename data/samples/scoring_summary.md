# Lead scoring (phase 5)

Run 2026-09-17, `config/scoring.yaml` v1 (fixed before the first calculation). Tiers: A >= 82.5, B >= 65.0 of 100. Counts only; the lead list is in data/interim/scored.csv.

## Scored and excluded

| segment | merchants | scored | excluded |
|---|---|---|---|
| A_aesthetic_clinics | 322 | 233 | 89 |
| B_custom_furniture | 400 | 286 | 114 |
| C_salla_zid_d2c | 43 | 0 | 43 |

Exclusion reasons (grouped):

| segment | reason | merchants |
|---|---|---|
| A_aesthetic_clinics | A | 72 |
| A_aesthetic_clinics | already Tabby merchant | 17 |
| B_custom_furniture | B | 111 |
| B_custom_furniture | already Tabby merchant | 3 |
| C_salla_zid_d2c | C | 3 |
| C_salla_zid_d2c | segment rejected | 40 |

## Tiers

| segment | A | B | C | A with a direct channel | median score |
|---|---|---|---|---|---|
| A_aesthetic_clinics | 75 | 144 | 14 | 75 | 81 |
| B_custom_furniture | 92 | 187 | 7 | 92 | 82 |

## Components (scored merchants)

| segment | bnpl_status_final | merchants |
|---|---|---|
| A_aesthetic_clinics | competitor_only | 4 |
| A_aesthetic_clinics | generic_installment | 7 |
| A_aesthetic_clinics | not_detected | 81 |
| A_aesthetic_clinics | unchecked | 141 |
| B_custom_furniture | not_detected | 43 |
| B_custom_furniture | unchecked | 243 |

| segment | channel | merchants |
|---|---|---|
| A_aesthetic_clinics | instagram | 23 |
| A_aesthetic_clinics | mobile_or_whatsapp | 124 |
| A_aesthetic_clinics | mobile_or_whatsapp_and_name | 41 |
| A_aesthetic_clinics | none | 24 |
| A_aesthetic_clinics | other_phone | 21 |
| B_custom_furniture | mobile_or_whatsapp | 271 |
| B_custom_furniture | mobile_or_whatsapp_and_name | 5 |
| B_custom_furniture | none | 9 |
| B_custom_furniture | other_phone | 1 |

| segment | reviews_quartile | merchants |
|---|---|---|
| A_aesthetic_clinics | 1 | 58 |
| A_aesthetic_clinics | 2 | 58 |
| A_aesthetic_clinics | 3 | 58 |
| A_aesthetic_clinics | 4 | 59 |
| B_custom_furniture | 1 | 71 |
| B_custom_furniture | 2 | 69 |
| B_custom_furniture | 3 | 72 |
| B_custom_furniture | 4 | 74 |

## Top-50 (A-tier with a direct channel)

Members: 50

Score range 100 to 89. 38 leads score above the cutoff; the other 12 come from 26 merchants tied at 89, ordered by review count (order fixed in scoring.yaml). The remaining 14 are flagged as reserve. Best score with BNPL unchecked: 88.

| segment | leads |
|---|---|
| A_aesthetic_clinics | 34 |
| B_custom_furniture | 16 |

| cities | leads |
|---|---|
| jeddah | 23 |
| riyadh | 27 |

| bnpl_status_final | leads |
|---|---|
| not_detected | 50 |

| channel | leads |
|---|---|
| mobile_or_whatsapp | 41 |
| mobile_or_whatsapp_and_name | 9 |

| owner_name_verified | leads |
|---|---|
| False | 41 |
| True | 9 |

| hook_from_page | leads |
|---|---|
| True | 50 |

| reviews_quartile | leads |
|---|---|
| 2 | 5 |
| 3 | 11 |
| 4 | 34 |

| flag | leads |
|---|---|
| B Jeddah: source relevance 0.40 | 4 |
| medical: Risk review | 34 |

## Sensitivity

Each component's points x0.8 and x1.2 in turn (tier cuts follow the new maximum), and unchecked BNPL at 15 / 21. Stable if every variant keeps >= 80% of the Top-50 (fixed before the run).

| variant | top size | overlap with base |
|---|---|---|
| ticket_fit x0.8 | 50 | 1.00 |
| ticket_fit x1.2 | 50 | 1.00 |
| bnpl x0.8 | 50 | 0.96 |
| bnpl x1.2 | 50 | 1.00 |
| traction x0.8 | 50 | 0.84 |
| traction x1.2 | 50 | 0.96 |
| reachability x0.8 | 50 | 1.00 |
| reachability x1.2 | 50 | 0.98 |
| bnpl unchecked = 15 | 50 | 1.00 |
| bnpl unchecked = 21 | 50 | 0.96 |

**Top list stable** (minimum overlap 0.84).
