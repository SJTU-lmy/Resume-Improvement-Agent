# -*- coding: utf-8 -*-
"""把单个 txt（笔记之间用整行等号 ===== 分隔）转换成 dataset/test_set.json。"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import List

PROJECT_ROOT = Path(__file__).resolve().parent
_DELIMITER_RE = re.compile(r"^=+$")


def split_notes(raw_text: str) -> List[str]:
    """按「整行只含 =」的行切分，返回去掉首尾空行、跳过空块的笔记列表。"""
    blocks: List[str] = []
    current: List[str] = []
    for line in raw_text.splitlines():
        if _DELIMITER_RE.match(line.strip()):
            block = "\n".join(current).strip()
            if block:
                blocks.append(block)
            current = []
        else:
            current.append(line)
    block = "\n".join(current).strip()
    if block:
        blocks.append(block)
    return blocks


def convert(input_path: Path, output_path: Path) -> int:
    if not input_path.exists():
        print(f"[错误] 输入文件不存在: {input_path}")
        return 1
    raw_text = input_path.read_text(encoding="utf-8-sig")
    notes = split_notes(raw_text)
    if not notes:
        print(
            f"[错误] {input_path} 中没有提取到任何笔记。"
            "请检查格式：每条笔记之间用单独一行 ===== 分隔"
        )
        return 1

    dataset = [
        {"sample_id": f"{index:03d}", "note_content": note}
        for index, note in enumerate(notes, start=1)
    ]
    if output_path.exists():
        print(f"[提示] 将覆盖已有文件: {output_path}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(dataset, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"转换完成：共 {len(notes)} 条笔记")
    print(f"输出文件：{output_path}")
    print(f"首条预览：{notes[0][:100]}")
    return 0


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="txt 笔记 → dataset/test_set.json")
    parser.add_argument(
        "--input",
        default=str(PROJECT_ROOT / "notes.txt"),
        help="输入 txt 路径（默认项目根目录 notes.txt）",
    )
    parser.add_argument(
        "--output",
        default=str(PROJECT_ROOT / "dataset" / "test_set.json"),
        help="输出 json 路径（默认 dataset/test_set.json）",
    )
    args = parser.parse_args()
    return convert(Path(args.input), Path(args.output))


if __name__ == "__main__":
    sys.exit(main())
