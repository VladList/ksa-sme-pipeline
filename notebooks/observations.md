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

## 2026-09-17 — entity resolution and exclusion rules

Source: `data/samples/resolve_summary.md`, `data/samples/rules_check.md`, rules in `config/rules.yaml`.

19. **821 records -> 765 merchants;** 39 merchants are built from 2+ records (branches or the same place found twice).
    No identifier was shared widely enough to be treated as noise. 5 merchants span both Riyadh and Jeddah: first to QA.
20. **Exclusions:** A 73 (71 without a specialty signal, 4 hospital or enterprise group), B 107 without a made-to-order
    signal, C 3 (2 outside KSA, 1 wholesale). No merchant crossed the chain threshold of 5 locations.
21. **The B rule held out of sample.** On 50 labelled records from the first probe (labelled before the rule existed) it
    kept all 45 fit and dropped 4 of 5 not_fit. Limitation: that probe was 95% Riyadh, so it does not test Jeddah,
    where the rule matters most. A and C rule checks are in-sample (0.93-1.0 precision) and optimistic.
22. **Gate G2 passed:** eligible A 250 (203 contactable), B 292 (279), C 40 (contactability pending). Raw volume is below
    the Day 1 targets because of the budget ceiling, but eligible merchants exceed the Top-50 need more than tenfold.

## 2026-09-17 — merge QA and rules v2

Source: `data/samples/merge_qa.md`, `data/samples/resolve_summary.md`.

23. **Merge precision 0.97** (36 of 37 verified merges correct; 2 unverified). The one false merge came from a classifieds
    site used as a "website"; classifieds domains are now ignored.
24. **Phone-based merges attach doctor listings to their host clinic** (2 cases): part of the manual "Located in" check
    from the probe now happens automatically.
25. **Segment B has SEO operators:** 4 merchants are one phone or site behind 2-3 generically named listings. After
    resolution they are one call, not three.
26. **Multi-city furniture companies contradict the workshop hypothesis** (Sedar, Alguthmi textile, Ayat curtains, Zerabi):
    rule v2 excludes B merchants present in both cities, B eligible 292 -> 289. Segment A keeps multi-city merchants by
    definition (up to 5 branches); the Meras group (6+ branches, confirmed on the web) is excluded.
    Final eligible: A 250 (203 contactable), B 289 (278), C 40 (contactability pending).

## 2026-09-17 — BNPL markers on live pages (step 4.1)

Source: `scripts/05_web_fingerprint.py --probe` on 6 URLs; markers in `config/bnpl_markers.yaml`.

27. **The known Tabby merchant is not found by the provider domain on its homepage.** fashion.sa shows Tabby as a word in
    its payment-methods list, next to Tamara; tabby.ai links appear only on its dedicated Tabby page. Domain-only
    detection would have missed it.
28. **Payment logos are a common signal and markers v1 missed them.** ramclinics.net (segment A) and a Zid store show Tabby
    and Tamara logos as image files; v1 returned `generic_installment` and `not_detected`. Added the `icon` marker kind,
    not verified: neither merchant's status is confirmed by Tabby. On Zid the logos sit in a footer payment block and may
    be a theme template, so a rule was fixed before step 4.2: a marker on >= 90% of one platform's stores is not counted.
29. **Arabic substring matching is unsafe:** the provider name "تابي" is contained in the common word "كتابي". Arabic
    markers now match whole words, allowing the prefixes و/ب/ل.
30. **Salla store pages answer a scripted client with a Cloudflare bot challenge** (HTTP 403, `cf-mitigated: challenge`);
    Zid stores and own websites load. The challenge is not bypassed. 12 of the 20 sampled C stores are on Salla, so C
    contactability is measured on the sample: Zid by script, Salla by hand in a browser, with the same definition.
31. **Clinics are live Tabby merchants** (Tabby merchant pages for Mac.clinics and Velvet Care Clinics, found by search):
    expect a visible share of segment A to be excluded as already on Tabby.
