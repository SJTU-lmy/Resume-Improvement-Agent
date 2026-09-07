# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from retrieval.factory import get_default_retriever

PROJECT_ROOT = Path(__file__).resolve().parent.parent
EXAMPLES_DIR = PROJECT_ROOT / "resume_examples"
AUTO_DIR = EXAMPLES_DIR / "auto"


def search(query: str, top_k: int = 3) -> List[str]:
    """按 config/retrieval_config.json 的 method 检索，返回 top-k 简历文本。"""
    return get_default_retriever().search_texts(query, top_k)


def archive_excellent_resume(
    sample_id: str,
    resume_text: str,
    score: int,
    threshold: int = 85,
    output_dir: Optional[Path] = None,
) -> Optional[Path]:
    """高分改写简历自动归档为 RAG 优秀范例；低于阈值返回 None。"""
    if score < threshold or not str(resume_text or "").strip():
        return None
    out_dir = Path(output_dir) if output_dir else AUTO_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{sample_id}_{score}.txt"
    path.write_text(str(resume_text).strip(), encoding="utf-8")
    return path
