from __future__ import annotations

import argparse
import sys
import warnings
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import numpy as np
from sklearn.exceptions import ConvergenceWarning
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from ..services import config
from ..services.categories import DOC_TYPE_UNSTRUCTURED, normalize_doc_type
from ..services.parsers import (
    parse_csv_bytes,
    parse_docx_bytes,
    parse_pdf_bytes,
    parse_txt_bytes,
    parse_xlsx_bytes,
)
from ..services.embeddings import embed


SUPPORTED_EXT = {ext.lower() for ext in config.ALLOWED_EXT}


def _parse_file(path: Path) -> str:
    data = path.read_bytes()
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return parse_pdf_bytes(data)
    if suffix == ".docx":
        return parse_docx_bytes(data)
    if suffix == ".xlsx":
        return parse_xlsx_bytes(data)
    if suffix == ".csv":
        return parse_csv_bytes(data)
    if suffix in {".txt", ".md"}:
        return parse_txt_bytes(data)
    raise ValueError(f"Unsupported extension: {suffix}")


def _prepare_text(text: str, max_words: int) -> str:
    words = text.split()
    if len(words) <= max_words:
        return text
    return " ".join(words[:max_words])


def _detect_doc_type(base: Path, path: Path) -> str:
    try:
        rel_parts = path.relative_to(base).parts
    except ValueError:
        rel_parts = path.parts
    doc_type = None
    if len(rel_parts) >= 2:
        doc_type = normalize_doc_type(rel_parts[0])
    if not doc_type:
        doc_type = DOC_TYPE_UNSTRUCTURED
    return doc_type


def _gather_examples(
    docs_dir: Path,
    max_docs_per_type: Optional[int],
    max_words: int,
) -> Tuple[List[List[float]], List[str]]:
    vectors: List[List[float]] = []
    labels: List[str] = []
    counts: Dict[str, int] = defaultdict(int)

    files: Iterable[Path] = docs_dir.rglob("*")
    for file_path in files:
        if not file_path.is_file():
            continue
        if file_path.suffix.lower() not in SUPPORTED_EXT:
            continue
        doc_type = _detect_doc_type(docs_dir, file_path)
        if max_docs_per_type is not None and counts[doc_type] >= max_docs_per_type:
            continue
        try:
            text = _parse_file(file_path)
        except Exception as exc:  # pragma: no cover - defensive logging
            print(f"[skip] {file_path}: {exc}", file=sys.stderr)
            continue
        text = (text or "").strip()
        if not text:
            continue
        snippet = _prepare_text(text, max_words)
        vector = embed(snippet)
        vectors.append(vector)
        labels.append(doc_type)
        counts[doc_type] += 1
    return vectors, labels


def train_classifier(
    docs_dir: Path,
    output: Path,
    max_docs_per_type: Optional[int],
    max_words: int,
    test_size: float,
    random_seed: int,
) -> None:
    vectors, labels = _gather_examples(docs_dir, max_docs_per_type, max_words)
    if not vectors:
        raise RuntimeError("Нет данных для обучения классификатора (vectors empty)")

    unique_labels = sorted(set(labels))
    if len(unique_labels) < 2:
        raise RuntimeError(
            "Для обучения нужно минимум две категории, сейчас доступна(ы): "
            + ", ".join(unique_labels)
        )

    X = np.array(vectors, dtype=np.float32)
    y = np.array(labels)

    counter = Counter(y)
    print("Примеры по категориям:")
    for label in sorted(counter):
        print(f"  {label}: {counter[label]}")

    stratify = y if min(counter.values()) >= 2 else None
    if test_size > 0 and len(y) > 1:
        X_train, X_test, y_train, y_test = train_test_split(
            X,
            y,
            test_size=test_size,
            random_state=random_seed,
            stratify=stratify,
        )
    else:
        X_train, X_test, y_train, y_test = X, None, y, None

    pipeline = Pipeline(
        steps=[
            ("scaler", StandardScaler()),
            (
                "clf",
                LogisticRegression(
                    max_iter=1000,
                    multi_class="multinomial",
                    solver="saga",
                    n_jobs=-1,
                ),
            ),
        ]
    )

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=ConvergenceWarning)
        pipeline.fit(X_train, y_train)

    if X_test is not None and y_test is not None and len(X_test) > 0:
        y_pred = pipeline.predict(X_test)
        acc = accuracy_score(y_test, y_pred)
        print(f"Точность (hold-out {test_size:.0%}): {acc:.3f}")
        print(classification_report(y_test, y_pred))

    output.parent.mkdir(parents=True, exist_ok=True)
    import joblib

    joblib.dump(pipeline, output)
    print(f"Модель сохранена: {output}")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Train logistic regression classifier for document types using MiniLM embeddings.",
    )
    parser.add_argument(
        "--docs",
        type=Path,
        default=Path("docs"),
        help="Каталог с документами (подкаталоги => категории)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=config.DOC_TYPE_MODEL_PATH,
        help="Путь для сохранения классификатора (.joblib)",
    )
    parser.add_argument(
        "--max-docs-per-type",
        type=int,
        default=None,
        help="Ограничить максимум документов на категорию (для балансировки)",
    )
    parser.add_argument(
        "--max-words",
        type=int,
        default=600,
        help="Сколько слов брать из документа (чтобы ограничить длину эмбеддинга)",
    )
    parser.add_argument(
        "--test-size",
        type=float,
        default=0.2,
        help="Доля данных для hold-out оценки (0 отключает)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Seed для train_test_split",
    )
    return parser


def main() -> None:
    args = build_arg_parser().parse_args()

    docs_dir = args.docs.expanduser().resolve()
    if not docs_dir.exists():
        raise SystemExit(f"Каталог {docs_dir} не найден")

    output = args.output if isinstance(args.output, Path) else Path(args.output)
    output = output.expanduser().resolve()

    print(f"Используем документы: {docs_dir}")
    print(f"Сохраняем модель в: {output}")
    train_classifier(
        docs_dir=docs_dir,
        output=output,
        max_docs_per_type=args.max_docs_per_type,
        max_words=args.max_words,
        test_size=args.test_size,
        random_seed=args.seed,
    )


if __name__ == "__main__":
    main()
