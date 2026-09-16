# State — 2026-09-16, Day 1

## Цель
3 дня → Top-50 A-tier SME-мерчантов в KSA (скоринг, контакт, ЛПР) +
доказательная база: какие источники и сегменты работают, с цифрами.

## Day 1 — план и статус
- [x] Архитектура репозитория, контракт данных (config/schema.yaml), тесты нормализации
- [x] Гипотезы ICP v1 с kill criteria (config/icp.yaml)
- [x] Реестр источников + протокол валидации, пороги зафиксированы до данных (data/sources.yaml)
- [ ] Sample-прогон Google Maps: A и B, Riyadh, 20 записей → ingest → разметка → report
- [ ] Эксперимент: sample A повторно со scrapeContacts=true — прирост fill_instagram vs стоимость
- [ ] Dork-сбор Salla/Zid (сегмент C): проверить паттерн URL на первых 10 результатах
- [ ] Решение по каждому source × segment в data/sources.yaml (дата + причина)
- [ ] Full-прогон только для принятых пар; Instagram по хэндлам из Maps
- [ ] Конец дня: цифры в observations.md, запись в runs.csv со стоимостью

## Day 2 (не начато)
Entity resolution (phone/domain/handle/place_id → merchant_id), исключения
(сети, закрытые, мерчанты Tabby), BNPL-fingerprint, LLM-обогащение, скоринг.

## Известные ограничения на сейчас
- name_location_count считается внутри одного run; пересчёт по всем run — на этапе resolve.
- Паттерны URL Salla/Zid и BNPL-маркеры не подтверждены на живых примерах (verified: false).
- Поля выгрузки Apify Instagram (телефон в профиле) — адаптер толерантен к отсутствию, проверить на sample.

## Открытые вопросы
- Медицинские категории (сегмент A): допустимы ли для BNPL/LTF со стороны Risk — пометка, не фильтр.
