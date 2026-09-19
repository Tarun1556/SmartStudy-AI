from typing import List, Tuple, Optional
import re
import os


def chunk_text(text: str, chunk_size: int = 800, overlap: int = 150) -> List[str]:
    if not text:
        return []

    text = re.sub(r'\s+', ' ', text).strip()
    if len(text) <= chunk_size:
        return [text]

    sentences = re.split(r'(?<=[.!?])\s+', text)
    chunks = []
    current = ""
    buffer = ""

    for s in sentences:
        s = s.strip()
        if not s:
            continue
        candidate = (current + " " + s).strip() if current else s
        if len(candidate) <= chunk_size:
            current = candidate
        else:
            if current:
                chunks.append(current)
            overlap_text = current[-overlap:] if len(current) > overlap else current
            current = (overlap_text + " " + s).strip() if overlap_text else s

    if current:
        chunks.append(current)

    if not chunks:
        chunks = [text[i:i + chunk_size] for i in range(0, len(text), chunk_size - overlap)]

    return chunks


def chunk_by_segments(segments: List[dict], max_chars_per_chunk: int = 1200) -> List[Tuple[str, Optional[float], Optional[float]]]:
    chunks = []
    current_text = ""
    current_start = None
    current_end = None
    current_chars = 0

    for seg in segments:
        text = seg.get("text", "")
        start = seg.get("start_time")
        end = seg.get("end_time")
        if not text:
            continue
        text = text.strip()
        tlen = len(text)

        if current_chars + tlen + 1 > max_chars_per_chunk and current_text:
            chunks.append((current_text.strip(), current_start, current_end))
            overlap_len = min(200, len(current_text))
            current_text = current_text[-overlap_len:] + " " + text
            current_start = start
            current_end = end
            current_chars = len(current_text)
        else:
            if not current_text:
                current_start = start
            current_text = (current_text + " " + text).strip() if current_text else text
            current_end = end
            current_chars = len(current_text)

    if current_text:
        chunks.append((current_text.strip(), current_start, current_end))

    return chunks


def split_long_document(text: str, max_chars_per_call: int = 6000) -> List[str]:
    if len(text) <= max_chars_per_call:
        return [text]

    parts = []
    start = 0
    n = len(text)
    while start < n:
        end = min(start + max_chars_per_call, n)
        if end < n:
            cut = text.rfind("\n", start, end)
            if cut == -1:
                cut = text.rfind(". ", start, end)
            if cut == -1:
                cut = end
            end = cut + 1
        parts.append(text[start:end].strip())
        if end <= start:
            break
        start = max(end - 500, start + 1)

    return [p for p in parts if p]
