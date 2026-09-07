# -*- coding: utf-8 -*-
"""岗位关键词抽取：从 job_requirement（任职要求段）定位关键词并按类分类。

分层设计：
- 词典（config/job_keywords.json）作为分类器/标准词表：硬技能/工具/软素质/领域 + 别名归一；
- jieba 补充词典外新词 → 进入 pending（待确认），不直接参与命中率；
- 预留 KeywordExtractor 接口：未来可加 LlmKeywordExtractor（配置 keyword_extractor 切换，pipeline 不动）。
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Set

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DICT_PATH = PROJECT_ROOT / "config" / "job_keywords.json"

_CATEGORIES = ["hard_skills", "tools", "soft_qualities", "domain"]
_PENDING_STOPWORDS = {
    "自己", "一个", "可以", "需要", "要求", "岗位", "工作", "负责", "熟悉",
    "优先", "具备", "能够", "了解", "掌握", "良好", "较强", "相关", "经验",
    "能力", "学历", "专业", "本科", "硕士", "实习", "全职", "兼职", "继任",
    "简历", "投递", "邮箱", "尽快", "每周", "到岗", "时间", "以及", "或者",
    "包括", "进行", "使用", "主要", "日常", "协助", "配合", "上级", "安排",
    "任务", "内容", "职责", "任职", "上述", "如下", "熟悉者", "加分",
    "熟练掌握", "熟练", "掌握", "语言", "具备者", "优先者", "计算机", "统计学",
    "管理", "以后", "毕业", "在读", "互联网", "咨询", "行业", "会计", "事务所",
    "经历", "信息", "洞察力", "杭州", "保证", "学历", "以上", "经理", "常用",
    "工具", "文档", "编写", "完整", "落地", "流程", "包含", "每周", "到岗",
    "时长", "期限", "期间", "全职实习", "大厂", "企业", "部门", "团队",
}


def _load_dict() -> Dict:
    return json.loads(DICT_PATH.read_text(encoding="utf-8"))


def _term_in_text(term: str, text: str) -> bool:
    """词典词在要求文本中出现：纯 ASCII 用词边界，中文用子串。"""
    if re.fullmatch(r"[A-Za-z0-9+#.\-/ ]+", term):
        return re.search(
            r"(?<![A-Za-z0-9])" + re.escape(term) + r"(?![A-Za-z0-9])",
            text,
            re.IGNORECASE,
        ) is not None
    return term.lower() in text.lower()


class KeywordExtractor:
    """关键词抽取接口；子类实现 extract()。"""

    name = "base"

    def extract(self, requirement_text: str) -> Dict[str, List[str]]:
        raise NotImplementedError


class RuleKeywordExtractor(KeywordExtractor):
    """词典 + jieba 规则版。"""

    name = "rule"

    def __init__(self) -> None:
        self._cfg = _load_dict()
        self._categories = {c: list(self._cfg.get(c, [])) for c in _CATEGORIES}
        self._aliases = self._cfg.get("aliases", {})
        self._limits = self._cfg.get("limits", {})

    def extract(self, requirement_text: str) -> Dict[str, List[str]]:
        text = str(requirement_text or "")
        result: Dict[str, List[str]] = {
            "hard_skills": [],
            "tools": [],
            "soft_qualities": [],
            "domain": [],
            "pending": [],
        }
        if not text.strip():
            return result

        # 1) 别名归一（先于标准词匹配，保证规范写法）
        alias_hits: Set[str] = set()
        for alias, canonical in self._aliases.items():
            if _term_in_text(alias, text):
                alias_hits.add(str(canonical))

        # 2) 词典命中
        for category in _CATEGORIES:
            for term in self._categories[category]:
                if term in alias_hits or _term_in_text(term, text):
                    if term not in result[category]:
                        result[category].append(term)

        # 3) jieba 补充新词 → pending（词典外、非停用词、非序号碎片）
        try:
            import jieba
        except ImportError:
            return self._apply_limits(result)
        known = set(alias_hits)
        for terms in result.values():
            known.update(terms)
        seen: Set[str] = set()
        for token in jieba.lcut(text):
            t = token.strip()
            low = t.lower()
            if (
                not t
                or len(t) < 2
                or len(t) > 8
                or low in _PENDING_STOPWORDS
                or low in seen
                or not re.search(r"[\u4e00-\u9fa5a-z0-9]", low)
                or re.fullmatch(r"[\d\s.、,，:：;；\-_/\\()（）]+", low)
                or any(t == k or t in k for k in known)
            ):
                continue
            seen.add(low)
            result["pending"].append(t)
        return self._apply_limits(result)

    def _apply_limits(self, result: Dict[str, List[str]]) -> Dict[str, List[str]]:
        per = {
            "hard_skills": int(self._limits.get("hard_skills", 5)),
            "tools": int(self._limits.get("tools", 5)),
            "soft_qualities": int(self._limits.get("soft_qualities", 3)),
            "domain": int(self._limits.get("domain", 3)),
        }
        total_limit = int(self._limits.get("total", 15))
        total = 0
        for category in _CATEGORIES:
            result[category] = result[category][: per[category]]
            total += len(result[category])
        # pending 不设上限（仅供人工核对）
        result["pending"] = result["pending"][:20]
        return result


_DEFAULT_EXTRACTOR: Optional[KeywordExtractor] = None


def get_keyword_extractor(extractor_name: Optional[str] = None) -> KeywordExtractor:
    """按配置返回抽取器；当前仅 rule，未来可加 llm（改配置即切换）。"""
    global _DEFAULT_EXTRACTOR
    if extractor_name is None:
        try:
            cfg = _load_dict()
        except Exception:
            cfg = {}
        extractor_name = cfg.get("keyword_extractor", "rule")
    if extractor_name == "rule":
        if _DEFAULT_EXTRACTOR is None:
            _DEFAULT_EXTRACTOR = RuleKeywordExtractor()
        return _DEFAULT_EXTRACTOR
    raise ValueError(f"未知 keyword_extractor: {extractor_name}（当前支持 rule）")


def extract_requirement_keywords(requirement_text: str) -> Dict[str, List[str]]:
    """从任职要求文本抽取并分类关键词（含 pending）。"""
    return get_keyword_extractor().extract(requirement_text)


def confirmed_keywords(categorized: Dict[str, List[str]]) -> List[str]:
    """去掉 pending 后的正式关键词（按 硬技能/工具/软素质/领域 顺序展开）。"""
    out: List[str] = []
    for category in _CATEGORIES:
        for term in categorized.get(category, []):
            if term not in out:
                out.append(term)
    return out
