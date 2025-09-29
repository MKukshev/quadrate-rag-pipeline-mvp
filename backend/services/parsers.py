
import io
import pandas as pd
import fitz  # PyMuPDF
from docx import Document

def _md_escape(s: str) -> str:
    return str(s).replace("|", "\\|").replace("`", "\\`")

def parse_pdf_bytes(data: bytes) -> str:
    """PDF -> Markdown: PyMuPDF (markdown/text), со стабилизацией разметки."""
    try:
        doc = fitz.open(stream=data, filetype="pdf")
        parts = []
        for page in doc:
            md = page.get_text("markdown")
            if not md:
                md = page.get_text("text")
            parts.append(md.strip())
        return "\n\n".join(parts)
    except Exception as e:
        # Фоллбек: pdfplumber (если установлен) — безопасное подключение
        try:
            import pdfplumber
            out = []
            with pdfplumber.open(io.BytesIO(data)) as pdf:
                for p in pdf.pages:
                    out.append(p.extract_text() or "")
            return "\n\n".join(out)
        except Exception:
            return "[PDF: не удалось извлечь текст — проверьте зависимости PyMuPDF/pdfplumber]"

def parse_docx_bytes(data: bytes) -> str:
    """DOCX -> Markdown: заголовки, списки, абзацы (по стилям)."""
    f = io.BytesIO(data)
    d = Document(f)
    out = []
    for p in d.paragraphs:
        txt = (p.text or "").strip()
        if not txt:
            continue
        style = (p.style.name or "").lower()
        if "heading" in style:
            # Выделяем уровень из имени стиля (Heading 1/2/3...)
            level = "".join(ch for ch in p.style.name if ch.isdigit()) or "1"
            out.append("#"*int(level) + " " + txt)
        elif p.style.name in {"List Paragraph"} or txt.startswith(("- ", "* ")):
            out.append("- " + txt.lstrip("-* ").strip())
        else:
            out.append(txt)
    return "\n\n".join(out)

def normalize_df(df: pd.DataFrame) -> pd.DataFrame:
    """Нормализация таблиц: даты -> ISO, NaN -> '', числа -> короткая форма."""
    df = df.copy()
    for c in df.columns:
        s = df[c]
        if pd.api.types.is_datetime64_any_dtype(s):
            df[c] = s.dt.strftime("%Y-%m-%d %H:%M:%S")
        elif pd.api.types.is_bool_dtype(s):
            df[c] = s.astype(str)
        elif pd.api.types.is_numeric_dtype(s):
            # не форматируем научной нотацией для больших чисел
            df[c] = s.map(lambda x: ("" if pd.isna(x) else (int(x) if float(x).is_integer() else round(float(x), 6))))
        else:
            df[c] = s.astype(str)
    df = df.fillna("")
    return df

def df_to_md(df: pd.DataFrame, sheet: str, max_rows: int = 50) -> str:
    df = normalize_df(df).head(max_rows)
    headers = "| " + " | ".join(_md_escape(c) for c in df.columns) + " |"
    sep = "| " + " | ".join("---" for _ in df.columns) + " |"
    rows = ["| " + " | ".join(_md_escape(v) for v in row) + " |" for row in df.astype(str).values]
    body = "\n".join(rows) if rows else "| |"
    return f"### Лист: {sheet}\n\n{headers}\n{sep}\n{body}\n"

def parse_xlsx_bytes(data: bytes) -> str:
    """XLSX -> Markdown-таблицы по листам (pandas/openpyxl)."""
    f = io.BytesIO(data)
    xls = pd.ExcelFile(f)
    parts = []
    for sheet in xls.sheet_names:
        try:
            df = xls.parse(sheet)
        except Exception:
            continue
        parts.append(df_to_md(df, sheet))
    return "\n\n".join(parts) if parts else "[XLSX: пустые листы]"

def parse_csv_bytes(data: bytes, encoding="utf-8") -> str:
    f = io.BytesIO(data)
    df = pd.read_csv(f, encoding=encoding)
    return df_to_md(df, sheet="CSV")

def parse_txt_bytes(data: bytes, encoding="utf-8") -> str:
    return data.decode(encoding, errors="ignore")
