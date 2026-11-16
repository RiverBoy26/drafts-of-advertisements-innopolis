"""Build a classification CSV from a normal CSV or the organizers' CSV export.

From ai-service (Git Bash / PowerShell):
    python scripts/make_private_submission.py --private-csv "private-test-dataset.csv" --output "result.csv"

The input file is read only; no intermediate CSV is required. The model inference
and submission format are kept the same as in the original script.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import re
import sys
from pathlib import Path

import joblib
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.main import norm, explicitly_negated
from app.transformer_classifier import ProbabilityBlend, RuBertClassifier
from advertisement_lexicon import LEX

OUTPUT = ROOT.parent / "outputs/private-test-submission-intent-context.csv"
IDS = (102, 103, 104, 105, 106)
NAMES = {
    102: "Штукатурные работы",
    103: "Плиточные работы",
    104: "Сантехнические работы",
    105: "Электромонтажные работы",
    106: "Обои и малярные работы",
}
HEADERS = ["testcase", "description"]
EXPORT_HEADER = re.compile(r"^testcase,description;+$")
CASE_START = re.compile(r'(?m)^"?(case-\d+),')


def excerpt(text, category):
    clean = re.sub(r"\s+", " ", text).strip()
    match = LEX[category].search(clean)
    if match:
        start = max(0, match.start() - 180)
        end = min(len(clean), match.end() + 420)
        part = clean[start:end]
        if start:
            part = "…" + part
        if end < len(clean):
            part += "…"
    else:
        part = clean[:600] + ("…" if len(clean) > 600 else "")
    return NAMES[category] + ". " + part


def _read_organizers_export(text: str) -> tuple[list[list[str]], int]:
    """Recover rows from the observed nested semicolon spreadsheet export.

    Physical lines have extra trailing semicolons, and some record-level quotes
    in the original export are unbalanced. Record boundaries are recognized by
    testcase IDs rather than relying on CSV quoting across the entire file.
    """
    matches = list(CASE_START.finditer(text))
    if not matches:
        raise ValueError(
            "Не найдены строки case-001, case-002 и т.д. "
            "Формат входного файла отличается от проверенного экспорта."
        )

    rows = []
    recovered = 0
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        block = text[match.start():end].rstrip("\r\n")
        # Additional semicolons are outer, empty columns introduced by export.
        inner_csv = "\n".join(
            re.sub(r";{2,}$", "", line) for line in block.splitlines()
        )
        try:
            parsed = list(csv.reader(io.StringIO(inner_csv), strict=True))
        except csv.Error:
            parsed = []

        if len(parsed) == 1 and len(parsed[0]) == 2 and parsed[0][0] == match.group(1):
            description = parsed[0][1]
        else:
            # Some records of the supplied organizer export have unmatched
            # quotes. Keep all text between consecutive 'case-NNN' boundaries.
            recovered += 1
            first, description = inner_csv.split(",", 1)
            if first.startswith('"'):
                if not description.startswith('""'):
                    raise ValueError(
                        f"Нестандартное экранирование у {match.group(1)}; "
                        "проверьте входной формат, оригинал не изменён."
                    )
                description = description[2:]
                if description.endswith('"""'):
                    description = description[:-3]
                elif description.endswith('"'):
                    description = description[:-1]
                description = re.sub(r'"(?=\n)|(?<=\n)"', "", description)
                description = description.replace('""', '"')

        # Spreadsheet export can also insert a quote immediately before or
        # after a semicolon inside the description. These are *export* quotes,
        # not part of the advertisement. Decode doubled quotes uniformly.
        description = description.replace('""', '"').replace('";"', ';')
        description = re.sub(r'";(?=\s|$)', ';', description)
        description = re.sub(r';"(?=\s|$)', ';', description)
        description = re.sub(r'\.;$', '.', description)
        rows.append([match.group(1), description])
    return rows, recovered


