"""Create a conservative, auditable training copy from weak labels and manual adjudications."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import zipfile
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from scipy.sparse.csgraph import connected_components
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.neighbors import NearestNeighbors

from benchmark_user_updated_cpu import IDS, ROOT, norm


WORKBOOK = ROOT / "data/source_manual/Дай Бог.xlsx"
CSV_FILE = ROOT / "data/source_manual/new_general_ads_25.csv"

# Each selected cluster was checked against the actual service wording. Only
# random IDs, seller names, or metadata vary inside these clusters. Other
# conflict clusters contain materially different job scope and retain their
# original labels.
CLUSTER_DECISIONS = {
    0:  ((102, 103, 104, 105, 106), "Identical full-service offer; one row omitted plumbing despite explicit plumbing list."),
    6:  ((102, 103, 104, 105, 106), "Same full-service offer; omitted plumbing label is contradicted by the explicit utilities list."),
    138:((102, 103, 104, 105, 106), "Same five-trade offer; five name/ID variants omitted the explicitly listed plumbing service."),
    152:((102, 103, 104, 105, 106), "Same full-cycle offer; varying seller names/IDs do not change the explicit five-trade scope."),
    293:((102, 103, 104, 105, 106), "The same active full-renovation description lists electrical work; the minority row omitted 105."),
    406:((104, 105), "Same full-renovation offer; engineering communication work and electricians/plumbers are explicitly offered."),
    541:((106,), "Same finishing-work description; two ID-only variants omitted the explicit painting/wallpaper trade."),
    562:((105, 106), "Same offer explicitly lists electrical and painting/finishing; one row omitted 106."),
    631:((102, 103, 104, 105, 106), "Same active broad renovation description; all five trades are listed, including tile."),
    670:((102, 103, 104, 105, 106), "Both repair types list plaster, tile, plumbing, electrical, and finishing work."),
    874:((104, 105), "Same full-cycle offer; explicitly names electricians and plumbers and says the company starts implementation."),
    1897:((102, 104, 105), "The same active renovation offer explicitly lists plaster, electrical, and plumbing; one row omitted plaster."),
    2318:((102, 103, 106), "Same description explicitly offers plaster, tile, and finishing; one ID-only variant omitted plaster and tile."),
}


def workbook_rows(path: Path) -> list[dict]:
    ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    with zipfile.ZipFile(path) as archive:
        shared: list[str] = []
        if "xl/sharedStrings.xml" in archive.namelist():
            root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
            shared = ["".join(t.text or "" for t in si.findall(".//m:t", ns)) for si in root.findall("m:si", ns)]
        root = ET.fromstring(archive.read("xl/worksheets/sheet1.xml"))
    result = []
    for row in root.findall(".//m:sheetData/m:row", ns):
        cells = {}
        for cell in row.findall("m:c", ns):
            col = re.sub(r"\d", "", cell.attrib["r"])
            value = cell.find("m:v", ns)
            inline = cell.find("m:is", ns)
            if value is not None and cell.attrib.get("t") == "s":
                cells[col] = shared[int(value.text)]
            elif value is not None:
                cells[col] = value.text or ""
            elif inline is not None:
                cells[col] = "".join(t.text or "" for t in inline.findall(".//m:t", ns))
            else:
                cells[col] = ""
        if cells.get("A", "").strip():
            labels = sorted({int(x) for x in re.findall(r"\d+", cells.get("B", ""))})
            result.append({"source": "Дай Бог.xlsx", "id": int(row.attrib["r"]),
                           "description": cells["A"].strip(), "labels": labels})
    return result


def parse_added_csv(path: Path) -> list[dict]:
    lines = path.read_text(encoding="utf-8-sig").splitlines()
    result = []
    for line_no, line in enumerate(lines[1:], 1):
        # The source has a quoted CSV record followed by a semicolon and, for
        # some rows, an unescaped quoted continuation. Join both into the ad.
        first, separator, continuation = line.partition(";")
        outer = next(csv.reader([first]))
        if len(outer) != 1:
            raise ValueError(f"CSV row {line_no}: expected one wrapped record, got {len(outer)} fields")
        fields = next(csv.reader([outer[0]]))
        if len(fields) != 3:
            raise ValueError(f"CSV row {line_no}: expected 3 inner fields, got {len(fields)}")
        labels = sorted({int(x) for x in re.findall(r"\d+", fields[1])})
        description = fields[2].strip().rstrip('"').strip()
        tail = ""
        if separator and continuation.strip().strip('"').strip():
            fragment = continuation.strip()
            try:
                decoded = next(csv.reader([fragment]))
                tail = decoded[0] if decoded else ""
            except (csv.Error, IndexError):
                tail = fragment.strip('"')
            tail = tail.rstrip('"').strip()
        if tail:
            description += "; " + tail
        result.append({"source": "new_general_ads_25.csv", "id": fields[0].strip(),
                       "description": description, "labels": labels,
                       "joined_continuation": bool(tail)})
    return result


def label_objects(labels) -> list[dict]:
    return [{"mcId": int(c)} for c in sorted(set(labels))]


def main(workbook_path: Path = WORKBOOK, csv_path: Path = CSV_FILE) -> None:
    for path in (workbook_path, csv_path):
        if not path.exists():
            raise FileNotFoundError(path)
    parsed_csv = parse_added_csv(csv_path)
    manual_raw = workbook_rows(workbook_path) + parsed_csv
    allowed = set(IDS)
    for row in manual_raw:
        if not set(row["labels"]).issubset(allowed):
            raise ValueError(f"Unexpected class IDs in {row['source']}:{row['id']}: {row['labels']}")

    # De-duplicate manual entries by normalized text; retain the first source
    # reference and fail if duplicate annotations disagree.
    manual_unique: dict[str, dict] = {}
    manual_audit = []
    for row in manual_raw:
        key = norm(row["description"])
        previous = manual_unique.get(key)
        if previous and previous["labels"] != row["labels"]:
            raise ValueError(f"Conflicting duplicate manual labels: {previous} vs {row}")
        duplicate = previous is not None
        if not duplicate:
            manual_unique[key] = row
        manual_audit.append({**row, "decision": "confirmed_by_text_context",
                             "duplicate_of": (previous["source"], previous["id"]) if duplicate else None,
                             "review_rule": "Count work currently offered by this advertiser; exclude past work, portfolio-only mentions, other providers, project/material-only services, and explicitly declined work."})

    raw = [json.loads(s) for s in (ROOT / "data/user-updated-train.jsonl").read_text(encoding="utf-8").splitlines() if s.strip()]
    dedup: dict[str, dict] = {}
    for record in raw:
        dedup.setdefault(norm(record["description"]), record)
    texts = list(dedup)
    y = np.asarray([[int(c in {int(v["mcId"]) for v in dedup[t].get("found_microcategories", [])}) for c in IDS]
                    for t in texts], dtype=np.uint8)
    matrix = TfidfVectorizer(analyzer="char", ngram_range=(3, 5), min_df=2,
                             max_features=100000, sublinear_tf=True).fit_transform(texts)
    graph = NearestNeighbors(radius=.05, metric="cosine", algorithm="brute", n_jobs=-1).fit(matrix).radius_neighbors_graph(matrix, mode="connectivity")
    n_components, components = connected_components(graph, directed=False)
    found_ids = set(map(int, components))
    if not set(CLUSTER_DECISIONS).issubset(found_ids):
        raise ValueError(f"Expected conflict groups missing: {sorted(set(CLUSTER_DECISIONS) - found_ids)}")

    group_members: dict[int, list[int]] = defaultdict(list)
    for index, group in enumerate(components):
        group_members[int(group)].append(index)
    updated_records = []
    changed_by_group = {}
    for index, text in enumerate(texts):
        record = dict(dedup[text])
        original = tuple(sorted(int(x["mcId"]) for x in record.get("found_microcategories", [])))
        group = int(components[index])
        if group in CLUSTER_DECISIONS:
            corrected, _ = CLUSTER_DECISIONS[group]
            record["found_microcategories"] = label_objects(corrected)
            if original != tuple(corrected):
                changed_by_group[group] = changed_by_group.get(group, 0) + 1
        updated_records.append(record)

    manual_records = [{"description": row["description"], "found_microcategories": label_objects(row["labels"])}
                      for row in manual_unique.values()]
    # The supplied texts are additions; exact overlap with existing weak data
    # would otherwise leak the new annotation into evaluation/training twice.
    overlap = {norm(r["description"]) for r in manual_records} & set(dedup)
    if overlap:
        raise ValueError(f"Manual records overlap existing source text: {len(overlap)}")
    merged = updated_records + manual_records

    data_dir = ROOT / "data"
    work_dir = ROOT / "work"
    data_dir.mkdir(exist_ok=True)
    work_dir.mkdir(exist_ok=True)
    base_out = data_dir / "user-updated-train-conflict-resolved-base.jsonl"
    manual_out = data_dir / "manual-conflict-resolved-additions.jsonl"
    merged_out = data_dir / "user-updated-train-conflict-resolved.jsonl"
    for path, records in ((base_out, updated_records), (manual_out, manual_records), (merged_out, merged)):
        path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records), encoding="utf-8")

    decisions = []
    for group, (labels, reason) in CLUSTER_DECISIONS.items():
        members = group_members[group]
        before = Counter(tuple(c for c, value in zip(IDS, y[i]) if value) for i in members)
        decisions.append({"group_id": group, "size": len(members), "labels_before": {";".join(map(str, k)): v for k, v in before.items()},
                          "labels_after": list(labels), "corrected_unique_texts": changed_by_group.get(group, 0), "reason": reason})

    audit = {
        "source_train_sha256": hashlib.sha256((ROOT / "data/user-updated-train.jsonl").read_bytes()).hexdigest(),
        "workbook_sha256": hashlib.sha256(workbook_path.read_bytes()).hexdigest(),
        "added_csv_sha256": hashlib.sha256(csv_path.read_bytes()).hexdigest(),
        "raw_source_rows": len(raw), "unique_source_texts": len(texts),
        "removed_exact_duplicate_source_rows": len(raw) - len(texts),
        "conflict_groups_found": int(n_components), "groups_adjudicated": decisions,
        "changed_weak_label_texts": sum(changed_by_group.values()),
        "manual_rows_reviewed": len(manual_raw), "manual_unique_texts": len(manual_unique),
        "manual_duplicates_removed": len(manual_raw) - len(manual_unique),
        "csv_rows_with_joined_context": sum(bool(r.get("joined_continuation")) for r in parsed_csv),
        "manual_adjudications": manual_audit,
        "outputs": {"base": str(base_out), "manual": str(manual_out), "merged": str(merged_out)},
        "retained_conflict_groups": [201, 240, 491, 942, 2812],
        "retained_conflict_rationale": "These groups differ in active work scope, service list, or presence of specific trade terms, so a majority label would erase real distinctions."
    }
    (work_dir / "conflict_resolved_data_audit.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    summary = {k: audit[k] for k in ("raw_source_rows", "unique_source_texts", "removed_exact_duplicate_source_rows",
                                     "changed_weak_label_texts", "manual_rows_reviewed", "manual_unique_texts",
                                     "manual_duplicates_removed", "csv_rows_with_joined_context", "outputs")}
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--workbook", type=Path, default=WORKBOOK)
    parser.add_argument("--added-csv", type=Path, default=CSV_FILE)
    args = parser.parse_args()
    main(args.workbook, args.added_csv)
