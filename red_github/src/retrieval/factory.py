# -*- coding: utf-8 -*-
"""Vector 检索器工厂：按 config/retrieval_config.json 构建默认检索器。"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Optional

from retrieval.base import BaseRetriever
from retrieval.doc_loader import load_documents
from retrieval.vector_retriever import DashscopeEmbedding, VectorRetriever

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config" / "retrieval_config.json"


def load_retrieval_config(config_path=None) -> Dict:
    path = Path(config_path) if config_path else DEFAULT_CONFIG_PATH
    if not path.exists():
        raise FileNotFoundError(
            f"检索配置不存在: {path}，请复制 config/retrieval_config.example.json "
            "为 retrieval_config.json 并填写 api_key"
        )
    return json.loads(path.read_text(encoding="utf-8"))


def create_retriever(config: Optional[Dict] = None) -> BaseRetriever:
    """创建基于 Vector 的检索器（含可选岗位族限定）。"""
    cfg = config or load_retrieval_config()
    vcfg = cfg.get("vector", {})
    api_key = str(vcfg.get("api_key") or "").strip()
    if not api_key or "在这里填写" in api_key:
        raise ValueError(
            "未配置检索 api_key：请在 config/retrieval_config.json 的 vector.api_key 填写"
        )
    provider = DashscopeEmbedding(
        api_key=api_key,
        model=str(vcfg.get("model") or "text-embedding-v3"),
        dimensions=int(vcfg.get("dimensions") or 1024),
    )
    retriever = VectorRetriever(provider)

    allowed_names = None
    family = str(cfg.get("job_family") or "").strip()
    if family:
        family_path = PROJECT_ROOT / "config" / "job_family.json"
        if family_path.exists():
            names = json.loads(family_path.read_text(encoding="utf-8")).get("families", {}).get(family)
            if names:
                allowed_names = {str(n) for n in names}
        else:
            print(f"[提示] config/job_family.json 不存在，忽略岗位族限定：{family}")
    retriever.index(load_documents(allowed_names=allowed_names))
    return retriever


_DEFAULT: Dict = {"retriever": None}


def get_default_retriever() -> BaseRetriever:
    """进程内缓存一份默认检索器。"""
    if _DEFAULT["retriever"] is None:
        _DEFAULT["retriever"] = create_retriever()
    return _DEFAULT["retriever"]
