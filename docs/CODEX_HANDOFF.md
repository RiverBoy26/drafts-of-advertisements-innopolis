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
- CPU classifier: character TF-IDF 3–5 grams plus One-vs-Rest Logistic Regression. It uses only `description`, saves class order explicitly as `[102,103,104,105,106]`, and uses threshold 0.45.
- Rebuild the local ignored model artifact with `python scripts/train_cpu.py`. Docker trains the artifact during image build from the committed training data.
- `CLASSIFIER_MODE=cpu|deepseek|hybrid`; DeepSeek classification is schema-checked. Hybrid uses CPU and requests DeepSeek only for uncertain predictions, falling back to CPU on provider error.
- DeepSeek generation uses JSON mode, bounded retries, timeout, configurable output tokens, request cost budget, and one repair attempt. Invalid/missing copy becomes null. API errors are redacted.
- Local evidence extraction and deterministic guardrails check category phrases, offsets, negation scope, source category exclusion, numeric and some claim types. These rules reduce obvious errors; they do not guarantee semantic truth.
- Optional LLM claim review is controlled by `CLAIM_VERIFIER_ENABLED=true`; it is fail-closed and adds cost/latency. It defaults off until live usefulness is measured.
- RAG retrieval code is present. It accepts only verified `human_reviewed_author` examples, filters by category, excludes exact and near duplicates, and uses examples as style references only. The corpus is empty, so production requests currently retrieve no examples.
- Cost is null without provider usage/prices. Request-scoped diagnostics include IDs, call counts, usage if present, timings, and configured price profile.
- Docker image can be built from `ai-service/`; a smoke build was not possible on the original PC because the Docker daemon was unavailable.

## Results already measured

Reproducible run environment at the time: Windows 10, Python 3.12.10, AMD Ryzen 5 7520U (4 cores / 8 threads), integrated AMD Radeon only. There was no usable discrete GPU.

The near-duplicate grouped validation connected normalized descriptions at char-TF-IDF cosine >=0.95, then used `GroupShuffleSplit(test_size=0.2, random_state=42)`: 3,928 train and 926 validation examples, 4,074 components, largest component 266. Cross-split maximum cosine was 0.9496; zero pairs were >=0.95, though 70 validation examples had a nearest train neighbor >=0.90.

| Classifier | Micro-F1 | Precision | Recall | Selected threshold |
|---|---:|---:|---:|---:|
| Word TF-IDF | 0.9094 | 0.9002 | 0.9187 | 0.50 |
| Char TF-IDF | 0.9342 | 0.9252 | 0.9434 | 0.45 |
| Word + char TF-IDF | 0.9319 | 0.9332 | 0.9306 | 0.50 |

Selected: char TF-IDF, because it had the highest micro-F1 and recall on this grouped weak-label validation. These numbers measure agreement with organizer labels, not human or hidden-set accuracy.

Final char-model run on the public parquet: micro-F1 0.7982, precision 0.7018, recall 0.9254; class F1 102=0.7613, 103=0.6327, 104=0.8138, 105=0.8590, 106=0.8769. Warm local classifier latency p50/p95 was 8.28/16.52 ms per description, excluding generation and HTTP.

Latest completed automated suite: 77 tests passed, 1 warning. `compileall`, `git diff --check`, data audit, and RAG validation passed. A real local TestClient CPU sample returned categories 103 and 105; with the generator disabled, the official response contained null text/title and took 8.81 ms with zero provider calls.

## Not measured / known limitations

- `DEEPSEEK_API_KEY` was absent. Real DeepSeek generation, classification, repair, semantic verification, provider token usage, cost, and latency are unmeasured. `scripts/live_smoke.py` is gated by `ENABLE_LIVE_API_TESTS=true` and a present key.
- RAG generation variants G0–G3 and retrieval relevance are unmeasured because there is no human-approved corpus and no human-labeled query set. `python scripts/evaluate_rag.py` must continue to say `NOT_MEASURED` until those inputs exist.
- The public parquet is not an independent blind test and lacks source `mcId`.
- The weak train labels contain duplicates and possible annotation errors. Near-duplicate split still has residual similarity >=0.90 examples.
- Docker image smoke was not run because Docker daemon was not available on the original computer.
- Deterministic evidence matching is deliberately conservative and incomplete; supported services outside its patterns can be missed. LLM verification is advisory, not proof.

## Recommended next phase on a stronger computer

Preserve the existing working baseline and compare controlled variants. Do not just increase model size or train longer.

1. **Recreate and record environment.** Pull the branch, build a fresh Python environment from pinned requirements, check CPU/GPU visibility, record GPU model/VRAM, driver/runtime, CPU, RAM, Python and package versions. The current sklearn pipeline is CPU-only; GPU matters for transformer/embedding experiments, not this TF-IDF baseline.
2. **Audit data before training.** Re-run `scripts/audit_data.py` and `scripts/audit_near_duplicates.py`. Add label-combination counts, duplicate group samples, empty/short/outlier descriptions, and conflicting near-duplicate labels. Inspect representative examples manually. Do not drop near duplicates blindly: some repeated texts can have different multi-labels or source context.
3. **Protect evaluation.** Split by connected components of near duplicates. Use several fixed seeds for development comparisons, and reserve a new untouched manually checked set for final evaluation. Never tune thresholds or prompts against the public parquet after it has been inspected.
4. **Compare label/data policies.** At minimum: current deduplicated baseline; exact-dedup with majority/union conflict handling; near-duplicate cluster-aware sampling; short/noisy text filtering; class-balanced and label-quality-filtered samples. Report retained rows, class/multilabel distribution, conflict rate, micro/macro/per-class F1, precision/recall, confidence calibration, and confusion examples.
5. **Compare model families.** Keep the current char TF-IDF baseline; test word+char, calibrated logistic models, and one or more Russian-capable pretrained embedding/transformer classifiers if GPU is usable. Use the same group splits, report training and inference latency, VRAM/RAM, artifact size, and resource requirements. Do not assume GPU training improves quality.
6. **Improve evidence and generation.** Build a fresh human-reviewed sample for category extraction and a blinded copy review set. Compare the current deterministic evidence, DeepSeek classifier, and hybrid mode. Measure unsupported-claim rate, category correctness, useful-fact retention, null rate, latency, tokens, and real USD cost. Only then decide whether semantic review or RAG earns its additional call/complexity.
7. **Curate RAG honestly.** Have a person approve each example and its provenance. Keep source facts separate from approved style text. Add human-labeled relevance queries and test category isolation, near-duplicate filtering, fact leakage, and G0/G1/G2/G3 generation under blind evaluation.
8. **Re-run integration checks.** `pytest -q`, `python scripts/train_cpu.py`, `python scripts/evaluate_cpu.py`, `python scripts/evaluate_public_test.py`, `python scripts/validate_rag.py`, `python scripts/evaluate_rag.py`, then a small gated live test with budget limits. Build and smoke-test Docker if the daemon is available.

## Useful commands

```powershell
cd ai-service
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python scripts/audit_data.py
python scripts/train_cpu.py
python -m pytest -q
python scripts/evaluate_cpu.py
python scripts/evaluate_public_test.py
python scripts/validate_rag.py
python scripts/evaluate_rag.py
uvicorn app.main:app --host 127.0.0.1 --port 8001
```

For an offline classifier-only demo, set `GENERATOR_PROVIDER=disabled`. For a real provider check, set the API key only in the local environment, deliberately set `ENABLE_LIVE_API_TESTS=true`, and run `python scripts/live_smoke.py`.
