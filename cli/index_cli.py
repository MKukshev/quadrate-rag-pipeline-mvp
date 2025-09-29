
import os, sys, uuid, pathlib
# add backend to path
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1] / "backend"))
from services.parsers import parse_pdf_bytes, parse_docx_bytes, parse_xlsx_bytes, parse_csv_bytes, parse_txt_bytes
from services.chunking import split_markdown
from services.qdrant_store import upsert_chunks, ensure_collection
from services.keyword_index import add_chunks as kw_add
from services.embeddings import get_embedder
from services.text_cleaning import clean_chunk
from services.categories import guess_doc_type
from services import config
from argparse import ArgumentParser

def parse_file(path: str) -> str:
    p = pathlib.Path(path)
    data = p.read_bytes()
    if p.suffix.lower() == ".pdf":
        return parse_pdf_bytes(data)
    if p.suffix.lower() == ".docx":
        return parse_docx_bytes(data)
    if p.suffix.lower() == ".xlsx":
        return parse_xlsx_bytes(data)
    if p.suffix.lower() == ".csv":
        return parse_csv_bytes(data)
    if p.suffix.lower() in [".txt", ".md"]:
        return parse_txt_bytes(data)
    raise ValueError(f"unsupported: {p.suffix}")

def main():
    ap = ArgumentParser(description="Batch ingest directory into vector+BM25 indices")
    ap.add_argument("--dir", required=True)
    ap.add_argument("--space", required=True)
    args = ap.parse_args()

    ensure_collection()
    get_embedder()

    total_docs, total_chunks = 0, 0
    for root, _, files in os.walk(args.dir):
        for f in files:
            if pathlib.Path(f).suffix.lower() not in config.ALLOWED_EXT:
                continue
            path = os.path.join(root, f)
            try:
                text = parse_file(path)
            except Exception as e:
                print(f"[skip] {path}: {e}")
                continue
            chunks = split_markdown(text)
            cleaned_chunks = []
            seen_chunks = set()
            for chunk in chunks:
                cleaned = clean_chunk(chunk)
                if not cleaned or len(cleaned.split()) < 5:
                    continue
                key = cleaned.lower()
                if key in seen_chunks:
                    continue
                seen_chunks.add(key)
                cleaned_chunks.append(cleaned)
            if not cleaned_chunks:
                print(f"[skip-empty] {path}")
                continue
            doc_id = f"{pathlib.Path(f).stem}_{uuid.uuid4().hex[:8]}"
            doc_path = pathlib.Path(path)
            doc_type = guess_doc_type(text, doc_path.name, doc_path)
            upsert_chunks(args.space, doc_id, doc_type, cleaned_chunks)
            kw_add(args.space, doc_id, doc_type, cleaned_chunks)
            total_docs += 1
            total_chunks += len(cleaned_chunks)
            print(f"[ok] {f}: {len(cleaned_chunks)} chunks (doc_id={doc_id}, doc_type={doc_type})")
    print(f"Done. docs={total_docs}, chunks={total_chunks}")

if __name__ == "__main__":
    main()
