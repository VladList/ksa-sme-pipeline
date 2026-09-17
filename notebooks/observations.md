# Observations

Findings in the order they were found, each with the numbers behind it and the file it was read from.
Hypotheses live in `config/icp.yaml`; this file records what the data said about them.
Labels are LLM judgements from name, Maps category and website field unless marked `manual_maps_check`.

## 2026-09-16 — keyword probe, 14 keywords x top 10, "Riyadh, Saudi Arabia"

Source: `data/samples/google_maps__keyword_probe__labeling.csv`, `data/keyword_check.csv`.

1. **Location text is a province, not a city.** Segment A: 44 of 80 places in Riyadh city, the rest in towns
   hundreds of km away (Wadi ad-Dawasir 11, Sajir 6, As Sulayyil 4, ...). Segment B: 57 of 60 in Riyadh.
   Sparse categories get padded with far-away results; dense ones do not.
2. **The actor de-duplicates across keywords within one run.** 140 unique placeIds, but ranks run past 10
   (e.g. 2..24): a place already found by another keyword is skipped and the next one is taken. Overlap costs
   depth (lower-ranked results), not double payment.
3. **English "orthodontic clinic" returns doctor listings.** 6 of 10. Manual check of the address and
   "Located in" line: 4 separate practice addresses, 2 inside another clinic (`data/samples/doctor_listing_check.csv`).
4. **Segment B listings often carry the keyword as their name** ("تفصيل كنب" three times). Name-based chain
   detection will produce false positives for B; resolve by phone/domain instead.

## 2026-09-17 — segment A re-probe inside a 25 km circle around Riyadh

Source: `data/samples/google_maps__keyword_probe_A_circle__labeling.csv`.

5. **The circle fixed location:** 80 of 80 places in Riyadh.
6. **Keyword quality was confounded by location.** "عيادة تجميل أسنان" fit 1/10 in the province probe,
   8/10 inside the city; "مركز ليزر" 1/10 -> 9/10.
7. **Company contacts add-on pays off for clinics** (80 places): Instagram 4 -> 42, mobile unchanged (40),
   email 25; contactable (mobile or Instagram) 41 -> 58. Cost: +$2 per 1,000 places.
8. **Fit counts listings, not merchants:** 4 of 10 results for "عيادة جلدية وتجميل" were branches of one brand.
   Noted, not used in the decision (the rule was fixed before this metric was added).

## 2026-09-17 — full run, 4 x Google Maps (A 360, B 418 places), $3.63

Source: `data/runs.csv`, `data/samples/google_maps__*__report.md`.

9. **Opposite contact profiles.** A: own website 69%, mobile 50%, Instagram 53%. B: mobile 88%, own website 32%,
   Instagram 5%. A is an Instagram-and-website outreach; B is a phone and field-visit outreach.
10. **Google Maps accepted for both segments** (thresholds fixed 2026-09-16): A relevance 0.80, contactable 0.79;
    B relevance 0.65, contactable 0.88.
11. **B degrades in Jeddah:** relevance 0.40 vs 0.90 in Riyadh (10 records each, wide uncertainty). Keywords chosen
    on Riyadh data return furniture showrooms in Jeddah. Share of B records with a custom-work signal in name or
    category: Jeddah 110/208, Riyadh 194/210. Consequence of skipping a Jeddah probe; caught by stratifying the
    validation sample by city.
12. **The contacts add-on is charged only for places with a website.** A Riyadh cost $0.99 and A Jeddah $0.97
    against an upper bound of $1.08 each; B runs matched the base price exactly ($0.84, $0.83).
13. **Two metrics are not trustworthy as-is:** `closed_rate` is 0.0 in all runs (the actor appears not to return
    closed places for these searches; treat as not measured), and name-based `chain_rate` in B (0.053) is inflated
    by identical SEO names (one name shared by 16 different workshops).

## 2026-09-17 — Tabby / Tamara merchant directories

14. **No free bulk list for either provider.** Both publish browsable store directories with per-merchant pages;
    full lists are sold by StoreLeads, which reports 2,377 KSA e-commerce stores with Tabby and 4,940 with Tamara
    (third-party tracker, e-commerce only, not market share). Decision: per-lead lookup for the shortlist.

## 2026-09-17 — segment C, Salla/Zid via search operators

Source: `data/raw/salla_zid_dork/2026-09-17__dork.csv` (not committed), `data/samples/salla_zid_dork__C_salla_zid_d2c__sample.csv`.

15. **Volume is not the constraint:** 5 queries, 45 result links, 43 unique stores (Salla 27, Zid 16). The store URL
    pattern holds for both platforms; many Zid stores use random subdomains, so the result title is the only brand name.
16. **Relevance 0.65 on 20 stores**, labelled from titles only: 13 fit, 2 not_fit (wholesale / reseller of global
    brands), 5 unclear (title without a niche). Store pages on Day 2 will turn most `unclear` into fit or not_fit.
17. **Salla is not KSA-only:** 2 of 43 stores signal Bahrain or the Emirates in the name. Country must be checked.
18. **Contactability cannot be measured from search results.** The validation script prints contactable 0.0 and
    recommends reject; that is missing data, not a measured absence. Provisional accept, conditional on Day 2.