32. **Ram Clinics has branches in many cities outside Riyadh and Jeddah** (its branches page), while the chain threshold
    counts only locations inside our two search circles. Not a rule change: the size penalty in scoring handles it.

## 2026-09-17 — BNPL fingerprint, page contacts and the verdict on segment C (step 4.2)

Source: `data/samples/bnpl_summary.md`, `data/samples/C_contact_check.csv`, run `2026-09-17__web_fingerprint`.

33. **Web coverage is partial.** Eligible merchants with an own site or store: A 164 of 250, B 84 of 289. Homepage loaded:
    A 109, B 46. BNPL status is unknown for most of B (205 have no website): for B it has to come from the call.
34. **About a quarter of own sites block scripts** (HTTP 403, mostly Cloudflare; A 37 of 164 in the first full run) and
    they were not bypassed. A further group is broken for any visitor (DNS, expired TLS, 404, 5xx; A 16). A dead site
    is itself a signal: the working channel for that clinic is Maps or Instagram.
35. **At least 16% of A clinics with a loaded homepage already show Tabby** (17 of 109; 4 more show only a competitor,
    7 mention installments without a provider). A lower bound: homepage only. 6 of the 17 rest on the unverified icon
    kind alone and are checked by eye before scoring. B: 3 of 46.
36. **Payment logos are not a platform template on Zid:** no marker appeared on half or more of Zid store pages, so a
    logo reflects the store's own payment settings.
37. **Segment C contactability is 1.00** (20/20 sampled stores: 8 Zid by script, 12 Salla by hand). The 0.0 in the dork
    report was missing data, as recorded on Day 1.
38. **Segment C is rejected by its own kill criterion:** 14 of 20 sampled stores already show a BNPL provider (0.70 >
    0.60; Tabby 11, other providers 3). Salla 11 of 12 (Tabby on 10), Zid 3 of 8. Robust to the one uncertain answer
    (store 1, a terminal redraw during the manual check): 13/20 = 0.65 still hits. Wilson 95% interval 0.48-0.86.
    Business reading: D2C stores on Salla are already covered by BNPL; the open space is offline services (A, B).
39. **Found after the data, not used in the decision:** the Salla vs Zid gap (11/12 vs 3/8) can be platform or method
    (eye vs script on the homepage). A Zid-only D2C segment would be a new hypothesis for fresh data, not a rescue of C.
40. **The manual check needed a method fix mid-way:** Tamara's new logo is a symbol without the word, unknown to a
    reviewer who does not know the brand. Unknown icons were resolved by opening the image URL and looking for the
    provider name, the same signal the script uses.
41. **Data quality:** one A clinic lists an unrelated domain as its website in Google Maps; one Salla store redirects to
    its own domain, which failed on the first load and worked on reload.

## 2026-09-17 — QA of Tabby detections (step 4.2)

Source: `data/samples/bnpl_tabby_qa.md`, `data/changelog.csv`.

42. **All 20 Tabby detections in A and B hold.** The eye check on the homepage confirmed 9 of 20. The 11 `no` answers were
    read in the page source and every one carries a Tabby signal: an integration script (1), the merchant's own text or
    banner (4), a logo in a lazy carousel or the footer (2), patient reviews that mention paying with Tabby (2), and 2
    weak cases (finding 44). The 20 exclusions "already Tabby merchant" stand: A 17, B 3.
43. **For a reviewer who does not read Arabic, the eye check was the weaker instrument:** it missed lazy-loaded logos,
    image file names, reviews and text inside page sections; the markup around the marker was decisive. The two-step
    method was adopted after the eye-check answers came in; the criteria for reading the source were fixed before the
    snippets were read, and every override and its reversal stays in the changelog.
44. **Two clinics carry Tabby only as a lead-source option in a booking form** with identical option ids on both sites (a
    shared booking system). Weak evidence, kept by the ambiguity rule; the first merchants to revisit if the pool runs short.
45. **The `icon` marker kind is now verified for Tabby:** 7 of 7 icon-only detections show a Tabby logo (5 by eye, 2 in
    the page source). Finding 35 stands: at least 16% of A clinics with a loaded homepage are already Tabby merchants.
