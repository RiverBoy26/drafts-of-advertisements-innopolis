# Avito AI service

Python 3.11+, FastAPI. Internal official-case API: `POST /internal/v1/avito/drafts`, `{description,mcId}` → `{drafts:[{mcId,title,text}]}`. CPU classifier is trained from organizer weak labels; generation calls DeepSeek only when `DEEPSEEK_API_KEY` is configured. RAG is optional and empty until approved examples are curated.

## PowerShell

```powershell
cd ai-service
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
python scripts/train_cpu.py
$env:DEEPSEEK_API_KEY = 'set locally, never commit'
uvicorn app.main:app --host 127.0.0.1 --port 8001
```

`pytest -q` requires no network/key/GPU. `GET /health/ready` reports CPU artifact state. `POST /internal/v1/avito/classify` returns category-only null drafts for CPU demonstration. Official endpoint fails 503 if classifier artifact is missing; if DeepSeek generation fails, preserves categories with null title/text. Costs require actual provider usage plus a configured external price profile; absent usage yields null cost. For labels/audit see repository `data/` and `docs/`.

The Docker image trains the CPU model during its build from the included organizer training data, so it does not depend on a checked-in binary artifact:

```powershell
docker build -t avito-ai:local .
docker run --rm -p 8001:8001 --env-file .env avito-ai:local
```

The optional semantic claim verifier is enabled with `CLAIM_VERIFIER_ENABLED=true`; it adds a DeepSeek call and rejects a draft if the reviewer call fails or reports unsupported claims. It defaults off until live cost and quality have been measured. Deterministic evidence and claim checks always run; neither is a guarantee of factual correctness.

Reproducible offline checks:

```powershell
python scripts/audit_data.py
python scripts/train_cpu.py
python scripts/evaluate_cpu.py
python scripts/audit_near_duplicates.py
python scripts/evaluate_public_test.py
python scripts/validate_rag.py
python scripts/evaluate_rag.py
python scripts/retrieve_rag.py 103 'Укладка плитки в ванной'
```

RAG retrieval is wired and filters to approved examples, but the curated store is deliberately empty until a reviewer supplies human-approved entries. `evaluate_rag.py` reports `NOT_MEASURED` without a separately labeled relevance query set; it does not treat self-retrieval as a quality score.

`evaluate_public_test.py` is a transparent public benchmark (not a blind estimate); it assumes source mcId 101 because the organizer parquet has no source ID column. Before a paid real call, use `python scripts/live_smoke.py`; it is disabled unless `ENABLE_LIVE_API_TESTS=true` and a key is present. Official DeepSeek API behavior and token rates: [Chat Completions](https://api-docs.deepseek.com/api/create-chat-completion/), [Thinking mode](https://api-docs.deepseek.com/guides/thinking_mode/), [Pricing](https://api-docs.deepseek.com/quick_start/pricing/).
