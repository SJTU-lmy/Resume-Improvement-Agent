# -*- coding: utf-8 -*-

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from content_validator import validate_note_fields
from keywords import confirmed_keywords, extract_requirement_keywords
from llm_client import call_llm
from retrieval.factory import get_default_retriever

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PROMPTS_DIR = PROJECT_ROOT / "prompts" / "v1"

QUALITY_LOW_SCORE = 60          # 总分低于此值触发质量修复
QUALITY_MATCH_FLOOR = 50        # 岗位匹配度低于此值触发
QUALITY_KEYWORD_FLOOR = 40      # 关键词覆盖低于此值触发


def _load_prompt(name: str) -> str:
    return (PROMPTS_DIR / name).read_text(encoding="utf-8")


def _render(template: str, **kwargs: Any) -> str:
    """只替换已知 {key} 占位符，保留模板里 JSON 示例的花括号。"""
    for key, value in kwargs.items():
        template = template.replace("{" + key + "}", str(value))
    return template


def _parse_any(raw_text: str) -> Any:
    """从原始文本提取第一个完整 JSON 对象或数组。"""
    if not raw_text:
        return None
    if raw_text.lstrip().startswith("["):
        match = re.search(r"\[[\s\S]*\]", raw_text)
    else:
        match = re.search(r"\{[\s\S]*\}", raw_text)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except (json.JSONDecodeError, ValueError):
        return None


def _call_and_parse(prompt: str, user_content: str, config: Optional[Dict]) -> Any:
    raw = call_llm(prompt, user_content, config=config)
    return _parse_any(raw), raw


def _call_filter(note_content: str, target_job: str, config: Optional[Dict]):
    prompt = _render(_load_prompt("filter.txt"), target_job=target_job or "（未指定）", note=note_content)
    obj, raw = _call_and_parse(prompt, "请判断并输出 JSON。", config)
    return obj, raw


def _call_optimizer(
    note_content: str,
    user_resume: str,
    target_job: str,
    filter_hint: Optional[Dict],
    examples: List[str],
    errors: Optional[List[Dict]],
    keywords: List[str],
    config: Optional[Dict],
):
    errors_section = ""
    if errors:
        errors_section = (
            "【上一轮检查/评分发现的问题，请逐条修正后重新输出】\n"
            + json.dumps(errors, ensure_ascii=False, indent=2)
        )
    prompt = _render(
        _load_prompt("optimizer.txt"),
        note=note_content,
        resume=user_resume,
        target_job=target_job or "（未指定）",
        filter_hint=json.dumps(filter_hint, ensure_ascii=False) if filter_hint else "（无）",
        examples="\n\n".join(examples) if examples else "（无）",
        errors_section=errors_section,
        keywords="、".join(keywords) if keywords else "（岗位职责/要求中的关键词）",
    )
    obj, raw = _call_and_parse(prompt, "请输出 JSON 结果。", config)
    return obj, raw


def _call_checker(
    cleaned: Dict[str, Any],
    note_content: str,
    original_resume: str,
    config: Optional[Dict],
):
    prompt = _render(
        _load_prompt("checker.txt"),
        note=note_content,
        original_resume=original_resume,
        cleaned_json=json.dumps(cleaned, ensure_ascii=False, indent=2),
    )
    obj, raw = _call_and_parse(prompt, "请输出检查结果 JSON 数组。", config)
    if not isinstance(obj, list):
        return [], raw
    return [e for e in obj if isinstance(e, dict)], raw


def _call_scorer(cleaned: Dict[str, Any], config: Optional[Dict]):
    keywords = confirmed_keywords(
        extract_requirement_keywords(str(cleaned.get("job_requirement") or ""))
    )
    prompt = _render(
        _load_prompt("scorer.txt"),
        job_name=str(cleaned.get("job_name") or ""),
        job_duty=str(cleaned.get("job_duty") or ""),
        job_requirement=str(cleaned.get("job_requirement") or ""),
        keywords="、".join(keywords) if keywords else "（无）",
        optimized_resume=str(cleaned.get("target_optimized_resume") or ""),
    )
    obj, raw = _call_and_parse(prompt, "请输出评分 JSON。", config)
    if isinstance(obj, dict):
        try:
            total = int(obj.get("total"))
        except (TypeError, ValueError):
            total = None
        return {
            "total": total,
            "scores": obj.get("scores") or {},
            "reason": str(obj.get("reason") or ""),
            "suggestions": obj.get("top_suggestions") or [],
        }, raw
    return None, raw


def _merge_rule_errors(cleaned: Dict[str, Any], note_content: str) -> List[Dict]:
    hard, _weak = validate_note_fields(cleaned, note_content)
    return [
        {
            "field": reason,
            "error_type": "规则校验",
            "detail": detail,
            "fix_suggestion": "按笔记原文修正该字段",
        }
        for reason, detail in hard
    ]


def _quality_triggered(score_obj: Optional[Dict]) -> bool:
    if not score_obj or score_obj.get("total") is None:
        return False
    if score_obj["total"] < QUALITY_LOW_SCORE:
        return True
    scores = score_obj.get("scores") or {}
    try:
        if int(scores.get("岗位匹配度", 100)) < QUALITY_MATCH_FLOOR:
            return True
        if int(scores.get("关键词覆盖", 100)) < QUALITY_KEYWORD_FLOOR:
            return True
    except (TypeError, ValueError):
        pass
    return False


