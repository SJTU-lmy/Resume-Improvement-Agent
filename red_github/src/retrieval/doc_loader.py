# -*- coding: utf-8 -*-
"""从 resume_examples 读取检索文档（txt/docx/pdf/OCR 缓存 txt）。"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Set

from resume_reader import read_resume_text

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
EXAMPLES_DIR = PROJECT_ROOT / "resume_examples"
_SUPPORTED_SUFFIX = {".txt", ".docx", ".pdf"}


def load_documents(
    examples_dir: Path = EXAMPLES_DIR,
    allowed_names: Optional[Set[str]] = None,
) -> List[Dict]:
    docs: List[Dict] = []
    if not examples_dir.exists():
        return docs
    for path in sorted(examples_dir.rglob("*")):
        if path.suffix.lower() not in _SUPPORTED_SUFFIX:
            continue
        if allowed_names is not None and path.name not in allowed_names:
            continue
        try:
            if path.suffix.lower() == ".txt":
                text = path.read_text(encoding="utf-8-sig")
            else:
                text = read_resume_text(path)
        except Exception:
            continue
        if text.strip():
            docs.append({"path": str(path), "text": text.strip()})
    return docs
