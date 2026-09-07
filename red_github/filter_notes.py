# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent


def keyword_filter(
    dataset: List[Dict], keywords: List[str]
) -> Tuple[List[Dict], List[Dict]]:
    """保留 note_content 命中任一关键词的样本；返回 (保留, 滤除清单)。"""
    kept: List[Dict] = []
    dropped: List[Dict] = []
    for sample in dataset:
        note = str(sample.get("note_content") or "")
        low_note = note.lower()
        hits = [k for k in keywords if k.lower() in low_note]
        if hits:
            sample = dict(sample)
            sample["_matched_keywords"] = hits
            kept.append(sample)
        else:
            dropped.append(
                {
                    "sample_id": sample.get("sample_id"),
                    "note_preview": note[:80],
                }
            )
    return kept, dropped


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="按目标岗位关键词预筛笔记")
    parser.add_argument("--job", default="", help="目标岗位名称，如 AI产品经理")
    parser.add_argument(
        "--keywords",
        required=True,
        help="逗号分隔的关键词，如 产品,需求,AI,数据分析",
    )
    parser.add_argument(
        "--input",
        default=str(PROJECT_ROOT / "dataset" / "test_set.json"),
        help="输入测试集（默认 dataset/test_set.json，需先跑 convert_notes.py）",
    )
    parser.add_argument(
        "--output",
        default=str(PROJECT_ROOT / "dataset" / "test_set.json"),
        help="输出测试集（默认覆盖 dataset/test_set.json）",
    )
    args = parser.parse_args()

    keywords = [k.strip() for k in args.keywords.split(",") if k.strip()]
    if not keywords:
        print("[错误] 请提供至少一个关键词，如 --keywords 产品,需求,AI")
        return 1

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"[错误] 测试集不存在: {input_path}，请先运行 python convert_notes.py")
        return 1
    try:
        dataset = json.loads(input_path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as e:
        print(f"[错误] {input_path} 不是合法 JSON：{e}")
        return 1
    if not isinstance(dataset, list) or not dataset:
        print(f"[错误] {input_path} 为空或不是数组")
        return 1

    kept, dropped = keyword_filter(dataset, keywords)
    if not kept:
        print(
            f"[错误] 没有笔记命中关键词（{', '.join(keywords)}），"
            "请放宽关键词或检查笔记内容"
        )
        return 1

    output_path = Path(args.output)
    if output_path.exists():
        print(f"[提示] 将覆盖已有文件: {output_path}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(kept, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(f"目标岗位：{args.job or '（未填写）'}")
    print(f"保留 {len(kept)} / 共 {len(dataset)} 条笔记")
    print(f"输出文件：{output_path}")
    if dropped:
        print("滤除样本：")
        for item in dropped:
            print(f"  - {item['sample_id']}: {item['note_preview']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