def _quality_feedback(score_obj: Optional[Dict]) -> List[Dict]:
    if not score_obj:
        return []
    return [
        {
            "field": "整体质量",
            "error_type": "质量不达标",
            "detail": (
                f"总分 {score_obj.get('total')}，分项 {json.dumps(score_obj.get('scores') or {}, ensure_ascii=False)}；"
                f"评分理由：{score_obj.get('reason') or ''}；改进建议：{json.dumps(score_obj.get('suggestions') or [], ensure_ascii=False)}"
            ),
            "fix_suggestion": (
                "对照同岗位族优秀范例的表述方式提升岗位匹配度与关键词覆盖，"
                "按评分理由逐条改进；事实与数字必须仍全部来自原简历，禁止编造"
            ),
        }
    ]


def _error_repair_loop(
    cleaned: Dict[str, Any],
    note_content: str,
    user_resume: str,
    target_job: str,
    filter_obj: Dict,
    examples: List[str],
    keywords: List[str],
    config: Optional[Dict],
    max_repair: int,
):
    """规则 + checker + 错误修复循环。返回 (cleaned, first_checker_errors, final_checker_errors, repair_rounds)。"""
    first_checker_errors: List[Dict] = []
    final_checker_errors: List[Dict] = []
    repair_rounds = 0
    round_no = 0
    while True:
        rule_errors = _merge_rule_errors(cleaned, note_content)
        try:
            checker_errors, _raw = _call_checker(cleaned, note_content, user_resume, config)
        except Exception:
            checker_errors = []
        if round_no == 0:
            first_checker_errors = list(checker_errors)
        merged_errors = list(checker_errors) + rule_errors
        if not merged_errors or round_no >= max_repair:
            final_checker_errors = list(checker_errors)
            break
        cleaned, _optimizer_raw = _call_optimizer(
            note_content,
            user_resume,
            target_job,
            filter_obj,
            examples,
            merged_errors,
            keywords,
            config,
        )
        if not isinstance(cleaned, dict):
            final_checker_errors = list(checker_errors)
            break
        repair_rounds += 1
        round_no += 1
    return cleaned, first_checker_errors, final_checker_errors, repair_rounds


def run_pipeline_v1(
    note_content: str,
    user_resume: str,
    target_job: str = "",
    config: Optional[Dict] = None,
    max_repair: int = 1,
    max_quality_repair: int = 1,
) -> Dict[str, Any]:
    """V1 单样本流水线（含低分质量修复轮）。"""
    # 1. filter
    try:
        filter_obj, filter_raw = _call_filter(note_content, target_job, config)
    except Exception as e:
        return {"status": "error", "error": f"filter 失败: {e}"}
    if not isinstance(filter_obj, dict):
        return {"status": "error", "error": "filter 输出无法解析为 JSON", "filter_raw": filter_raw}
    try:
        relevance_score = int(filter_obj.get("relevance_score"))
    except (TypeError, ValueError):
        relevance_score = None
    if not filter_obj.get("keep", True):
        return {
            "status": "filtered_out",
            "relevance_score": relevance_score,
            "reason": str(filter_obj.get("reason") or ""),
            "filter_raw": filter_raw,
        }

    # 2. RAG（按 job_family 限定后的检索器）
    keywords = [str(k) for k in (filter_obj.get("keywords") or []) if str(k).strip()]
    query = " ".join(
        [
            target_job or "",
            str(filter_obj.get("job_hint") or ""),
            " ".join(keywords),
        ]
    )
    examples = get_default_retriever().search_texts(query, top_k=3)

    # 3. optimizer 初版
    cleaned, optimizer_raw = _call_optimizer(
        note_content, user_resume, target_job, filter_obj, examples, None, keywords, config
    )
    if not isinstance(cleaned, dict):
        return {
            "status": "error",
            "error": "optimizer 输出无法解析为 JSON",
            "optimizer_raw": optimizer_raw,
        }

    # 4-7. 规则 + checker + 错误修复
    cleaned, first_checker_errors, final_checker_errors, repair_rounds = _error_repair_loop(
        cleaned, note_content, user_resume, target_job, filter_obj, examples, keywords, config, max_repair
    )

    # 8. scorer + 低分质量修复轮
    quality_rounds = 0
    quality_triggered = False
    try:
        score_obj, score_raw = _call_scorer(cleaned, config)
    except Exception as e:
        score_obj, score_raw = None, f"scorer 失败: {e}"
    if _quality_triggered(score_obj) and max_quality_repair > 0:
        quality_triggered = True
        cleaned, _raw2 = _call_optimizer(
            note_content,
            user_resume,
            target_job,
            filter_obj,
            examples,
            _quality_feedback(score_obj),
            keywords,
            config,
        )
        if isinstance(cleaned, dict):
            quality_rounds += 1
            cleaned, _f1, final_checker_errors, extra_repair = _error_repair_loop(
                cleaned,
                note_content,
                user_resume,
                target_job,
                filter_obj,
                examples,
                keywords,
                config,
                max_repair,
            )
            repair_rounds += extra_repair
            try:
                score_obj, score_raw = _call_scorer(cleaned, config)
            except Exception as e:
                score_obj, score_raw = None, f"scorer 失败: {e}"

    return {
        "status": "ok",
        "cleaned": cleaned,
        "optimizer_raw": optimizer_raw,
        "relevance_score": relevance_score,
        "filter_reason": str(filter_obj.get("reason") or ""),
        "first_checker_errors": first_checker_errors,
        "final_checker_errors": final_checker_errors,
        "repair_rounds": repair_rounds,
        "quality_triggered": quality_triggered,
        "quality_rounds": quality_rounds,
        "score": score_obj.get("total") if score_obj else None,
        "score_obj": score_obj,
        "score_raw": score_raw,
    }
