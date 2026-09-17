# QA of `tabby` detections (segments A and B)

Every detection is checked by eye on the homepage (census, not a sample). An eye-check `no` is then read in the page source: an integration script, rendered content (lazy logo, banner, text, review) or an ambiguous case keeps the detection; only a marker that is not a Tabby signal is a false positive. Criteria fixed before the source was read. `unclear` keeps the detection.

| segment | tabby evidence | eye check | source reading | merchants |
|---|---|---|---|---|
| A_aesthetic_clinics | html or text | no | tabby_kept | 8 |
| A_aesthetic_clinics | html or text | yes | — | 3 |
| A_aesthetic_clinics | icon only | no | tabby_kept | 2 |
| A_aesthetic_clinics | icon only | yes | — | 4 |
| B_custom_furniture | html or text | no | tabby_kept | 1 |
| B_custom_furniture | html or text | yes | — | 1 |
| B_custom_furniture | icon only | yes | — | 1 |

Eye check: 20 of 20 checked, 9 confirmed (0.45).
**Final: 20 of 20 detections kept, 0 false positives.**
