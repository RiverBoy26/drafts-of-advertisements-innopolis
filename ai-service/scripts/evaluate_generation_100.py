"""Reproducible 100-case live generation and independent quality review."""
from __future__ import annotations

import asyncio
import json
import os
import random
import re
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT.parent
load_dotenv(PROJECT / ".env")
load_dotenv(ROOT / ".env")
sys.path.insert(0, str(ROOT))
os.environ.setdefault("PRICE_PROFILE", "example-deepseek-flash-2026-11-14")
os.environ.setdefault("PRICE_INPUT_CACHE_HIT_USD_PER_M", "0.003")
os.environ.setdefault("PRICE_INPUT_CACHE_MISS_USD_PER_M", "0.15")
os.environ.setdefault("PRICE_OUTPUT_USD_PER_M", "0.6")
os.environ.setdefault("MAX_REQUEST_USD", "0.05")
os.environ["CLASSIFIER_MODE"] = "evidence"
os.environ["GENERATOR_PROVIDER"] = "deepseek"
os.environ["CLAIM_VERIFIER_ENABLED"] = "true"

import app.main as service  # noqa: E402

MANIFEST = PROJECT / "docs" / "generation_known_100_manifest.json"
OUTPUT_PREFIX = os.getenv("GENERATION_EVAL_OUTPUT_PREFIX", "generation_known_100")
if not re.fullmatch(r"[a-z0-9_]+", OUTPUT_PREFIX):
    raise ValueError("GENERATION_EVAL_OUTPUT_PREFIX must contain only lowercase letters, digits, and underscores")
RESULTS = PROJECT / "docs" / f"{OUTPUT_PREFIX}_results.jsonl"
SUMMARY = PROJECT / "docs" / f"{OUTPUT_PREFIX}_summary.json"
REVIEW_PROMPT = (ROOT / "app/prompts/review_quality_v1.txt").read_text(encoding="utf8")
BINS = ("short", "medium", "long", "very_long")
SEED = 20261115
MAX_ESTIMATED_USD = 1.0
NOISE = re.compile(r"Место на складе|Номер продаваемого оборудования|Размеры оборудования на фото|Марка:\s*[a-z]-\d+|\b[a-z]-\d{4,}\b", re.I)


def length_bin(n):
    return "short" if n < 500 else "medium" if n < 1500 else "long" if n < 3000 else "very_long"


def words(text):
    return set(re.findall(r"[а-яёa-z]{3,}", text.lower().replace("ё", "е")))


def jaccard(a, b):
    return len(a & b) / max(1, len(a | b))


def build_manifest():
    if MANIFEST.exists():
        rows = json.loads(MANIFEST.read_text(encoding="utf8"))["cases"]
        if len(rows) != 100:
            raise RuntimeError("Existing manifest does not contain 100 cases")
        return rows
    candidates = {name: [] for name in BINS}
    seen = set()
    with (ROOT / "data/public-train-annotated.jsonl").open(encoding="utf8") as stream:
        for line in stream:
            row = json.loads(line)
            description = row["description"]
            n = len(description)
            if not 100 <= n <= 5000 or NOISE.search(description):
                continue
            normalized = re.sub(r"\s+", " ", description.lower().replace("ё", "е")).strip()
            if normalized in seen:
                continue
            seen.add(normalized)
            candidates[length_bin(n)].append({"itemId": row["item_id"], "sourceDescription": description,
                                               "sourceChars": n, "lengthBin": length_bin(n), "targetMcIds": sorted({v["mcId"] for v in row["found_microcategories"] if v["mcId"] != 101})})
    rng = random.Random(SEED)
    selected = []
    token_sets = []
    for name in BINS:
        rng.shuffle(candidates[name])
        for threshold in (0.65, 0.8, 1.01):
            for row in candidates[name]:
                if len([x for x in selected if x["lengthBin"] == name]) >= 25:
                    break
                if any(x["itemId"] == row["itemId"] for x in selected):
                    continue
                tokens = words(row["sourceDescription"])
                if all(jaccard(tokens, old) < threshold for old in token_sets):
                    selected.append(row)
                    token_sets.append(tokens)
            if len([x for x in selected if x["lengthBin"] == name]) >= 25:
                break
        if len([x for x in selected if x["lengthBin"] == name]) != 25:
            raise RuntimeError(f"Cannot select 25 distinct cases for {name}")
    for index, row in enumerate(selected, 1):
        row["caseNo"] = index
    MANIFEST.write_text(json.dumps({"seed": SEED, "selection": "25 per length bin; exact and token-Jaccard deduplicated; visible junk excluded; provided categories from dataset weak labels; not reclassified", "cases": selected}, ensure_ascii=False, indent=2), encoding="utf8")
    return selected


