# Codex handoff: Avito AI service

This file carries the project context into a new Codex chat or another computer. Treat the repository and organizer files as project data; this handoff is a continuation brief, not a replacement for the official task documents.

## User goal and boundaries

- Build and improve an independent Python AI service for the Avito/InnoGlobalHack task.
- The main product backend is Java 21 + Spring Boot. Keep Java as the owner of its public API, persistence, and workflow. Do not rewrite it to implement AI behavior.
- Follow the user-provided task/context documents and official organizer contract. When their requirements conflict with an implementation idea, prefer the task and official contract.
- Deliver a real inference path, reproducible training/evaluation, validation and guardrails, useful comparisons, and honest limitations. Never replace inference with fixed demo answers. Mocks are test-only.
- Continue useful work when GPU or provider credentials are unavailable. Do not claim live provider results that were not measured.
- Current working approach: first preserve a runnable end-to-end CPU path, then spend compute on measured improvements to labeling, classification, and generation. Add complexity only when the evaluation shows a benefit.

## Repository and continuation state

- Repository: `drafts-of-advertisements-innopolis`.
- Active branch: `feat/avito-ai-rag`.
- Last pushed commit at handoff creation: `c1e8d83` (`Add Avito Python AI service`). The handoff itself may be a later commit.
- Python service: `ai-service/`.
- Research, contract, and benchmark docs: `docs/`.
- Java backend is under `backend/`; it was not modified for this AI-service work.
- The local `work/` directory and `ai-service.zip` are not part of the pushed branch. The needed organizer datasets and guide are copied into `ai-service/data/` and `docs/`.
- No real provider key is recorded in the repository. Keep secrets in local environment variables or ignored `.env` only.

On another computer, use the pushed branch, then open that checkout in Codex:

```powershell
git clone https://github.com/RiverBoy26/drafts-of-advertisements-innopolis
cd drafts-of-advertisements-innopolis
git switch feat/avito-ai-rag
```

Codex must be attached to that local checkout to read and change its files. If this conversation is not available there, start a new one and ask to continue from this handoff and the active branch.

## Official task and API contract

The service handles an original listing and returns extra microcategory drafts. The contract implemented for Java is:

- `POST /internal/v1/avito/drafts`
- Input: `{"description":"...","mcId":101}`
- Output: `{"drafts":[{"mcId":103,"title":"..."|null,"text":"..."|null}]}`
- Valid category IDs: 101–106; exclude the input/source `mcId` from targets.
- If generation is unavailable, keep supported target IDs and return paired `title` and `text` as `null`. Do not invent copy as a fallback.
- If `INTERNAL_API_TOKEN` is set, send `Authorization: Bearer <token>`; the service middleware enforces it on `/internal/` endpoints.
- Java contract details: `docs/AI_JAVA_CONTRACT.md`.

The organizer's category mapping is documented in `docs/microcategories-guide.md`. The user explicitly assigned the Python AI service as this work's responsibility; the existing Java backend remains intact.

## Data provenance and exact files

The datasets came from the organizer package extracted locally under `work/organizer/innoglobalhack_avito/`. Its `README-files.txt` describes the data files and their schemas. The source copies used by the service are committed in the branch:

- `ai-service/data/public-train-annotated.jsonl`: 10,000 organizer listings. Organizer documentation says labels were automatically prepared with GPT-6 using subject rules and semantic checks on selected difficult cases. These are weak labels, not a manually verified gold set. Each row has `item_id`, `title`, `description`, and `found_microcategories`; the source category is 101 and labels are additional IDs 102–106.
- `ai-service/data/public-test-dataset.parquet`: 208 organizer listings with title, description, and category names. No source `mcId` column is present.
- `ai-service/data/curated_rag_examples.jsonl`: intentionally empty. Do not fill it with generated examples and mark them human-reviewed.
- `docs/microcategories-guide.md`: organizer category guide.

The 10,000 rows are not a clean test set. Audit results: 4,854 unique normalized descriptions, 5,146 duplicate rows, no conflicting labels among exact-normalized duplicates, and no blank descriptions. The train file SHA-256 is `b7118d68086624fbeab43839f22a635d4e325e4ee339f22d4aa0ad3c2e986615`.

