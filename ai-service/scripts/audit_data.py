import hashlib
import json
import re
import statistics
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data/public-train-annotated.jsonl"
CLASS_IDS = (102, 103, 104, 105, 106)


def normalize(text):
    return re.sub(r"\s+", " ", text.lower().replace("ё", "е")).strip()


rows = [json.loads(line) for line in SOURCE.read_text(encoding="utf-8").splitlines() if line.strip()]
groups = defaultdict(list)
for row in rows:
    labels = tuple(sorted({int(x["mcId"]) for x in row.get("found_microcategories", [])}))
    groups[normalize(row.get("description", ""))].append(labels)

conflict_groups = {text: values for text, values in groups.items() if len(set(values)) > 1}
class_counts = Counter(label for row in rows for label in {int(x["mcId"]) for x in row.get("found_microcategories", [])})
combination_counts = Counter(tuple(sorted({int(x["mcId"]) for x in row.get("found_microcategories", [])})) for row in rows)
lengths = [len(row.get("description", "")) for row in rows]
normalized_bytes = SOURCE.read_bytes().replace(b"\r\n", b"\n")

report = {
    "source": SOURCE.name,
    "rows": len(rows),
    "unique_normalized_descriptions": len(groups),
    "duplicate_rows": len(rows) - len(groups),
    "conflicting_label_groups": len(conflict_groups),
    "empty_descriptions": sum(not row.get("description", "").strip() for row in rows),
    "label_counts": dict(sorted(class_counts.items())),
    "label_combination_counts": {(",".join(map(str, combo)) if combo else "none"): n for combo, n in sorted(combination_counts.items())},
    "description_chars": {
        "min": min(lengths), "median": statistics.median(lengths),
        "p95": sorted(lengths)[int(.95 * (len(lengths) - 1))], "max": max(lengths),
    },
    "sha256_lf_normalized": hashlib.sha256(normalized_bytes).hexdigest(),
    "label_source": "weak automated labels; not a human-verified gold set",
}
print(json.dumps(report, ensure_ascii=False, indent=2))
