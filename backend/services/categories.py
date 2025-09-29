from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, Iterable, List, Optional

try:
    import joblib
except ImportError:  # pragma: no cover
    joblib = None

from . import config
from .embeddings import embed

DocType = str

DOC_TYPE_EMAIL = "email_correspondence"
DOC_TYPE_MESSENGER = "messenger_correspondence"
DOC_TYPE_PRESENTATION = "presentations"
DOC_TYPE_PROTOCOL = "protocols"
DOC_TYPE_TECHNICAL = "technical_docs"
DOC_TYPE_WORK_PLAN = "work_plans"
DOC_TYPE_UNSTRUCTURED = "unstructured"

ALL_DOC_TYPES: List[DocType] = [
    DOC_TYPE_EMAIL,
    DOC_TYPE_MESSENGER,
    DOC_TYPE_PRESENTATION,
    DOC_TYPE_PROTOCOL,
    DOC_TYPE_TECHNICAL,
    DOC_TYPE_WORK_PLAN,
    DOC_TYPE_UNSTRUCTURED,
]

_DIR_ALIAS_MAP: Dict[str, DocType] = {
    DOC_TYPE_EMAIL: DOC_TYPE_EMAIL,
    "email": DOC_TYPE_EMAIL,
    "emails": DOC_TYPE_EMAIL,
    "mail": DOC_TYPE_EMAIL,
    DOC_TYPE_MESSENGER: DOC_TYPE_MESSENGER,
    "messenger": DOC_TYPE_MESSENGER,
    "chats": DOC_TYPE_MESSENGER,
    "chat": DOC_TYPE_MESSENGER,
    DOC_TYPE_PRESENTATION: DOC_TYPE_PRESENTATION,
    "slides": DOC_TYPE_PRESENTATION,
    "presentations": DOC_TYPE_PRESENTATION,
    DOC_TYPE_PROTOCOL: DOC_TYPE_PROTOCOL,
    "minutes": DOC_TYPE_PROTOCOL,
    DOC_TYPE_TECHNICAL: DOC_TYPE_TECHNICAL,
    "tech": DOC_TYPE_TECHNICAL,
    "specs": DOC_TYPE_TECHNICAL,
    "specifications": DOC_TYPE_TECHNICAL,
    DOC_TYPE_WORK_PLAN: DOC_TYPE_WORK_PLAN,
    "plans": DOC_TYPE_WORK_PLAN,
    "roadmaps": DOC_TYPE_WORK_PLAN,
}

_FILENAME_HINTS: Dict[DocType, Iterable[str]] = {
    DOC_TYPE_EMAIL: ("mail", "email", "inbox", "outbox"),
    DOC_TYPE_MESSENGER: ("chat", "messenger", "im", "telegram", "slack"),
    DOC_TYPE_PRESENTATION: ("presentation", "slides", "deck"),
    DOC_TYPE_PROTOCOL: ("protocol", "minutes"),
    DOC_TYPE_TECHNICAL: ("tech", "spec", "architecture", "api", "manual"),
    DOC_TYPE_WORK_PLAN: ("plan", "roadmap", "schedule"),
}

_TEXT_PATTERNS: Dict[DocType, Iterable[str]] = {
    DOC_TYPE_EMAIL: (
        r"from:\s",
        r"subject:\s",
        r"to:\s",
        r"с уважением",
    ),
    DOC_TYPE_MESSENGER: (
        r"\[\d{2}:\d{2}\]",
        r"\d{2}:\d{2}:\d{2}",
        r"telegram",
        r"slack",
        r"whatsapp",
    ),
    DOC_TYPE_PRESENTATION: (
        r"slide",
        r"agenda",
        r"speaker",
    ),
    DOC_TYPE_PROTOCOL: (
        r"повестка",
        r"протокол",
        r"решили",
        r"участники",
    ),
    DOC_TYPE_TECHNICAL: (
        r"требования",
        r"api",
        r"архитектура",
        r"диаграмма",
        r"implementation",
        r"конфигурац",
    ),
    DOC_TYPE_WORK_PLAN: (
        r"план",
        r"дедлайн",
        r"вех",
        r"milestone",
        r"спринт",
        r"roadmap",
    ),
}

