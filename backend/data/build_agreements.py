"""扫描 docs/*.pdf，生成技术协议检索库 backend/data/agreements.json。

只做原文抽取和分块，不生成摘要、不做推导；每条 chunk 保留 PDF 页码和原文。
"""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

from pypdf import PdfReader

DOCS_DIR = Path(__file__).resolve().parents[2] / "docs"
OUT = Path(__file__).parent / "agreements.json"

HEADING_RE = re.compile(r"^(?:\d+(?:\.\d+)*\s+\S|第[一二三四五六七八九十]+[章节]|附件\s*\S)")
SPECIAL_IDS = {"2001001111": "DOC-TA-2001001111-01"}


def page_lines(text: str) -> list[str]:
    return [line.strip() for line in (text or "").splitlines() if line.strip()]


def is_page_number(line: str) -> bool:
    return bool(re.fullmatch(r"[-—\s]*\d{1,3}[-—\s]*", line))


def heading(line: str) -> bool:
    return bool(HEADING_RE.match(line)) and len(line) <= 40


def build_chunks(pages: list[list[str]], doc_no: str) -> list[dict]:
    chunks: list[dict] = []
    for page_no, lines in enumerate(pages, start=1):
        buffer: list[str] = []

        def flush() -> None:
            nonlocal buffer
            text = "\n".join(buffer).strip()
            buffer = []
            if len(text) < 40:
                return
            if text.count("......") >= 2:
                return
            chunks.append(
                {
                    "id": f"CL-{doc_no}-{page_no}-{len(chunks) + 1:03d}",
                    "page": page_no,
                    "text": text,
                }
            )

        for line in lines:
            if heading(line) and buffer and len("\n".join(buffer)) >= 80:
                flush()
            buffer.append(line)
            joined = "\n".join(buffer)
            if len(joined) >= 320 and line.endswith(("。", "；", "：")):
                flush()
            elif len(joined) >= 520:
                flush()
        flush()
    return chunks


def main() -> None:
    docs = []
    for path in sorted(DOCS_DIR.glob("*.pdf")):
        match = re.match(r"(\d+)", path.stem)
        doc_no = match.group(1) if match else path.stem
        reader = PdfReader(str(path))
        raw_pages = [(page.extract_text() or "") for page in reader.pages]
        first_lines = [page_lines(text)[0] for text in raw_pages if page_lines(text)]
        header = Counter(first_lines).most_common(1)[0][0] if first_lines else ""

        pages: list[list[str]] = []
        for text in raw_pages:
            lines = [
                line
                for line in page_lines(text)
                if line != header and not is_page_number(line)
            ]
            pages.append(lines)

        chunks = build_chunks(pages, doc_no)
        docs.append(
            {
                "id": SPECIAL_IDS.get(doc_no, f"DOC-TA-{doc_no}"),
                "doc_no": doc_no,
                "title": path.stem,
                "file_name": path.name,
                "pages": len(raw_pages),
                "chunk_count": len(chunks),
                "chunks": chunks,
            }
        )

    OUT.write_text(json.dumps(docs, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"agreements={len(docs)} chunks={sum(d['chunk_count'] for d in docs)}")
    for doc in docs:
        print(doc["doc_no"], doc["pages"], doc["chunk_count"], doc["title"])


if __name__ == "__main__":
    main()
