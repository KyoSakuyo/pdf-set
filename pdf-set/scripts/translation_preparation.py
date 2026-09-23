"""Internal paragraph grouping and typesetting for prepare_translation."""
import re

from sentence_boundaries import safe_cuts

SUP_RE = re.compile(r"<sup>(.*?)</sup>", re.DOTALL | re.IGNORECASE)


def read_single_path(path):
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            value = line.strip()
            if value:
                return value
    return ""


def split_paragraphs(text, protect_sup=True):
    normalized = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not normalized:
        return []
    spans = []
    if protect_sup:
        spans = [(m.start(), m.end()) for m in SUP_RE.finditer(normalized)]

    parts = []
    last = 0
    for m in re.finditer(r"\n\s*\n", normalized):
        if protect_sup and is_protected(spans, m.start()):
            continue
        part = normalized[last:m.start()].strip()
        if part:
            parts.append(part)
        last = m.end()
    tail = normalized[last:].strip()
    if tail:
        parts.append(tail)
    return parts


def is_protected(spans, index):
    return any(start <= index < end for start, end in spans)


def split_paragraph(paragraph, max_chars, buffer_chars, protect_sup=True):
    if max_chars <= 0 or buffer_chars < 0:
        raise ValueError("max_chars must be positive and buffer_chars non-negative")
    cuts = safe_cuts(paragraph, protect_sup=protect_sup)
    parts = []
    start = 0
    while len(paragraph) - start > max_chars + buffer_chars:
        available = [cut for cut in cuts if start < cut < len(paragraph)]
        if not available:
            break
        end = min(available, key=lambda cut: abs(cut - start - max_chars))
        parts.append(paragraph[start:end].strip())
        start = end
    parts.append(paragraph[start:].strip())
    return [part for part in parts if part]


def split_sup_blocks(text, max_chars, buffer_chars):
    def repl(match):
        inner = match.group(1)
        inner_parts = []
        for para in split_paragraphs(inner, protect_sup=False):
            inner_parts.extend(
                split_paragraph(para, max_chars, buffer_chars, protect_sup=False)
            )
        if len(inner_parts) <= 1:
            return match.group(0)
        return "\n\n".join(f"<sup>{part}</sup>" for part in inner_parts)

    return SUP_RE.sub(repl, text)


def process_text(text, max_chars, buffer_chars):
    text = split_sup_blocks(text, max_chars, buffer_chars)
    paragraphs = split_paragraphs(text, protect_sup=True)
    output_paragraphs = []
    for para in paragraphs:
        if not para:
            continue
        output_paragraphs.extend(
            split_paragraph(para, max_chars, buffer_chars, protect_sup=True)
        )
    return "\n\n".join(output_paragraphs).rstrip() + "\n"


def pack_paragraphs(paragraphs, max_chars):
    chunks = []
    current = []
    current_len = 0
    sep_len = 2

    for para in paragraphs:
        if not para:
            continue
        para_len = len(para)

        if not current:
            current = [para]
            current_len = para_len
            if para_len > max_chars:
                chunks.append(current)
                current = []
                current_len = 0
            continue

        new_len = current_len + sep_len + para_len
        if new_len <= max_chars:
            current.append(para)
            current_len = new_len
            continue

        chunks.append(current)
        current = [para]
        current_len = para_len
        if para_len > max_chars:
            chunks.append(current)
            current = []
            current_len = 0

    if current:
        chunks.append(current)

    return chunks
