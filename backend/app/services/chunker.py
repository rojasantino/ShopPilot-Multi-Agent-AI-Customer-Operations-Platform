"""Split markdown documents into retrieval-sized chunks, keeping the section heading."""

import re


def chunk_markdown(text: str, max_chars: int = 600) -> list[str]:
    chunks: list[str] = []
    heading = ""
    buffer: list[str] = []

    def flush() -> None:
        body = " ".join(buffer).strip()
        if body:
            chunks.append(f"{heading}: {body}" if heading else body)
        buffer.clear()

    for line in text.splitlines():
        stripped = line.strip()
        if match := re.match(r"^#{1,3}\s+(.*)", stripped):
            flush()
            heading = match.group(1)
        elif not stripped:
            if sum(len(b) for b in buffer) >= max_chars // 2:
                flush()
        else:
            buffer.append(stripped)
            if sum(len(b) for b in buffer) >= max_chars:
                flush()
    flush()
    return chunks
