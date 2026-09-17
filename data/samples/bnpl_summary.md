# BNPL fingerprint and page contacts (stage 5, step 4.2)

Run 2026-09-17. Homepage only: `not_detected` does not mean no BNPL. Markers: `config/bnpl_markers.yaml`. Eligible merchants only (`data/interim/merchants.csv`, exclusion_reason empty).

## Targets

| segment | eligible | own_site | salla | zid | no_site | page loaded | fetch_failed |
|---|---|---|---|---|---|---|---|
| A_aesthetic_clinics | 250 | 162 | 2 | 0 | 86 | 109 | 55 |
| B_custom_furniture | 289 | 83 | 1 | 0 | 205 | 46 | 38 |
| C_salla_zid_d2c | 40 | 0 | 24 | 16 | 0 | 16 | 24 |

## BNPL status (merchants with a site or store)

| segment | tabby | competitor_only | generic_installment | not_detected | fetch_failed |
|---|---|---|---|---|---|
| A_aesthetic_clinics | 17 | 4 | 7 | 81 | 55 |
| B_custom_furniture | 3 | 0 | 0 | 43 | 38 |
| C_salla_zid_d2c | 2 | 2 | 0 | 12 | 24 |

## Evidence kind behind provider detections

A merchant counts once per provider and kind (it can have several kinds). `icon` is not verified.

| segment | provider | kind | merchants |
|---|---|---|---|
| A_aesthetic_clinics | tabby | html | 1 |
| A_aesthetic_clinics | tabby | icon | 6 |
| A_aesthetic_clinics | tabby | text_ar | 10 |
| A_aesthetic_clinics | tamara | html | 5 |
| A_aesthetic_clinics | tamara | icon | 4 |
| A_aesthetic_clinics | tamara | text_ar | 10 |
| B_custom_furniture | tabby | icon | 2 |
| B_custom_furniture | tabby | text_ar | 2 |
| B_custom_furniture | tamara | icon | 1 |
| B_custom_furniture | tamara | text_ar | 1 |
| C_salla_zid_d2c | mispay | html | 1 |
| C_salla_zid_d2c | mispay | icon | 1 |
| C_salla_zid_d2c | tabby | icon | 2 |
| C_salla_zid_d2c | tamara | icon | 3 |

`tabby` detected by icon only (unverified kind): {'A_aesthetic_clinics': 6, 'B_custom_furniture': 1, 'C_salla_zid_d2c': 2}

## Platform templates

Evidence on at least half of one platform's loaded pages; `dropped` = html/icon on >= 90% (rule fixed before this run).

none

## Fetch failures

Blocked pages are not bypassed (methodology). Broken sites fail for any visitor, not only for the script.

| segment | platform | reason | detail | merchants |
|---|---|---|---|---|
| A_aesthetic_clinics | own_site | blocked for scripts | HTTP 403 | 35 |
| A_aesthetic_clinics | own_site | connection error | ConnectTimeout | 2 |
| A_aesthetic_clinics | own_site | page not found | HTTP 404 | 4 |
| A_aesthetic_clinics | own_site | page not found | HTTP 410 | 1 |
| A_aesthetic_clinics | own_site | site broken: TLS certificate | ConnectError:tls | 5 |
| A_aesthetic_clinics | own_site | site broken: domain does not resolve | ConnectError:dns | 4 |
| A_aesthetic_clinics | own_site | site broken: server or TLS error | HTTP 521 | 1 |
| A_aesthetic_clinics | own_site | site broken: server or TLS error | HTTP 525 | 1 |
| A_aesthetic_clinics | salla | blocked for scripts | HTTP 403 | 2 |
| B_custom_furniture | own_site | blocked for scripts | HTTP 403 | 22 |
| B_custom_furniture | own_site | connection error | ConnectError | 1 |
| B_custom_furniture | own_site | connection error | ConnectTimeout | 2 |
| B_custom_furniture | own_site | page not found | HTTP 404 | 2 |
| B_custom_furniture | own_site | site broken: TLS certificate | ConnectError:tls | 5 |
| B_custom_furniture | own_site | site broken: domain does not resolve | ConnectError:dns | 4 |
| B_custom_furniture | own_site | site broken: server or TLS error | HTTP 500 | 1 |
| B_custom_furniture | salla | blocked for scripts | HTTP 403 | 1 |
| C_salla_zid_d2c | salla | blocked for scripts | HTTP 403 | 24 |

## Page contacts (merchants whose page loaded)

Contact values on more than 2 pages are ignored (platform or agency). Flags only, no values stored.

| segment | loaded | phone | mobile | whatsapp | instagram | SAR price | foreign currency |
|---|---|---|---|---|---|---|---|
| A_aesthetic_clinics | 109 | 75 | 46 | 69 | 89 | 4 | 2 |
| B_custom_furniture | 46 | 35 | 35 | 27 | 22 | 0 | 0 |
| C_salla_zid_d2c | 16 | 15 | 15 | 4 | 11 | 12 | 0 |

## Segment C contactability — validation sample (`data/samples/C_contact_check.csv`)

Definition (methodology 2026-09-17): phone, WhatsApp or tel link, or Instagram visible on the store homepage. Threshold 0.50, fixed before data. The script reads links, text and embedded JSON of the homepage; a contact that appears only after JavaScript runs can be missed, which biases the script rows towards `no`.

| checked_by | stores | contactable |
|---|---|---|
| manual_browser | 12 | 12 |
| script | 8 | 8 |

**contactable_rate 1.00** (20/20) -> recommend: accept (threshold 0.50).

### Segment C kill criterion: stores already showing a BNPL provider

`config/icp.yaml`: reject C if > 0.60 of stores already show a BNPL provider. Measured on the same 20-store sample (Salla blocks scripts): script where the page loads, by hand where it does not. Homepage only; `unclear` counts against the source.

| bnpl_status | stores |
|---|---|
| competitor_only | 3 |
| not_detected | 6 |
| tabby | 11 |

**share with a provider (unclear counted as yes) 0.70** -> kill criterion hit: reject C (threshold 0.60).