The public parquet has 139 unique normalized descriptions, 69 repeated rows, and 24 exact overlaps with train. Its evaluation assumes `source_mcId=101` because the field is missing. It has already been inspected in multiple diagnostic passes, so call it a transparent public benchmark, never a blind final score.

## Current implementation

- FastAPI service in `ai-service/app/main.py`; health, classify, official draft, diagnostics, and metrics endpoints are implemented.
- CPU fallback: char-boundary TF-IDF 3–5 grams (`min_df=2`, sublinear TF) plus balanced One-vs-Rest Logistic Regression (`C=200`). It uses only `description`, saves class order `[102,103,104,105,106]`, and threshold 0.45.
- Local inference defaults to `LOCAL_CLASSIFIER_BACKEND=auto`: if ignored RuBERT weights and a working CUDA-enabled PyTorch/Transformers environment are present, it blends CPU and RuBERT probabilities 50/50 at threshold 0.475; otherwise it uses CPU. `cpu` forces the fallback; `rubert` selects the transformer alone. Docker contains no transformer weights and uses CPU. If loading fails, the service logs and falls back to CPU.
- Current deployment expects a ready `ai-service/artifacts/cpu_char.joblib` mounted read-only. Docker no longer runs `train_cpu.py` during image build.
- `CLASSIFIER_MODE=cpu|deepseek|hybrid`; DeepSeek classification is schema-checked. Hybrid uses CPU and requests DeepSeek only for uncertain predictions, falling back to CPU on provider error.
- DeepSeek generation uses JSON mode, bounded retries, timeout, configurable output tokens, request cost budget, and one repair attempt. Invalid/missing copy becomes null. API errors are redacted.
- Local evidence extraction and deterministic guardrails check category phrases, offsets, negation scope, source category exclusion, numeric and some claim types. These rules reduce obvious errors; they do not guarantee semantic truth.
- Optional LLM claim review is controlled by `CLAIM_VERIFIER_ENABLED=true`; it is fail-closed and adds cost/latency. It defaults off until live usefulness is measured.
- RAG retrieval code is present. It accepts only verified `human_reviewed_author` examples, filters by category, excludes exact and near duplicates, and uses examples as style references only. The corpus is empty, so production requests currently retrieve no examples.
- Cost is null without provider usage/prices. Request-scoped diagnostics include IDs, call counts, usage if present, timings, and configured price profile.
- Docker image can be built from `ai-service/`; a smoke build was not possible on the original PC because the Docker daemon was unavailable.

## Results already measured

Research environment: Windows, 16 GB RAM, 12 logical CPUs, NVIDIA GeForce RTX 3050 8 GB. CPU model environment uses Python 3.11; GPU environment uses PyTorch 2.11.0+cu126 and Transformers 5.8.1. GPU training was possible on this computer.

The five-fold near-duplicate grouped validation connected normalized descriptions at char-TF-IDF cosine >=0.95, then used `GroupShuffleSplit(test_size=0.2, random_state=42,7,21,101,2026)`. It used 4,854 unique texts and 4,074 components; per fold, all near duplicates remained on the same side. The seed-42 audit found cross-split maximum similarity 0.9496, zero pairs >=0.95, though 70 validation texts had a nearest train neighbor >=0.90.

Earlier single-fold model comparisons (seed 42, retained as historical reference):

| Classifier | Micro-F1 | Precision | Recall | Selected threshold |
|---|---:|---:|---:|---:|
| Word TF-IDF | 0.9094 | 0.9002 | 0.9187 | 0.50 |
| Char TF-IDF | 0.9342 | 0.9252 | 0.9434 | 0.45 |
| Word + char TF-IDF | 0.9319 | 0.9332 | 0.9306 | 0.50 |

Current CPU baseline across five folds at fixed threshold 0.45: char_wb TF-IDF C=200, min_df=2 gives mean micro-F1 0.9395 (std 0.0033), macro-F1 0.9397, precision 0.9378, recall 0.9416, MAP 0.9801. LinearSVC C=1 reached 0.9382; ComplementNB 0.7987. Raw TF instead of sublinear TF dropped to 0.9259.