_value_to_type: Dict[str, DocType] = {
    **{dt: dt for dt in ALL_DOC_TYPES},
    **_DIR_ALIAS_MAP,
}

_keywords: Dict[DocType, Iterable[str]] = {
    DOC_TYPE_EMAIL: (
        "email",
        "e-mail",
        "почта",
        "email-переписк",
        "почтов",
    ),
    DOC_TYPE_MESSENGER: (
        "messenger",
        "переписк",
        "чат",
        "telegram",
        "whatsapp",
        "slack",
    ),
    DOC_TYPE_PRESENTATION: (
        "презентац",
        "slides",
        "deck",
        "slide",
    ),
    DOC_TYPE_PROTOCOL: (
        "протокол",
        "minutes",
        "совещан",
        "комитет",
    ),
    DOC_TYPE_TECHNICAL: (
        "технич",
        "spec",
        "api",
        "архитект",
        "документаци",
    ),
    DOC_TYPE_WORK_PLAN: (
        "план",
        "roadmap",
        "расписан",
        "milestone",
        "дорожн",
    ),
}

_classifier = None


def _load_classifier():
    global _classifier
    if _classifier is not None:
        return _classifier
    model_path = config.DOC_TYPE_MODEL_PATH
    if not model_path or joblib is None:
        _classifier = None
        return _classifier
    try:
        path = Path(model_path)
        if not path.exists():
            raise FileNotFoundError
        pipeline = joblib.load(path)
    except Exception:
        pipeline = None
    _classifier = pipeline
    return _classifier


def _predict_with_classifier(text: str) -> Optional[DocType]:
    classifier = _load_classifier()
    if classifier is None:
        return None
    text = (text or "").strip()
    if not text:
        return None
    try:
        # ожидание, что классификатор принимает эмбеддинги MiniLM
        vec = embed(text)
        pred = classifier.predict([vec])[0]
        if pred in ALL_DOC_TYPES:
            return pred
    except Exception:
        return None
    return None


def doc_type_from_path(path: Path) -> Optional[DocType]:
    for part in path.parents:
        candidate = part.name.lower()
        if candidate in _DIR_ALIAS_MAP:
            return _DIR_ALIAS_MAP[candidate]
    candidate = path.parent.name.lower()
    return _DIR_ALIAS_MAP.get(candidate)


def normalize_doc_type(value: Optional[str]) -> Optional[DocType]:
    if not value:
        return None
    val = value.strip().lower()
    return _value_to_type.get(val)


def extract_doc_types_from_text(text: Optional[str]) -> List[DocType]:
    if not text:
        return []
    lowered = text.lower()
    matches: List[DocType] = []
    for doc_type, hints in _keywords.items():
        if any(hint in lowered for hint in hints):
            matches.append(doc_type)
    return matches


def _guess_by_filename(name: str) -> Optional[DocType]:
    lname = name.lower()
    for doc_type, hints in _FILENAME_HINTS.items():
        if any(hint in lname for hint in hints):
            return doc_type
    suffix = Path(name).suffix.lower()
    if suffix in {".ppt", ".pptx", ".key"}:
        return DOC_TYPE_PRESENTATION
    if suffix in {".xls", ".xlsx"}:
        return DOC_TYPE_WORK_PLAN
    if suffix in {".md", ".rst"}:
        return DOC_TYPE_TECHNICAL
    return None


def _guess_by_content(text: str) -> Optional[DocType]:
    snippet = (text or "")[:4000].lower()
    for doc_type, patterns in _TEXT_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, snippet, flags=re.IGNORECASE):
                return doc_type
    return None


def guess_doc_type(text: str, filename: str, path: Optional[Path] = None) -> DocType:
    candidate = None
    if path is not None:
        candidate = doc_type_from_path(path)
        if candidate:
            return candidate
    candidate = _guess_by_filename(filename)
    if candidate:
        return candidate
    candidate = _guess_by_content(text)
    if candidate:
        return candidate
    candidate = _predict_with_classifier(text)
    if candidate:
        return candidate
    return DOC_TYPE_UNSTRUCTURED
