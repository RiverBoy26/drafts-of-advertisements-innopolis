# Live demo

Windows PowerShell: положить готовый `cpu_char.joblib` в `ai-service/artifacts`, затем из корня проекта запустить `docker compose up -d --build`. Проверить `GET /health/ready` внутри ML-контейнера; до добавления артефакта он возвращает 503. Для генерации текста задать `GENERATOR_PROVIDER=deepseek` и `DEEPSEEK_API_KEY` в корневом `.env`. По умолчанию генерация отключена: классификатор возвращает категории с `title` и `text`, равными null. Новые тексты обрабатываются текущим inference, canned responses нет. Измерения 10 новых примеров и стоимость пока `NOT_MEASURED`.
