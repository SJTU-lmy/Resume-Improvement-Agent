# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from llm_client import load_config  # noqa: E402
from resume_reader import find_resume_file, read_resume_text  # noqa: E402
from resume_writer import write_optimized_resume  # noqa: E402
from v1_pipeline import run_pipeline_v1  # noqa: E402


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="单条运行（v1 多智能体流水线）")
    parser.add_argument("--sample_id", default=None, help="样本 id；缺省第一条")
    parser.add_argument("--job", default="", help="求职目标岗位，如 AI产品经理")
    parser.add_argument("--resume", default=None, help="简历文件路径（.docx/.pdf）")
    parser.add_argument("--with-pdf", action="store_true", help="同时生成 pdf")
    parser.add_argument("--out", default=str(PROJECT_ROOT / "new"), help="输出目录")
    args = parser.parse_args()

    dataset_path = PROJECT_ROOT / "dataset" / "test_set.json"
    if not dataset_path.exists():
        print(f"[错误] 测试集不存在: {dataset_path}，请先准备 dataset/test_set.json")
        return 1
    dataset = json.loads(dataset_path.read_text(encoding="utf-8-sig"))
    if not dataset:
        print("[错误] 测试集为空")
        return 1
    sample = None
    if args.sample_id:
        sample = next((s for s in dataset if str(s.get("sample_id")) == args.sample_id), None)
        if sample is None:
            print(f"[错误] 未找到 sample_id={args.sample_id}")
            return 1
    else:
        sample = dataset[0]

    sample_id = str(sample.get("sample_id"))
    note_content = str(sample.get("note_content") or "")
    inline_resume = str(sample.get("user_resume") or "").strip()
    if inline_resume:
        resume_text = inline_resume
    else:
        resume_text = read_resume_text(find_resume_file(args.resume))

    config = load_config()
    res = run_pipeline_v1(
        note_content, resume_text, target_job=args.job,
        config=config, max_repair=1, max_quality_repair=1,
    )
    if res["status"] == "filtered_out":
        print(f"[提示] 该笔记被筛选剔除（岗位与目标不匹配）：{res.get('reason','')}")
        return 0
    if res["status"] != "ok" or not isinstance(res.get("cleaned"), dict):
        print(f"[错误] 运行失败：{res.get('error','')}")
        return 1

    cleaned = res["cleaned"]
    print("岗位信息：", {
        "job_name": cleaned.get("job_name"),
        "base_city": cleaned.get("base_city"),
        "contact_email": cleaned.get("contact_email"),
        "post_type": cleaned.get("post_type"),
    })
    out_dir = Path(args.out)
    files = write_optimized_resume(
        sample_id, str(cleaned.get("target_optimized_resume") or ""),
        output_dir=out_dir, include_pdf=args.with_pdf,
    )
    print("已生成：")
    for p in files.values():
        print(" ", p)
    return 0


if __name__ == "__main__":
    sys.exit(main())
