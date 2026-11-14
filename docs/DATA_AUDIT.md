# Аудит набора организаторов

Повторный прогон `python scripts/audit_data.py` по `public-train-annotated.jsonl`: 10 000 строк; 4 854 уникальные normalized descriptions; 5 146 повторных строк; 0 конфликтующих label-групп; 0 пустых описаний. Длины описаний: min 1, median 2 196, p95 4 960, max 5 564 символов. Распределение меток: 102=5 484, 103=5 073, 104=4 582, 105=4 562, 106=5 481. SHA-256 исходника: `b7118d68086624fbeab43839f22a635d4e325e4ee339f22d4aa0ad3c2e986615`. Это слабые автоматические labels.

Нормализация `ё` согласована с обучением. Public test: 208 строк, 139 unique descriptions, 69 повторов, 24 строки exact-overlap с train. В нём отсутствует source mcId; оценка принимает 101 только как явное допущение.

Near-duplicate audit (`scripts/audit_near_duplicates.py`, exact-group split, char TF-IDF 3–5 gram cosine nearest neighbor): 199/971 validation descriptions (20.49%) had a train nearest neighbor at cosine ≥0.90, and 152/971 at ≥0.95. Для final comparison использованы connected components с порогом 0.95: 4 074 групп, largest 266; в cross-split не осталось пар ≥0.95, но осталось 70 nearest neighbors ≥0.90. Это прозрачная строгая контрольная split-методика, но не гарантия, что перефразирования ниже .95 не протекают.