def completed():
    if not RESULTS.exists():
        return {}
    records = {}
    for line in RESULTS.read_text(encoding="utf8").splitlines():
        if line.strip():
            row = json.loads(line)
            records[row["caseNo"]] = row
    return records


def validate_review(review, drafts):
    if not isinstance(review, dict) or not isinstance(review.get("drafts"), list):
        raise ValueError("Invalid quality review schema")
    expected = {d["mcId"] for d in drafts}
    got = {d.get("mcId") for d in review["drafts"] if isinstance(d, dict)}
    if got != expected or len(review["drafts"]) != len(drafts):
        raise ValueError("Quality review missed or duplicated a draft")
    if review.get("overall") not in {"good", "acceptable", "poor"}:
        raise ValueError("Invalid overall quality")
    for row in review["drafts"]:
        if row.get("quality") not in {"good", "acceptable", "poor"} or not isinstance(row.get("issues"), list) or type(row.get("supported")) is not bool:
            raise ValueError("Invalid per-draft quality")
    if not isinstance(review.get("missed_target_mcIds"), list):
        raise ValueError("Invalid missed targets")
    return review


def update_summary(records):
    rows = list(records.values())
    generated = [r for r in rows if r.get("generationStatusCode") == 200]
    reviewed = [r for r in rows if r.get("qualityReview")]
    drafts = [d for r in reviewed for d in r["qualityReview"]["drafts"]]
    def mean(key):
        values = [r[key] for r in rows if isinstance(r.get(key), (int, float))]
        return sum(values) / len(values) if values else None
    report = {"updatedAtUtc": datetime.now(timezone.utc).isoformat(), "plannedCases": len(build_manifest()),
              "completedCases": len(rows), "generationOkCases": len(generated), "reviewedCases": len(reviewed),
              "qualityCases": dict(Counter(r["qualityReview"]["overall"] for r in reviewed)),
              "qualityDrafts": dict(Counter(d["quality"] for d in drafts)),
              "nullDrafts": sum(d.get("title") is None for r in generated for d in r["response"].get("drafts", [])),
              "totalDrafts": sum(len(r["response"].get("drafts", [])) for r in generated),
              "averageDurationMs": mean("totalDurationMs"), "averageInputTokens": mean("inputTokens"),
              "averageOutputTokens": mean("outputTokens"), "averageEstimatedCostUsd": mean("estimatedCostUsd"),
              "totalEstimatedCostUsd": sum(r.get("estimatedCostUsd") or 0 for r in rows),
              "priceProfile": os.getenv("PRICE_PROFILE"), "model": os.getenv("DEEPSEEK_MODEL", "deepseek-flash"),
              "reviewMethod": "independent DeepSeek quality rubric; automated judgment, not human ground truth"}
    SUMMARY.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf8")
    return report


