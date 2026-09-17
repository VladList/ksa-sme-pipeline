# Merge QA — 2026-09-17

Scope: all 39 merchants built from 2+ records by stage 4 with rules v1. Each merge was reviewed by name, Maps category,
city and the identifier that linked it; ambiguous group links were checked on the web. No phone numbers are listed.

| verdict | merchants | examples / notes |
|---|---|---|
| correct: same brand, shared domain or Instagram | 29 | Ram Clinics, Stars Smile, BellaDerm (4 branches), Kaya, Lines, JosephDerm, Alshakreen (4), Sedar, Ayat curtains, Alguthmi textile |
| correct: doctor listing merged into its host clinic by a shared phone | 2 | Derma Vitalis + a dermatologist listing; Ideal Clinics + an endodontist listing |
| correct: one operator behind several generically named listings (shared phone or site) | 4 | B listings named "تفصيل ستائر …" |
| correct: group link confirmed on the web | 1 | Meras + Mozdanh (the group's clinic finder lists Mozdanh branches; a clinic directory calls Mozdanh part of the Meras group) |
| wrong | 1 | two unrelated upholstery shops linked through the classifieds site haraj.com.sa |
| unverified | 2 | Masters clinics + a doctor listing whose address names another clinic; Soft Leather Clinic + Eternal Beauty (shared domain and Instagram) |

Merge precision: 36 of 37 verified merges correct (0.97); worst case counting unverified as wrong 36 of 39 (0.92).

## Rule changes that followed (config/rules.yaml v2)

1. Classifieds domains (haraj.com.sa, opensooq.com, mstaml.com) never link businesses.
2. Segment B excludes merchants present in both cities: the hypothesis is a local workshop, not a multi-city company
   (Sedar, Alguthmi textile, Ayat curtains, Zerabi). Segment A keeps multi-city merchants because its definition allows
   up to 5 branches (Ram Clinics, Stars Smile stay eligible).
3. Curated `same_as` link Meras ↔ Mozdanh with evidence, and the Meras group is excluded as a group with 6+ branches.

## Effect of v2 (stage 4 re-run)

- Merchants: 765 (37 built from 2+ records): the haraj merge split, Meras and Mozdanh joined.
- B eligible 292 -> 289 (4 merchants excluded as multi-city companies, 3 of them previously eligible).
- A eligible unchanged at 250 (the Meras group was already excluded for lacking a specialty keyword; it is now excluded
  for the right reason).
