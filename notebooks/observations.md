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
