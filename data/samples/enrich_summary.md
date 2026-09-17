# LLM enrichment (step 4.3)

Model `gpt-5.6-luna`, prompt `v1`, run 2026-09-17. Counts only: names and hooks stay in data/interim/. All model fields end with `_inferred`; Arabic hooks are AI-drafted and not native-reviewed.

- pool: 519
- pool_by_segment: {'A_aesthetic_clinics': 233, 'B_custom_furniture': 286}
- pool_by_input: {'name_only': 386, 'page_text': 133}
- chosen: 519
- estimated_input_tokens: 506226
- answered: 519
- errors: Counter()
- input_tokens: 398560
- output_tokens: 134558
- cost_this_run_usd: 0
- cost_all_answers_usd: 0.2412
- cost_per_merchant_usd: 0.00046
- cost_per_merchant_by_input_usd: {'name_only': 0.0004, 'page_text': 0.00064}
- projected_all_usd: 0.241
- owner_name_given: 48
- owner_name_in_source: 48
- owner_roles: {'unknown': 471, 'doctor_or_person_in_business_name': 42, 'founder': 5, 'owner': 1}
- ticket_basis: {'category_typical': 441, 'unknown': 66, 'prices_on_page': 12}
- by_input: {('name_only', False): 355, ('page_text', False): 116, ('name_only', True): 31, ('page_text', True): 17}
- g3_by_segment: {'A_aesthetic_clinics': {'merchants': 233, 'contactable': 186, 'owner_name_verified': 43, 'name_and_contactable': 42, 'hook_from_page': 90, 'price_on_page': 11}, 'B_custom_furniture': {'merchants': 286, 'contactable': 275, 'owner_name_verified': 5, 'name_and_contactable': 5, 'hook_from_page': 43, 'price_on_page': 1}}
