"""列出 Windows 窗口，用于确认电脑端微信/小程序窗口标题和客户区尺寸。

用法：
    python tools/window_probe.py --keyword 微信
    python tools/window_probe.py --keyword 雷霆
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from windows_controller import WindowsController


def main() -> None:
    parser = argparse.ArgumentParser(description="列出匹配的 Windows 窗口")
    parser.add_argument("--keyword", default="微信", help="窗口标题关键词")
    parser.add_argument("--exact-title", action="store_true", help="要求标题与 --keyword 完全一致")
    args = parser.parse_args()

    items = WindowsController.list_windows(args.keyword)
    if args.exact_title:
        items = [item for item in items if item.title == args.keyword]
    if not items:
        print(f"未找到标题包含 {args.keyword!r} 的窗口")
        return

    for item in items:
        l, t, r, b = item.client_rect_screen
        print("-" * 80)
        print(f"hwnd        : {item.hwnd}")
        print(f"title       : {item.title!r}")
        print(f"class       : {item.class_name}")
        print(f"window rect : {item.rect}")
        print(f"client rect : {item.client_rect_screen}, size={r-l}x{b-t}")
        status = "OK" if (r - l) == 720 and (b - t) == 1280 else "NO"
        print(f"target 720x1280: {status}")


if __name__ == "__main__":
    main()
