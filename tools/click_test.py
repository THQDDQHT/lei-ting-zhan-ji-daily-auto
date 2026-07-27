"""测试 WindowsController 的窗口点击方式。

用法：
    python tools/click_test.py --window-title 雷霆战机：集结 --x 360 --y 640 --click-method message
    python tools/click_test.py --window-title 雷霆战机：集结 --x 360 --y 640 --click-method foreground
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from config import DEFAULT_CAPTURE_METHOD, DEFAULT_CLICK_METHOD, DEFAULT_FORCE_CLIENT_SIZE, DEFAULT_WINDOW_TITLE, TARGET_CLIENT_WIDTH, TARGET_CLIENT_HEIGHT
from windows_controller import WindowsController


def main() -> None:
    parser = argparse.ArgumentParser(description="测试对窗口客户区坐标的点击")
    parser.add_argument("--window-title", default=DEFAULT_WINDOW_TITLE)
    parser.add_argument("--capture-method", choices=["printwindow", "mss"], default=DEFAULT_CAPTURE_METHOD)
    parser.add_argument("--click-method", choices=["message", "foreground"], default=DEFAULT_CLICK_METHOD)
    parser.add_argument("--no-force-client-size", dest="force_client_size", action="store_false", default=DEFAULT_FORCE_CLIENT_SIZE, help="点击前不自动调整客户区尺寸")
    parser.add_argument("--client-width", type=int, default=TARGET_CLIENT_WIDTH, help="目标客户区宽度，默认720")
    parser.add_argument("--client-height", type=int, default=TARGET_CLIENT_HEIGHT, help="目标客户区高度，默认1280")
    parser.add_argument("--x", type=float, required=True)
    parser.add_argument("--y", type=float, required=True)
    args = parser.parse_args()

    ctrl = WindowsController(
        window_title=args.window_title,
        capture_method=args.capture_method,
        click_method=args.click_method,
        client_width=args.client_width,
        client_height=args.client_height,
        force_client_size=args.force_client_size,
    )
    ctrl.tap(args.x, args.y, delay=0.5)
    print(f"clicked client=({args.x}, {args.y}) by {args.click_method}")


if __name__ == "__main__":
    main()
