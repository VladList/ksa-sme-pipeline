# Entity resolution and exclusions

- records in: 821
- merchants out: 765 (37 merchants built from 2+ records)
- identifiers ignored as hubs (shared by too many records): none

## Merchants by segment

| segment | merchants | excluded | eligible | eligible contactable |
|---|---|---|---|---|
| A_aesthetic_clinics | 322 | 72 | 250 | 203 |
| B_custom_furniture | 400 | 111 | 289 | 278 |
| C_salla_zid_d2c | 43 | 3 | 40 | 0 |

## Eligible merchants by segment and city

| segment | city | eligible |
|---|---|---|
| A_aesthetic_clinics | jeddah | 121 |
| A_aesthetic_clinics | jeddah|riyadh | 2 |
| A_aesthetic_clinics | riyadh | 127 |
| B_custom_furniture | jeddah | 105 |
| B_custom_furniture | riyadh | 184 |
| C_salla_zid_d2c | n/a | 40 |

## Exclusion reasons

| segment | reason | merchants |
|---|---|---|
| A_aesthetic_clinics | A: hospital or enterprise group | 6 |
| A_aesthetic_clinics | A: no segment signal in name or category | 70 |
| B_custom_furniture | B: multi-city company, not a local workshop | 4 |
| B_custom_furniture | B: no segment signal in name or category | 108 |
| C_salla_zid_d2c | C: outside KSA signal | 2 |
| C_salla_zid_d2c | C: wholesale | 1 |