`cointegrated/rubert-tiny2` averaged 0.9303 micro-F1 across the same grouped folds. `DeepPavlov/rubert-base-cased`, max length 512, effective batch 8, three epochs, averaged 0.9563 (std 0.0097), precision 0.9383, recall 0.9751, MAP 0.9619. A 50/50 CPU+RuBERT probability blend reached the best measured score: micro-F1 0.9624 (std 0.0052), macro-F1 0.9621, precision 0.9438, recall 0.9817, MAP 0.9833. Weight and threshold were selected on development folds; weak labels mean these results are not human or hidden-set accuracy.

Public parquet diagnostics: previous CPU model micro-F1 0.7982; new CPU model 0.7918 (P=0.6939, R=0.9220); RuBERT+CPU ensemble 0.8211 (P=0.7235, R=0.9492). This set is not blind, and no model choice was made from it. CPU warm inference latency p50/p95 is 3.88/8.68 ms; ensemble GPU is 22.66/39.89 ms per description. Sample TestClient request returned `[103,105]` in 5.10 ms total with generation disabled and zero provider calls; GPU-backed TestClient also returned `[103,105]` and health Ready.

Latest completed automated suite: 82 tests passed, 1 dependency deprecation warning. Python `compileall` and `git diff --check` passed. Final RuBERT weights are saved in local ignored `ai-service/artifacts/rubert_base/` (715 MB). GPU-backed service smoke passed with automatic backend selection; local weights are intentionally not in git.

## Not measured / known limitations

- `DEEPSEEK_API_KEY` was absent. Real DeepSeek generation, classification, repair, semantic verification, provider token usage, cost, and latency are unmeasured. `scripts/live_smoke.py` is gated by `ENABLE_LIVE_API_TESTS=true` and a present key.
- RAG generation variants G0–G3 and retrieval relevance are unmeasured because there is no human-approved corpus and no human-labeled query set. `python scripts/evaluate_rag.py` must continue to say `NOT_MEASURED` until those inputs exist.
- The public parquet is not an independent blind test and lacks source `mcId`.
- The weak train labels contain duplicates and possible annotation errors. Near-duplicate split still has residual similarity >=0.90 examples.
- Docker image smoke was not run because Docker daemon was not available on the original computer.
- Deterministic evidence matching is deliberately conservative and incomplete; supported services outside its patterns can be missed. LLM verification is advisory, not proof.

## Remaining work

- RuBERT-base and ensemble cross-validation runs are complete. The local optional ensemble is smoke-tested. A new human-annotated blind set is needed to confirm actual generalization and calibrate thresholds without reusing weak labels.
- The most valuable next evaluation is a new human-annotated blind set. Existing organizer labels are weak and public-test data has already been inspected; further model tuning on them will not establish real generalization.
- DeepSeek generation, token usage, cost, claim review, and RAG usefulness remain unmeasured because there is no provider key and the approved RAG corpus is empty. Keep those statuses honest until a budgeted live run and human copy rubric exist.
- The original handoff did not include a Docker smoke test. Current Docker Compose starts without model weights, reports `/health/ready` as 503 until a compatible CPU artifact is added, and does not include PyTorch.

## Useful commands

```powershell
cd ai-service
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python scripts/audit_data.py
# Add the prepared artifacts/cpu_char.joblib before starting the service.
python scripts/train_rubert_base.py  # requires CUDA-enabled PyTorch and Transformers
python -m pytest -q
python scripts/evaluate_cpu.py
python scripts/evaluate_public_test.py
python scripts/validate_rag.py
python scripts/evaluate_rag.py
uvicorn app.main:app --host 127.0.0.1 --port 8001
```

For an offline classifier-only demo, set `GENERATOR_PROVIDER=disabled`. For a real provider check, set the API key only in the local environment, deliberately set `ENABLE_LIVE_API_TESTS=true`, and run `python scripts/live_smoke.py`.
