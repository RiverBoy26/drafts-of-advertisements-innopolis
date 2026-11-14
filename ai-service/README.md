# Avito AI service

Python 3.11+, FastAPI. Internal official-case API: `POST /internal/v1/avito/drafts`, `{description,mcId}` → `{drafts:[{mcId,title,text}]}`. The current CPU model is char-boundary TF-IDF (3–5 grams, min_df=2) with balanced One-vs-Rest Logistic Regression (C=200), trained from organizer weak labels. Five near-duplicate-grouped validation folds average micro-F1 0.9395 at threshold 0.45; see `docs/MODEL_SELECTION.md` for the measured limits and transformer research. Generation calls DeepSeek only when `DEEPSEEK_API_KEY` is configured. RAG is optional and empty until approved examples are curated.

## PowerShell

```powershell
cd ai-service
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
# Поместите готовый artifacts/cpu_char.joblib перед запуском.
$env:DEEPSEEK_API_KEY = 'set locally, never commit'
uvicorn app.main:app --host 127.0.0.1 --port 8001
```

`pytest -q` requires no network/key/GPU. `GET /health/ready` reports CPU artifact state. `POST /internal/v1/avito/classify` returns category-only null drafts for CPU demonstration. Official endpoint fails 503 if classifier artifact is missing; if DeepSeek generation fails, preserves categories with null title/text. Costs require actual provider usage plus a configured external price profile; absent usage yields null cost. For labels/audit see repository `data/` and `docs/`.

The optional local RuBERT-base experiment uses PyTorch and Transformers in a CUDA-enabled environment. Install the project requirements there, install a CUDA-enabled PyTorch build, then `pip install -r requirements-transformer.txt` and run `python scripts/train_rubert_base.py`; the output is stored under ignored `artifacts/rubert_base/`. `LOCAL_CLASSIFIER_BACKEND=auto` uses the 50/50 RuBERT+CPU blend (threshold 0.475) when local model weights exist, and otherwise uses CPU. Set it to `cpu` to force the fallback or `rubert` to use RuBERT alone. If loading the optional model fails, the service logs the issue and uses the CPU model. Docker does not include the weights, so it uses CPU. The GPU experiment is measured in `docs/EXPERIMENT_RESULTS.md`; its labels are still weak organizer labels.

The Docker image does not train a model. Place an existing compatible CPU artifact at `ai-service/artifacts/cpu_char.joblib`; root Compose mounts that directory read-only. Until the file is present, `/health/ready` returns 503. The current Docker image does not include PyTorch, so RuBERT weights alone are insufficient.

The root Compose file starts this service on the internal address `http://ai-service:8001`, checks `/health/ready`, and shares `INTERNAL_API_TOKEN` with Java. Java and the frontend can start before the artifact is supplied; analyses report classifier unavailability until then. It defaults to CPU classification with `GENERATOR_PROVIDER=disabled`; enable DeepSeek generation by setting `GENERATOR_PROVIDER=deepseek` and `DEEPSEEK_API_KEY` in the root `.env`. Java accepts titles up to 255 characters and text up to 10,000; oversized generated copy is returned as paired nulls. The trained data covers source category 101, so predictions for other source categories are not validated and the model cannot suggest 101 as a target.

```powershell
docker build -t avito-ai:local .
docker run --rm -p 8001:8001 --env-file .env -v "${PWD}/artifacts:/service/artifacts:ro" avito-ai:local
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
