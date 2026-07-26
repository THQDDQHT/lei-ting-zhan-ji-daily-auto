"""模板匹配调试工具。

用法：
  python tools/template_debug.py screenshots/某张截图.png
  python tools/template_debug.py screenshots/某张截图.png --template stamina_free
  python tools/template_debug.py screenshots/某张截图.png --template stamina_free,stamina_free_used_up

说明：
- 未指定 --template 时，会对 config.TEMPLATE_SPECS 中所有模板匹配一遍；
- 指定 --template 时，只匹配指定模板；
- 默认使用每个模板在 config.py 中配置的 grayscale 参数；
- 对于 stamina_free / stamina_free_used_up 这类颜色状态模板，建议配置 grayscale=False。
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

# 允许从项目根目录外执行
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from config import TEMPLATE_DIR, TEMPLATE_SPECS
from vision import TemplateMatcher


def parse_templates(value: str) -> list[str]:
    items = [item.strip() for item in value.split(",") if item.strip()]
    if not items:
        raise argparse.ArgumentTypeError("--template 不能为空")
    unknown = [item for item in items if item not in TEMPLATE_SPECS]
    if unknown:
        raise argparse.ArgumentTypeError(
            f"未知模板: {unknown}，可用模板: {', '.join(TEMPLATE_SPECS.keys())}"
        )
    return items


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="OpenCV模板匹配调试工具")
    parser.add_argument("screenshot", nargs="?", help="待匹配的截图路径")
    parser.add_argument(
        "--template",
        "-t",
        type=parse_templates,
        default=None,
        help="指定一个或多个模板名，多个用逗号分隔；不指定则匹配全部模板",
    )
    parser.add_argument(
        "--grayscale",
        choices=["auto", "true", "false"],
        default="auto",
        help="匹配模式：auto 使用 config.py 中的 grayscale 配置；true 强制灰度；false 强制彩色",
    )
    parser.add_argument(
        "--sort-by-score",
        action="store_true",
        help="按匹配分数从高到低输出",
    )
    parser.add_argument(
        "--list-templates",
        action="store_true",
        help="列出所有可用模板名后退出",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.list_templates:
        for name, spec in TEMPLATE_SPECS.items():
            mode = "gray" if spec.get("grayscale", True) else "color"
            print(f"{name:24s} mode={mode:5s} file={spec['file']} desc={spec.get('desc', '')}")
        return

    if not args.screenshot:
        parser.error("未使用 --list-templates 时必须提供 screenshot 参数")
    shot = Path(args.screenshot)
    if not shot.exists():
        raise FileNotFoundError(f"截图不存在: {shot}")

    names = args.template if args.template is not None else list(TEMPLATE_SPECS.keys())
    matcher = TemplateMatcher(grayscale=True)

    results = []
    for name in names:
        spec = TEMPLATE_SPECS[name]
        template_path = TEMPLATE_DIR / spec["file"]
        if not template_path.exists():
            results.append((name, None, f"模板文件不存在: {template_path}"))
            continue

        if args.grayscale == "auto":
            grayscale = spec.get("grayscale", True)
        elif args.grayscale == "true":
            grayscale = True
        else:
            grayscale = False

        res = matcher.match(
            shot,
            template_path,
            threshold=spec["threshold"],
            roi=spec.get("roi"),
            grayscale=grayscale,
        )
        results.append((name, res, grayscale))

    if args.sort_by_score:
        results.sort(key=lambda item: item[1].score if item[1] is not None else -999, reverse=True)

    print(f"截图: {shot}")
    print(f"模板数量: {len(results)}")
    for name, res, extra in results:
        spec = TEMPLATE_SPECS[name]
        if res is None:
            print(f"{name:24s} ERROR {extra}")
            continue
        mode = "gray" if extra else "color"
        print(
            f"{name:24s} found={str(res.found):5s} "
            f"score={res.score:.3f} threshold={spec['threshold']:.3f} "
            f"mode={mode:5s} center=({res.x:.1f},{res.y:.1f}) "
            f"roi={spec.get('roi')} desc={spec.get('desc','')}"
        )


if __name__ == "__main__":
    main()
