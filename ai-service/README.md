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

The optional local RuBERT-base experiment uses PyTorch and Transformers in a CUDA-enabled environment. Install the project requirements there, install a CUDA-enabled PyTorch build, then `pip install -r requirements-transformer.txt` and run `python scripts/train_rubert_base.py`; the output is stored under `artifacts/rubert_base/`. The selected local blend is 75% noise-trained CPU + 25% RuBERT at threshold 0.525. It was selected on five grouped folds and an experimenter-authored unseen-template OOD test; see `docs/NOISE_ROBUSTNESS.md` for the measured tradeoff and limits. If RuBERT weights are unavailable, the service falls back to the noise-trained CPU model. Set `LOCAL_CLASSIFIER_BACKEND=cpu` to force CPU or `rubert` to use RuBERT alone. Docker trains the noise-trained CPU artifact from the included augmented dataset; it does not contain RuBERT weights.

The Docker image trains the CPU model during its build from the augmented training copy, so it does not depend on a checked-in binary artifact:

```powershell
docker build -t avito-ai:local .
docker run --rm -p 8001:8001 --env-file .env -v "${PWD}/artifacts:/service/optional-artifacts:ro" avito-ai:local
```

The semantic claim verifier is enabled with `CLAIM_VERIFIER_ENABLED=true` and always runs when `targetMcIds` are supplied. It adds a DeepSeek call and rejects a draft if the reviewer call fails or reports unsupported claims. Deterministic checks also run; neither is a guarantee of factual correctness.

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

RAG retrieval is wired and filters to approved examples. The curated store contains one official organizer example for category 104; other categories await reviewed examples. `evaluate_rag.py` reports `NOT_MEASURED` without a separately labeled relevance query set; it does not treat self-retrieval as a quality score.

In the normal workflow (`CLASSIFIER_MODE=cpu`, the Compose default), the local classifier selects candidate IDs from 102–106. A local service-offer check then removes IDs without evidence in the author's text, including obvious search-keyword tails; it does not predict new IDs. Only accepted IDs reach DeepSeek in one batch request. The semantic guard checks each generated draft against the source. A caller with an external classifier may supply `targetMcIds` in the same request and skip local classification, but the service-offer check still applies. Diagnostics distinguish `targetMcIds`, `acceptedTargetMcIds`, and `unsupportedTargetMcIds`. An official organizer example is available to RAG for category 104 as a style reference; public training rows are not indexed because they contain weak labels and noisy text.

The 100-case check is reproducible with `python scripts/evaluate_generation_100.py`. It selects 25 distinct examples in each of four length bands, skips obvious noisy product metadata, checkpoints every completed case in `docs/generation_100_results.jsonl`, and calls an independent DeepSeek quality reviewer for each response. It resumes from completed case numbers and stops at an estimated $1 budget. Run `python scripts/summarize_generation_100.py` afterwards for the readable report and per-case/per-draft CSV files. These judgments are automated; inspect the source and draft side by side before treating them as a quality benchmark.

`evaluate_public_test.py` is a transparent public benchmark (not a blind estimate); it assumes source mcId 101 because the organizer parquet has no source ID column. Before a paid real call, use `python scripts/live_smoke.py`; it is disabled unless `ENABLE_LIVE_API_TESTS=true` and a key is present. Official DeepSeek API behavior and token rates: [Chat Completions](https://api-docs.deepseek.com/api/create-chat-completion/), [Thinking mode](https://api-docs.deepseek.com/guides/thinking_mode/), [Pricing](https://api-docs.deepseek.com/quick_start/pricing/).

Generation with known categories: send `targetMcIds` (unique integer IDs 102–106) together with `description` and source `mcId=101` to the drafts endpoint. This bypasses category prediction. Candidate IDs without confirmed service evidence are omitted from `drafts` and listed in diagnostics; an empty accepted list returns `drafts: []` without a DeepSeek call. Structural validation runs locally; a mandatory semantic guard checks the full source. Rejected generated drafts are regenerated only for their rejected category IDs, with the guard's feedback, and checked again. `GUARDRAIL_RETRY_ATTEMPTS` sets the number of regeneration attempts (default 2, capped at 3); accepted sibling drafts are preserved. Diagnostics include attempt count, recovered category IDs, total time, provider calls, token usage, and estimated cost. Historical 100-case results use weak dataset labels and are not a human gold benchmark.

Generation defaults to `GENERATION_REQUEST_MODE=batch`: the first DeepSeek call drafts all selected categories together from the full source. Verification checks each result; only missing or rejected categories are regenerated, with up to `GENERATION_CONCURRENCY=5` repair calls at once and at most `GUARDRAIL_RETRY_ATTEMPTS` attempts. Accepted siblings are preserved. `per_category` remains available for comparison. The generation prompt mirrors useful formatting from the source, such as restrained emoji and short lists, while keeping every claim grounded in the source. Live evaluation results are stored separately from tracked source files.