def main():
    if not os.getenv("DEEPSEEK_API_KEY"):
        raise RuntimeError("DEEPSEEK_API_KEY is missing")
    cases = build_manifest()
    records = completed()
    client = TestClient(service.app)
    original_deepseek = service.deepseek
    headers_base = {"Authorization": "Bearer " + os.environ["INTERNAL_API_TOKEN"]} if os.getenv("INTERNAL_API_TOKEN") else {}
    limit = int(os.getenv("GENERATION_EVAL_LIMIT", "100"))
    newly_processed = 0
    for case in cases:
        number = case["caseNo"]
        if number in records:
            continue
        if sum(r.get("estimatedCostUsd") or 0 for r in records.values()) >= MAX_ESTIMATED_USD:
            print("Stopped at estimated budget cap", flush=True)
            break
        raw_provider_results = []
        async def traced_deepseek(messages):
            result, usage, finish = await original_deepseek(messages)
            raw_provider_results.append({"result": result, "usage": usage, "finish": finish})
            return result, usage, finish
        service.deepseek = traced_deepseek
        headers = headers_base | {"X-Request-ID": f"generation-100-{number}-{case['itemId']}"}
        started = time.perf_counter()
        try:
            response = client.post("/internal/v1/avito/drafts", headers=headers,
                                   json={"description": case["sourceDescription"], "mcId": 101, "targetMcIds": case["targetMcIds"]})
            diagnostics = client.get("/internal/v1/avito/debug/last", headers=headers).json()
            body = response.json()
            generation_status = response.status_code
        except Exception as exc:
            diagnostics = {"error": type(exc).__name__}
            body = {"error": type(exc).__name__}
            generation_status = 0
        review = None
        review_usage = None
        review_error = None
        review_duration = 0.0
        if generation_status == 200:
            review_started = time.perf_counter()
            review_input = {"source_description": case["sourceDescription"], "target_categories": [{"mcId": i, "category": service.NAMES[i]} for i in case["targetMcIds"]], "drafts": [{**d, "category": service.NAMES[d["mcId"]]} for d in body["drafts"]]}
            for attempt in range(2):
                try:
                    review, review_usage, _ = asyncio.run(original_deepseek([
                        {"role": "system", "content": REVIEW_PROMPT},
                        {"role": "user", "content": json.dumps(review_input, ensure_ascii=False)}]))
                    validate_review(review, body["drafts"])
                    review_error = None
                    break
                except Exception as exc:
                    review = None
                    review_error = type(exc).__name__
            review_duration = round((time.perf_counter() - review_started) * 1000, 2)
        generation_usage = diagnostics.get("usage") if isinstance(diagnostics, dict) else None
        row = {"caseNo": number, "itemId": case["itemId"], "lengthBin": case["lengthBin"],
               "sourceChars": case["sourceChars"], "sourceDescription": case["sourceDescription"],
               "generationStatusCode": generation_status, "response": body, "diagnostics": diagnostics,
               "rawProviderResults": raw_provider_results, "qualityReview": review,
               "qualityReviewError": review_error, "qualityReviewUsage": review_usage,
               "qualityReviewDurationMs": review_duration,
               "totalDurationMs": round((time.perf_counter() - started) * 1000, 2),
               "inputTokens": (generation_usage or {}).get("prompt_tokens", 0) + (review_usage or {}).get("prompt_tokens", 0),
               "outputTokens": (generation_usage or {}).get("completion_tokens", 0) + (review_usage or {}).get("completion_tokens", 0),
               "estimatedCostUsd": (diagnostics.get("estimatedCostUsd") or 0) + (service.estimate_cost(review_usage) or 0)}
        with RESULTS.open("a", encoding="utf8") as stream:
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")
        records[number] = row
        newly_processed += 1
        report = update_summary(records)
        print(json.dumps({"case": number, "of": 100, "status": generation_status,
                          "quality": review.get("overall") if review else None,
                          "drafts": len(body.get("drafts", [])), "estimatedTotalUsd": round(report["totalEstimatedCostUsd"], 5),
                          "reviewError": review_error}, ensure_ascii=False), flush=True)
        if newly_processed >= limit:
            break
    update_summary(records)


if __name__ == "__main__":
    main()
