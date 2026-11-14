"""Run the local classifier and generate two Avito drafts directly with DeepSeek.

No backend or frontend server is started. Set DEEPSEEK_API_KEY in the environment
or in ai-service/.env before running this script. Results are written under work/.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.main import (  # noqa: E402
    ACTIVE_BACKEND,
    NAMES,
    deepseek,
    evidence,
    predict,
    rag,
    valid_text,
)


def pick_examples(limit: int) -> list[dict]:
    dataset = ROOT / "data" / "public-train-annotated.jsonl"
    chosen: list[dict] = []
    seen_targets: set[tuple[int, ...]] = set()
    for line in dataset.open(encoding="utf-8"):
        row = json.loads(line)
        description = row.get("description", "")
        if not description.strip():
            continue
        target_ids = tuple(predict(description, 101))
        if not target_ids or target_ids in seen_targets:
            continue
        facts = {mc: evidence(description, mc) for mc in target_ids}
        target_ids = tuple(mc for mc in target_ids if facts[mc])
        if not target_ids or target_ids in seen_targets:
            continue
        row["_predicted_targets"] = list(target_ids)
        chosen.append(row)
        seen_targets.add(target_ids)
        if len(chosen) >= limit:
            break
    return chosen


async def generate(row: dict) -> dict:
    description = row["description"]
    target_ids = row["_predicted_targets"]
    entries = []
    rag_examples = {}
    for mc in target_ids:
        facts = evidence(description, mc)
        examples = rag(mc, [fact["text"] for fact in facts], description)
        rag_examples[str(mc)] = [item["example_id"] for item in examples]
        entries.append({
            "mcId": mc,
            "category": NAMES[mc],
            "confirmed_services": [fact["text"] for fact in facts],
            "evidence": facts,
            "rag_examples": examples,
        })

    prompt = (ROOT / "app" / "prompts" / "generate_v1.txt").read_text(encoding="utf-8")
    answer, usage, finish = await deepseek([
        {"role": "system", "content": prompt},
        {"role": "user", "content": json.dumps(
            {"source_mcId": 101, "targets": entries}, ensure_ascii=False
        )},
    ])
    by_id = {
        item.get("mcId"): item
        for item in answer.get("drafts", [])
        if isinstance(item, dict)
    } if isinstance(answer, dict) else {}
    drafts = []
    for mc in target_ids:
        title, text = valid_text(description, by_id.get(mc, {}), mc)
        drafts.append({"mcId": mc, "category": NAMES[mc], "title": title, "text": text})
    return {
        "item_id": row.get("item_id"),
        "source_mcId": 101,
        "source_category": NAMES[101],
        "title": row.get("title"),
        "description": description,
        "classifier_backend": ACTIVE_BACKEND,
        "predicted_targets": target_ids,
        "rag_example_ids": rag_examples,
        "drafts": drafts,
        "deepseek_finish_reason": finish,
        "deepseek_usage": usage,
        "validation": "title/text null means draft failed local factual/category validation",
    }


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=2, help="Number of DeepSeek requests (default: 2)")
    parser.add_argument("--output", type=Path, default=ROOT / "work" / "live_deepseek_demo.json")
    args = parser.parse_args()
    if args.limit < 1:
        parser.error("--limit must be positive")
    if not os.getenv("DEEPSEEK_API_KEY"):
        raise SystemExit("DEEPSEEK_API_KEY is missing; set it in the environment or ai-service/.env")

    rows = pick_examples(args.limit)
    if not rows:
        raise SystemExit("No dataset rows produced both classifier predictions and textual evidence")
    results = []
    for row in rows:
        print(f"Generating for item_id={row.get('item_id')} targets={row['_predicted_targets']}", flush=True)
        results.append(await generate(row))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "status": "ok",
        "requests": len(results),
        "model": os.getenv("DEEPSEEK_MODEL", "deepseek-flash"),
        "classifier": ACTIVE_BACKEND,
        "results_file": str(args.output.resolve()),
        "results": results,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
