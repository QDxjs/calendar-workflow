"""Command-line entry point for CSV and manifest-driven calendar generation."""

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
import sys


def main() -> int:
    import generate as app

    parser = argparse.ArgumentParser(description="从 CSV 批量生成每日文学日历 SVG 与 PNG。")
    inputs = parser.add_mutually_exclusive_group()
    inputs.add_argument("--input", type=Path, help="输入 CSV（默认：同目录 content.csv）")
    inputs.add_argument("--replay", type=Path, metavar="MANIFEST", help="按批次清单重建，不重新抽选内容或版式")
    parser.add_argument("--outdir", type=Path, default=None,
                        help="批次目录；未指定时自动创建带时间戳的新目录")
    parser.add_argument("--seed", type=int, default=None,
                        help="随机种子；指定后可复现随机版式选择")
    parser.add_argument("--creator", type=str, default="",
                        help="可选：在日历页脚额外显示制作者/署名")
    parser.add_argument("--version", action="version", version=f"%(prog)s {app.APP_VERSION}")
    parser.add_argument("--check", action="store_true",
                        help="校验 CSV 与 SVG 排版，不写出文件或 PNG")
    args = parser.parse_args()
    if args.replay is not None and args.seed is not None:
        parser.error("--replay 不能与 --seed 同用；恢复模式直接读取清单记录。")
    try:
        if args.replay is not None:
            if args.creator:
                parser.error("--replay 不能与 --creator 同用；恢复模式直接读取清单记录。")
            pages, seed = app.prepare_replay(args.replay)
        else:
            input_path = args.input if args.input is not None else Path(__file__).with_name("content.csv")
            seed = args.seed
            pages = app.prepare_pages(input_path, seed=seed, creator=args.creator)
        if args.check:
            app.validate_rendering(pages, exhaustive_random_layouts=args.replay is None and seed is None)
            print(f"校验通过：{len(pages)} 页；未写入文件。")
            return 0
        if args.outdir is None:
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            prefix = "replay" if args.replay is not None else "csv_layout-from-file"
            base = app.APP_ROOT / "output" / "calendar_runs" / f"{prefix}_{stamp}"
            args.outdir = base
            suffix = 2
            while args.outdir.exists():
                args.outdir = Path(f"{base}_{suffix}")
                suffix += 1
        count = app.publish_with_summary(pages, args.outdir, seed=seed)
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 1
    print(f"完成：共生成 {count} 张日历页。")
    return 0
