# -*- coding: utf-8 -*-
"""词向量检索：provider 抽象 + 余弦相似度（纯 Python，不依赖 numpy/FAISS）。"""
from __future__ import annotations

from typing import Dict, List

from retrieval.base import BaseRetriever, RetrievalResult


def cosine(a: List[float], b: List[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(y * y for y in b) ** 0.5
    return dot / (na * nb) if na and nb else 0.0


class DashscopeEmbedding:
    """阿里云百炼 text-embedding-v3（纯 HTTP，零新增依赖）。"""

    def __init__(self, api_key: str, model: str = "text-embedding-v3", dimensions: int = 1024):
        self.api_key = api_key
        self.model = model
        self.dimensions = dimensions

    def embed(self, texts: List[str], text_type: str = "document") -> List[List[float]]:
        # 使用 DashScope OpenAI 兼容端点（原生端点对 input 校验有问题）；
        # text_type 仅作兼容参数保留，兼容端点不支持该字段。
        try:
            import requests
        except ImportError:
            raise RuntimeError(
                "未安装 requests 库，请先在 Anaconda 虚拟环境中执行 "
                "pip install -r requirements.txt 后重试"
            )
        # 兼容端点单批上限 10 条，按 10 条分批
        url = "https://dashscope.aliyuncs.com/compatible-mode/v1/embeddings"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        all_vectors: List[List[float]] = []
        for start in range(0, len(texts), 10):
            chunk = texts[start : start + 10]
            payload = {"model": self.model, "input": chunk}
            try:
                resp = requests.post(url, json=payload, headers=headers, timeout=60)
            except requests.RequestException as e:
                raise RuntimeError(f"阿里 embedding 请求失败：{e}")
            if resp.status_code != 200:
                raise RuntimeError(
                    f"阿里 embedding 返回状态码 {resp.status_code}：{resp.text[:300]}"
                )
            data = resp.json()
            try:
                embeddings = sorted(data["data"], key=lambda x: x.get("index", 0))
                all_vectors.extend(e["embedding"] for e in embeddings)
            except (KeyError, TypeError, IndexError) as e:
                raise RuntimeError(
                    f"阿里 embedding 响应解析失败：{e}，片段：{resp.text[:300]}"
                )
        return all_vectors


class VectorRetriever(BaseRetriever):
    name = "vector"

    def __init__(self, provider) -> None:
        self._provider = provider
        self._docs: List[Dict] = []
        self._vectors: List[List[float]] = []

    def index(self, docs: List[Dict]) -> None:
        self._docs = list(docs)
        texts = [d["text"][:2000] for d in self._docs]
        if texts:
            self._vectors = self._provider.embed(texts, text_type="document")

    def search(self, query: str, top_k: int = 3) -> List[RetrievalResult]:
        if not self._docs or not self._vectors:
            return []
        query_vec = self._provider.embed([query[:2000]], text_type="query")[0]
        scored = [
            (cosine(query_vec, vec), idx)
            for idx, vec in enumerate(self._vectors)
        ]
        scored.sort(key=lambda x: x[0], reverse=True)
        return [
            RetrievalResult(
                text=self._docs[i]["text"][:2000], score=s, source=self._docs[i]["path"]
            )
            for s, i in scored[:top_k]
        ]
