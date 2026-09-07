from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Set, Tuple

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
POST_TYPES = {"全职", "实习", "兼职", "找继任"}

CITY_WORDS = [
    "北京", "上海", "广州", "深圳", "杭州", "成都", "武汉", "南京", "苏州", "西安",
    "长沙", "厦门", "合肥", "青岛", "天津", "重庆", "宁波", "无锡", "珠海", "佛山",
    "东莞", "济南", "大连", "福州", "昆明", "哈尔滨", "长春", "沈阳", "石家庄",
    "郑州", "南昌", "贵阳", "南宁", "太原", "兰州", "海口", "乌鲁木齐", "银川",
    "西宁", "呼和浩特", "拉萨", "香港", "澳门", "远程", "线上", "新加坡", "吉隆坡",
    "曼谷", "东京", "首尔", "伦敦", "纽约", "旧金山", "洛杉矶", "悉尼", "墨尔本",
    "多伦多", "温哥华", "柏林", "巴黎",
]
CITY_EN_MAP = {
    "beijing": "北京", "shanghai": "上海", "guangzhou": "广州", "shenzhen": "深圳",
    "hangzhou": "杭州", "chengdu": "成都", "wuhan": "武汉", "nanjing": "南京",
    "suzhou": "苏州", "xian": "西安", "chongqing": "重庆", "tianjin": "天津",
    "remote": "远程",
}
_UNVERIFIABLE_RE = re.compile(
    r"详情见|见P\d|见图|见图片|见评论|评论区|私信|看图|图[一二三四五六七八九十\d]|"
    r"详见p\d|jd见|见评论区",
    re.IGNORECASE,
)


def _note_cities(note: str) -> Set[str]:
    """从文本里找出命中的城市词（中文 + 常见英文），返回中文城市集合。"""
    found: Set[str] = set()
    low_note = note.lower()
    for city in CITY_WORDS:
        if city in note:
            found.add(city)
    for en, zh in CITY_EN_MAP.items():
        if re.search(rf"\b{re.escape(en)}\b", low_note):
            found.add(zh)
    return found


def validate_note_fields(
    cleaned: Dict[str, Any], note_content: str
) -> Tuple[List[Tuple[str, str]], List[str]]:
    """线索字段 vs 笔记原文核对。返回 (硬错误列表, 弱信号列表)。"""
    hard: List[Tuple[str, str]] = []
    weak: List[str] = []

    # --- contact_email ---
    email = str(cleaned.get("contact_email") or "").strip()
    if email:
        if not EMAIL_RE.fullmatch(email):
            hard.append(("email_invalid", f"contact_email 不符合邮箱格式: {email}"))
        else:
            note_emails = [e.lower().rstrip(".") for e in EMAIL_RE.findall(note_content)]
            norm_email = email.lower().rstrip(".")
            if note_emails and norm_email not in note_emails:
                hard.append(("email_mismatch", f"笔记邮箱 {'/'.join(note_emails)} 提取为 {email}（抄错）"))
            elif not note_emails:
                if _UNVERIFIABLE_RE.search(note_content):
                    weak.append("笔记未直接给出邮箱（私信/图内），contact_email 无法核验")
                else:
                    hard.append(("email_invalid", f"笔记原文中无邮箱，却填写 contact_email: {email}（疑似编造）"))

    # --- base_city ---
    base_city = str(cleaned.get("base_city") or "").strip()
    note_cities = _note_cities(note_content)
    base_cities = _note_cities(base_city)
    if base_city:
        if not base_cities:
            weak.append(f"base_city「{base_city}」不在城市词表中，无法核验")
        elif not note_cities:
            if _UNVERIFIABLE_RE.search(note_content):
                weak.append("笔记未直接写明城市（可能在图内），base_city 无法核验")
            else:
                hard.append(("city_fabricated", f"笔记中找不到城市，却填写 base_city: {base_city}（疑似编造）"))
        elif not (base_cities & note_cities):
            hard.append(("city_mismatch", f"笔记城市 {'/'.join(sorted(note_cities))}，提取为 {base_city}（抄错）"))
    elif note_cities:
        hard.append(("city_missing", f"笔记含城市 {'/'.join(sorted(note_cities))}，但 base_city 为空（漏填）"))

    # --- post_type ---
    post_type = str(cleaned.get("post_type") or "").strip()
    note_types = [t for t in POST_TYPES if t in note_content]
    if "继任" in note_content and "找继任" not in note_types:
        note_types.append("找继任")
    if post_type:
        if post_type not in POST_TYPES:
            hard.append(("post_type_invalid", f"post_type 不在枚举 {POST_TYPES}: {post_type}"))
        elif note_types and post_type not in note_types:
            hard.append(("post_type_conflict", f"笔记提及 {'/'.join(note_types)}，post_type 填 {post_type}（矛盾）"))
    elif note_types:
        weak.append(f"笔记提及 {'/'.join(note_types)} 但 post_type 为空")

    # --- job_name 必须能在笔记文字中找到依据 ---
    job_name = str(cleaned.get("job_name") or "").strip()
    if job_name:
        two_grams = {job_name[i : i + 2] for i in range(len(job_name) - 1)}
        overlap = sum(1 for g in two_grams if g in note_content)
        if overlap == 0:
            hard.append(("job_name_fabricated", f"笔记文字中无岗位名依据，却填写 job_name: {job_name}（应填\"\"）"))
        elif overlap == 1:
            weak.append("job_name 与笔记重叠度低（仅 1 个 2 字片段），请人工核验")

    return hard, weak


def check_missing_fields(cleaned: Dict[str, Any], note_content: str) -> Optional[str]:
    """笔记里写了职责/要求，但对应字段为空 → 返回问题描述（无则 None）。"""
    if re.search(r"职责|工作内容|岗位职责|工作职责", note_content) and not str(
        cleaned.get("job_duty") or ""
    ).strip():
        return "笔记中含职责/工作内容描述，但 job_duty 为空"
    if re.search(r"任职要求|岗位要求|要求|需要|优先", note_content) and not str(
        cleaned.get("job_requirement") or ""
    ).strip():
        return "笔记中含要求描述，但 job_requirement 为空"
    return None
