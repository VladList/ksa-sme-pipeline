# KSA SME Merchant Pipeline — бриф (2026-09-16)

Пайплайн outbound-лидогенерации SME-мерчантов в KSA под BNPL (кейс под
отбор на Business Development Executive, Tabby). Артефакт для CV и
собеседования, не продакшен. Срок — 3 дня.

## Приоритеты
1. Решения на цифрах: источник принимается или отклоняется по метрикам, а не по ощущению.
2. Прозрачность важнее точности: каждый порог, вес и отказ записан с причиной и датой.
3. Нет evidence_url — нет строки.
4. Не обещать: не создавать файлы, папки, зависимости и команды под будущие шаги.
   Появляются вместе с кодом, который реально запускался.

## Правила данных
- data/raw/ иммутабелен, не коммитится. Имя файла = run_id, строка в data/runs.csv.
- Колонки и их порядок — только из config/schema.yaml. Поле от LLM — суффикс _inferred.
- PII (телефоны, имена владельцев, текст био) — только в data/interim и data/private.
  В data/samples и output/public — маскированно. Pre-commit блокирует немаскированные мобильные.
- Отклонённые источники и сегменты не удаляются, а получают status + reason.
- Фильтрация не удаляет строки, а пишет exclusion_reason (Day 2).

## Правила сбора
- Только публичные бизнес-листинги и публичные бизнес-профили.
- LinkedIn не скрейпить. Персональные данные авторов отзывов не собирать.
- Bot-challenge (Cloudflare и т.п.) не обходить, User-Agent браузера не подменять: такая страница = fetch_failed.
- Сначала sample-прогон (20 записей на source × segment), потом full.

## Команды (существуют)
- uv run pytest -q
- uv run python scripts/01_build_apify_inputs.py google_maps --mode full|sample   (проверка бюджета от spent_usd)
- uv run python scripts/02_ingest.py <source_id> <raw_file> [--segment <segment>]
- uv run python scripts/03_source_report.py sample|report <source_id> <segment> --runs "<glob run_id>"   (пробы исключать)
- uv run python scripts/04_resolve.py   (записи → мерчанты; правила только в config/rules.yaml, изменения — с версией и причиной)
- uv run python scripts/05_web_fingerprint.py --probe <url> [<url> ...] [--refresh]   (BNPL-маркеры на живых страницах; кэш data/cache/web/, не коммитится)
- uv run python scripts/05_web_fingerprint.py --run [--limit N]   (главные страницы eligible → data/interim/bnpl.csv, сводка data/samples/bnpl_summary.md)
- uv run python scripts/05_web_fingerprint.py --manual-c   (ручная проверка выборки C, которую скрипт не загрузил; ответы y/n/?, сохраняются по магазину)
- uv run python scripts/05_web_fingerprint.py --qa-tabby   (QA всех детекций Tabby в A и B: глазом, затем `no` разбираются по коду страницы через adjudicate_tabby; переопределения — в data/changelog.csv)
- uv run python scripts/06_enrich.py --dry-run | --check | --trial | --run   (LLM-обогащение A и B по config/llm.yaml; ключ OPENAI_API_KEY в .env; ответы кэшируются в data/cache/llm/)
- uv run python scripts/07_score.py   (скоринг, тиры, Top-50, sensitivity по config/scoring.yaml → data/interim/scored.csv, data/samples/scoring_summary.md)
- uv run python scripts/check_no_pii.py <files>

## Окружение
.env не читается агентом (.claude/settings.json). data/private/ тоже.
