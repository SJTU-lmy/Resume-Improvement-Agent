# -*- coding: utf-8 -*-
"""通用 LLM 请求客户端。

兼容 OpenAI 接口格式，但不依赖 openai 库：使用 requests 直接请求
chat/completions 接口（默认对接 DeepSeek）。超时与其它异常统一抛出 LLMError。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional, Union

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config" / "llm_config.json"


class LLMError(Exception):
    """LLM 调用失败（超时、网络异常、非 200 状态、未配置等）。"""


def preflight(config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """入口脚本预检：requests 是否安装、api_key 是否配置。返回配置字典。"""
    try:
        import requests  # noqa: F401
    except ImportError:
        raise LLMError(
            "未安装 requests 库，请先在 Anaconda 虚拟环境中执行 "
            "pip install -r requirements.txt 后重试"
        )
    cfg = config or load_config()
    api_key = str(cfg.get("api_key", "")).strip()
    if not api_key or "请填写" in api_key:
        raise LLMError(
            "未配置有效的 api_key，请在 config/llm_config.json 中填写 DeepSeek API Key"
        )
    return cfg


def load_config(config_path: Optional[Union[str, Path]] = None) -> Dict[str, Any]:
    """读取 config/llm_config.json，返回配置字典。"""
    path = Path(config_path) if config_path else DEFAULT_CONFIG_PATH
    if not path.exists():
        raise LLMError(f"配置文件不存在: {path}，请先在 config/llm_config.json 中填写配置")
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        raise LLMError(f"配置文件 {path} 不是合法 JSON: {e}")


def call_llm(
    system_prompt: str,
    user_content: str,
    config: Optional[Dict[str, Any]] = None,
) -> str:
    """调用 OpenAI 兼容接口，返回原始字符串结果。

    Args:
        system_prompt: 系统提示词。
        user_content: 用户消息内容。
        config: 配置字典；缺省时从 config/llm_config.json 读取。

    Returns:
        模型返回的原始文本（未做任何清洗）。

    Raises:
        LLMError: 请求超时、网络异常、非 200 状态、配置缺失等。
    """
    try:
        import requests  # 惰性导入：未安装时给出中文提示
    except ImportError:
        raise LLMError(
            "未安装 requests 库，请先在 Anaconda 虚拟环境中执行 "
            "pip install -r requirements.txt 后重试"
        )

    cfg = config or load_config()

    api_key = str(cfg.get("api_key", "")).strip()
    if not api_key or "请填写" in api_key:
        raise LLMError(
            "未配置有效的 api_key，请在 config/llm_config.json 中填写 DeepSeek API Key"
        )

    base_url = str(cfg.get("base_url", "https://api.deepseek.com")).rstrip("/")
    model = str(cfg.get("model", "deepseek-chat"))
    temperature = cfg.get("temperature", 0.3)
    max_tokens = cfg.get("max_tokens", 4096)
    timeout = cfg.get("timeout", 60)

    url = f"{base_url}/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False,
    }

    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=timeout)
    except requests.Timeout:
        raise LLMError(f"LLM 请求超时（{timeout} 秒）：{url}")
    except requests.RequestException as e:
        raise LLMError(f"LLM 请求失败：{e}")

    if resp.status_code != 200:
        raise LLMError(
            f"LLM 接口返回异常状态码 {resp.status_code}：{resp.text[:500]}"
        )

    try:
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
    except (ValueError, KeyError, IndexError, TypeError) as e:
        raise LLMError(f"LLM 响应解析失败：{e}，原始响应片段：{resp.text[:500]}")

    if not isinstance(content, str) or not content.strip():
        raise LLMError("LLM 返回内容为空")
    return content
