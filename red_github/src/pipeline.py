from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from llm_client import call_llm
from parser_clean import parser_clean

PROJECT_ROOT = Path(__file__).resolve().parent.parent
EXECUTOR_PROMPT_PATH = PROJECT_ROOT / "prompts" / "executor_v0.txt"


def build_user_message(note_content: str, user_resume: str) -> str:
    """拼接用户消息：小红书文案 + 简历。"""
    return (
        "【小红书招聘笔记】\n"
        f"{note_content}\n\n"
        "【我的简历】\n"
        f"{user_resume}"
    )


def load_executor_prompt() -> str:
    """读取 prompts/executor_v0.txt 作为 system prompt。"""
    return EXECUTOR_PROMPT_PATH.read_text(encoding="utf-8")


def run_pipeline(
    note_content: str,
    user_resume: str,
    config: Optional[Dict[str, Any]] = None,
) -> Tuple[Optional[Dict[str, Any]], str]:
    """单样本完整流程。

    Returns:
        (cleaned_json, raw_text)：cleaned_json 为 parser_clean 的结果，
        解析失败时为 None；raw_text 为 LLM 原始输出。
    """
    system_prompt = load_executor_prompt()
    user_message = build_user_message(note_content, user_resume)
    raw_text = call_llm(system_prompt, user_message, config=config)
    cleaned = parser_clean(raw_text)
    return cleaned, raw_text
