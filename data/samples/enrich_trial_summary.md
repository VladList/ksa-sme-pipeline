# LLM enrichment (step 4.3) — TRIAL

Model `gpt-5.6-luna`, prompt `v1`, run 2026-09-17. Counts only: names and hooks stay in data/interim/. All model fields end with `_inferred`; Arabic hooks are AI-drafted and not native-reviewed.

- pool: 519
- pool_by_segment: {'A_aesthetic_clinics': 233, 'B_custom_furniture': 286}
- pool_by_input: {'name_only': 386, 'page_text': 133}
- chosen: 20
- estimated_input_tokens: 27269
- answered: 20
- errors: Counter()
- input_tokens: 21761
- output_tokens: 5606
- cost_this_run_usd: 0.0111
- cost_per_merchant_usd: 0.00055
- cost_per_merchant_by_input_usd: {'name_only': 0.00039, 'page_text': 0.00072}
- projected_all_usd: 0.246
- owner_name_given: 3
- owner_name_in_source: 3
- owner_roles: {'doctor_or_person_in_business_name': 3, 'unknown': 17}
- ticket_basis: {'category_typical': 17, 'unknown': 3}
- by_input: {('page_text', True): 2, ('page_text', False): 8, ('name_only', False): 9, ('name_only', True): 1}
