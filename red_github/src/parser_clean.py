from __future__ import annotations

import json
import re
from typing import Any, Dict, Optional

_BRACE_PATTERN = re.compile(r"\{[\s\S]*\}")


def parser_clean(raw_text: Optional[str]) -> Optional[Dict[str, Any]]:
    """从原始文本中提取大括号内 JSON，解析失败返回 None。"""
    if raw_text is None:
        return None
    match = _BRACE_PATTERN.search(raw_text)
    if not match:
        return None
    try:
        obj = json.loads(match.group(0))
    except (json.JSONDecodeError, ValueError):
        return None
    return obj if isinstance(obj, dict) else None
