# Воспроизведение conflict-resolved ансамбля

Ветка `develop` содержит код актуального кандидата, конфигурацию, подготовленные наборы данных и аудит изменений. Веса намеренно хранятся отдельно от Git. Закрытый тестовый CSV и созданные по нему построчные предсказания в репозиторий не добавлены.

## Запуск модели на другом компьютере

1. Получите ветку `develop` и установите зависимости из `requirements.txt` и `requirements-transformer.txt`. Для быстрого инференса и обучения RuBERT установите совместимую сборку PyTorch с CUDA; на CPU инференс будет медленнее.
2. Распакуйте архив весов в `ai-service/artifacts/` так, чтобы существовали файлы `cpu_char_conflict_resolved.joblib` и каталог `rubert_conflict_resolved/` с конфигурацией, токенизатором и весами RuBERT.
3. Скопируйте `.env.example` в `.env`, оставьте настройки ансамбля из примера и запустите AI-сервис по инструкции в `README.md`.

Установка Python-зависимостей из `ai-service`:

```powershell
python -m pip install -r requirements.txt
python -m pip install -r requirements-transformer.txt
```

Параметры ансамбля и измеренные характеристики описаны в [MODEL_CONFIGURATION_RU.md](MODEL_CONFIGURATION_RU.md). Основной разбор кандидата находится в `../output/pdf/avito_last_model_analysis_ru.pdf`.

## Данные и подготовка

- `data/user-updated-train.jsonl` — исходная слабая обучающая разметка.
- `data/user-updated-train-conflict-resolved-base.jsonl` — дедуплицированная копия с точечными исправлениями разметки.
- `data/manual-conflict-resolved-additions.jsonl` — новые ручные примеры.
- `data/user-updated-train-conflict-resolved.jsonl` — объединённая база.
- `data/human_style_trap_candidates.jsonl`, `data/intent_context_augmented.jsonl`, `data/offer_scope_contrasts.jsonl` — дополнительные ловушки и контрастные примеры для обучения.
- `data/user-updated-ood.jsonl` — отдельная проверка на тексты вне целевых категорий.
- `data/source_manual/` — исходные XLSX и CSV ручных дополнений. `data/manual_reference_from_xlsx.json` — ручной эталон для независимой проверки; строки, попавшие в обучение, исключаются из контрольной выборки.
- `reports/conflict_resolved_data_audit.json` — число удалённых точных дублей, принятые решения по конфликтным группам и источник ручных примеров.

Подготовленные JSONL уже включены в репозиторий. Чтобы пересоздать их из источников, из папки `ai-service` выполните:

```powershell
python scripts/prepare_conflict_resolved_data.py
```

Скрипт читает исходный файл `data/user-updated-train.jsonl` и файлы в `data/source_manual/`; он сохраняет аудит и три обучающие версии JSONL.

## Повторное обучение и проверка

Для точного повторения обучения дополнительно нужны предыдущие базовые веса: `artifacts/cpu_char_intent_context.joblib` и `artifacts/rubert_intent_context/`. Они не включены в Git по просьбе хранить веса отдельно. Обучение RuBERT требует CUDA. Когда эти веса распакованы, выполните из `ai-service`:

```powershell
python scripts/train_conflict_resolved_candidate.py
```

Скрипт переобучит CPU-модель и RuBERT, оценит кандидата на ручной отложенной выборке из 19 объявлений и OOD-наборе из 800 текстов, затем сохранит метрики в `work/conflict_resolved_candidate_eval.json`. Он не читает закрытый CSV и не создаёт секретную отправку.

Чтобы построить CSV для закрытой проверки, явно передайте путь к локальному файлу. CSV и результаты остаются локальными:

```powershell
python scripts/evaluate_conflict_resolved_candidate.py `
  --private-csv "C:\path\to\private-test-dataset.csv" `
  --output "..\outputs\private-test-submission-conflict-resolved.csv"
```

В отчёт записываются локальные метрики ручной и OOD-проверок и число строк созданного CSV; целевые метки закрытого набора недоступны, поэтому этот запуск не вычисляет его score.

## Зафиксированные результаты

- Независимая ручная выборка: 19 объявлений; micro-F1 `0.9091`, precision `0.8333`, recall `1.0000`, exact match `0.7368`.
- OOD-набор: 1 объявление с ложным срабатыванием из 800 (`0.125%`).
- Тёплая классификация на RTX 3050: p50 `15.35 мс`, p95 `62.34 мс`, среднее `36.26 мс`; загрузка моделей — около `8.31 с`.
- Для предыдущей отправки известно `89%`. Score нового кандидата закрытая система ещё не сообщила; локальные метрики не заменяют этот результат.

Агрегаты сохранены в `reports/conflict_resolved_metrics.json` и `reports/conflict_resolved_latency.json`. Подробный разбор — в PDF-отчёте.

Для повторной сборки PDF дополнительно установите `reportlab`; сам готовый PDF уже лежит в репозитории.