def read_input_csv(path: Path) -> pd.DataFrame:
    """Accept standard 2-column CSV or the exact kind of export provided by organizers."""
    if not path.is_file():
        raise FileNotFoundError(f"Не найден входной CSV: {path}")

    text = path.read_text(encoding="utf-8-sig")
    first_line = text.splitlines()[0].strip() if text.splitlines() else ""
    if EXPORT_HEADER.fullmatch(first_line):
        # In this export, the comma-separated CSV lives inside the first
        # semicolon-delimited column. Parse it without saving an intermediate file.
        rows, recovered = _read_organizers_export(text)
        data = pd.DataFrame(rows, columns=HEADERS, dtype=str)
    else:
        try:
            data = pd.read_csv(path, dtype=str, keep_default_na=False, encoding="utf-8-sig")
        except pd.errors.ParserError as exc:
            raise ValueError(
                "Не удалось прочитать CSV. Ожидается обычный файл с колонками "
                "testcase,description либо экспорт организаторов, начинающийся "
                "с testcase,description;;;;;. "
                f"Исходная ошибка: {exc}"
            ) from exc
        if list(data.columns) != HEADERS:
            raise ValueError(
                f"Неправильные столбцы: {data.columns.tolist()}. "
                "Ожидаются testcase,description в этом порядке."
            )
        print(f"Распознан обычный CSV: {len(data)} объявлений.", flush=True)

    if data.empty:
        raise ValueError("Во входном файле нет объявлений.")
    if (data["testcase"].str.strip() == "").any():
        raise ValueError("Есть пустые testcase; исходный файл не изменён.")
    if (data["description"].str.strip() == "").any():
        raise ValueError("Есть пустые description; исходный файл не изменён.")
    if not data["testcase"].is_unique:
        duplicates = data.loc[data["testcase"].duplicated(), "testcase"].tolist()[:5]
        raise ValueError(f"Повторяющиеся testcase: {duplicates}")
    return data


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--private-csv", type=Path, required=True,
        help="Путь к CSV организаторов (исходный файл не изменяется)",
    )
    parser.add_argument(
        "--output", type=Path, default=None,
        help="Путь к выходному CSV для бота",
    )
    parser.add_argument(
        "--adaptive", action="store_true",
        help="Адаптивная смесь: 55 процентов RuBERT для коротких, 45 для длинных",
    )
    parser.add_argument(
        "--scope", action="store_true",
        help="Использовать отдельно обученный offer-scope вариант",
    )
    parser.add_argument("--short-threshold", type=float, default=.525)
    args = parser.parse_args()

    # The only substantive change: parse both original CSV representations.
    data = read_input_csv(args.private_csv)

    variant = "intent_scope" if args.scope else "intent_context"
    cpu = joblib.load(ROOT / f"artifacts/cpu_char_{variant}.joblib")["model"]
    bert = RuBertClassifier(str(ROOT / f"artifacts/rubert_{variant}"))
    texts = [norm(x) for x in data.description]

    if args.adaptive:
        import numpy as np
        cpu_scores = cpu.predict_proba(texts)
        bert_scores = bert.predict_proba(texts)
        token_lengths = [
            len(ids) for ids in bert.tokenizer(
                texts, add_special_tokens=True, truncation=False
            )["input_ids"]
        ]
        weights = np.asarray([.55 if n <= 512 else .45 for n in token_lengths])[:, None]
        scores = (1 - weights) * cpu_scores + weights * bert_scores
        if args.scope:
            output = ROOT.parent / "outputs/private-test-submission-scope-adaptive.csv"
        elif args.short_threshold != .525:
            output = ROOT.parent / (
                f"outputs/private-test-submission-adaptive-short-{int(args.short_threshold * 1000):03d}.csv"
            )
        else:
            output = ROOT.parent / "outputs/private-test-submission-adaptive.csv"
    else:
        scores = ProbabilityBlend((cpu, bert), (.55, .45)).predict_proba(texts)
        output = ROOT.parent / (
            "outputs/private-test-submission-scope.csv" if args.scope
            else "outputs/private-test-submission-intent-context.csv"
        )

    if args.output is not None:
        output = args.output
    if output.resolve() == args.private_csv.resolve():
        parser.error("--output не должен совпадать с исходным CSV")

    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["testcase", "microcats", "descriptions"])
        writer.writeheader()
        for i, (case, source, text, row) in enumerate(
            zip(data.testcase, data.description, texts, scores)
        ):
            threshold = args.short_threshold if args.adaptive and token_lengths[i] <= 512 else .525
            cats = [
                c for c, s in zip(IDS, row)
                if s >= threshold and not explicitly_negated(text, c)
            ]
            writer.writerow({
                "testcase": case,
                "microcats": json.dumps(cats, ensure_ascii=False),
                "descriptions": json.dumps(
                    [excerpt(source, c) for c in cats], ensure_ascii=False
                ),
            })

    with output.open("r", encoding="utf-8-sig", newline="") as f:
        saved = list(csv.DictReader(f))
    assert len(saved) == len(data)
    for case, row in zip(data.testcase, saved):
        assert row["testcase"] == case
        cats = json.loads(row["microcats"])
        descs = json.loads(row["descriptions"])
        assert len(cats) == len(descs) and len(cats) == len(set(cats))
        assert all(c in IDS for c in cats)
        assert all(isinstance(x, str) and x for x in descs)
    print(json.dumps({
        "file": str(output),
        "rows": len(saved),
        "bytes": output.stat().st_size,
        "empty": sum(not json.loads(r["microcats"]) for r in saved),
        "category_assignments": sum(len(json.loads(r["microcats"])) for r in saved),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
