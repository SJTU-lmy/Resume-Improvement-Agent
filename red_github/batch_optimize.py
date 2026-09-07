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
    parser = argparse.ArgumentParser(description="批量生成优化简历（成品版）")
    parser.add_argument("--job", default="", help="求职目标岗位，如 AI产品经理")
    parser.add_argument("--resume", default=None, help="简历文件路径（.docx/.pdf）")
    parser.add_argument("--out", default=str(PROJECT_ROOT / "new"), help="输出目录")
    parser.add_argument("--with-pdf", action="store_true", help="同时生成 pdf")
    parser.add_argument("--sample-limit", type=int, default=None, help="只处理前 N 条")
    parser.add_argument("--max-repair", type=int, default=1)
    parser.add_argument("--max-quality-repair", type=int, default=1)
    args = parser.parse_args()

    dataset_path = PROJECT_ROOT / "dataset" / "test_set.json"
    if not dataset_path.exists():
        print(f"[错误] 测试集不存在: {dataset_path}")
        return 1
    dataset = json.loads(dataset_path.read_text(encoding="utf-8-sig"))
    if args.sample_limit:
        dataset = dataset[: args.sample_limit]
    if not dataset:
        print("[错误] 测试集为空")
        return 1

    config = load_config()
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    info = []
    kept = filtered = failed = 0
    for sample in dataset:
        sid = str(sample.get("sample_id"))
        note_content = str(sample.get("note_content") or "")
        inline_resume = str(sample.get("user_resume") or "").strip()
        resume_text = inline_resume or read_resume_text(find_resume_file(args.resume))
        row = {"sample_id": sid, "status": "ok"}
        try:
            res = run_pipeline_v1(
                note_content, resume_text, target_job=args.job,
                config=config, max_repair=args.max_repair,
                max_quality_repair=args.max_quality_repair,
            )
        except Exception as e:
            row.update({"status": "error", "message": str(e)[:200]})
            failed += 1
            info.append(row)
            continue
        if res["status"] == "filtered_out":
            row.update({"status": "filtered_out", "reason": res.get("reason", "")})
            filtered += 1
            info.append(row)
            continue
        if res["status"] != "ok" or not isinstance(res.get("cleaned"), dict):
            row.update({"status": "error", "message": res.get("error", "")})
            failed += 1
            info.append(row)
            continue
        cleaned = res["cleaned"]
        files = write_optimized_resume(
            sid, str(cleaned.get("target_optimized_resume") or ""),
            output_dir=out_dir, include_pdf=args.with_pdf,
        )
        row.update({
            "job_name": cleaned.get("job_name"),
            "base_city": cleaned.get("base_city"),
            "contact_email": cleaned.get("contact_email"),
            "post_type": cleaned.get("post_type"),
            "docx": files.get("docx", ""),
        })
        kept += 1
        info.append(row)

    info_path = out_dir / "jobs_info.json"
    info_path.write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"完成：生成 {kept} 份，筛选剔除 {filtered}，失败 {failed}")
    print(f"简历目录：{out_dir}")
    print(f"岗位信息清单：{info_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
