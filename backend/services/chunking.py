
import re
from .config import CHUNK_TOKENS, CHUNK_OVERLAP

def split_markdown(text: str, target_tokens: int = CHUNK_TOKENS, overlap: int = CHUNK_OVERLAP):
    blocks = re.split(r"\n{2,}", text.strip())
    chunks, buf, count = [], [], 0
    for b in blocks:
        sentences = re.split(r"(?<=[.!?])\s+", b)
        for s in sentences:
            t = len(s.split())
            if count + t > target_tokens and count > 0:
                chunk_text = "\n".join(buf).strip()
                if chunk_text:
                    chunks.append(chunk_text)
                if overlap > 0 and chunk_text:
                    tail = " ".join(chunk_text.split()[-overlap:])
                    buf = [tail]
                    count = len(tail.split())
                else:
                    buf, count = [], 0
            buf.append(s)
            count += t
    if buf:
        chunks.append("\n".join(buf).strip())
    return [c for c in chunks if c]
