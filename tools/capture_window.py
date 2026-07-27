"""截取电脑端微信/小程序窗口客户区，用于制作新模板。

用法：
    python tools/capture_window.py --window-title 雷霆战机：集结 --out screenshots/pc_home.png
    python tools/capture_window.py --window-title 雷霆战机：集结 --capture-method mss --out screenshots/pc_home.png
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
    parser = argparse.ArgumentParser(description="截取 Windows 微信/小程序窗口客户区")
    parser.add_argument("--window-title", default=DEFAULT_WINDOW_TITLE, help="窗口完整标题")
    parser.add_argument("--no-force-client-size", dest="force_client_size", action="store_false", default=DEFAULT_FORCE_CLIENT_SIZE, help="截图前不自动调整客户区尺寸")
    parser.add_argument("--client-width", type=int, default=TARGET_CLIENT_WIDTH, help="目标客户区宽度，默认720")
    parser.add_argument("--client-height", type=int, default=TARGET_CLIENT_HEIGHT, help="目标客户区高度，默认1280")
    parser.add_argument("--capture-method", choices=["printwindow", "mss"], default=DEFAULT_CAPTURE_METHOD)
    parser.add_argument("--out", default=str(ROOT / "screenshots" / "window_capture.png"), help="输出图片路径")
    args = parser.parse_args()

    ctrl = WindowsController(
        window_title=args.window_title,
        capture_method=args.capture_method,
        click_method=DEFAULT_CLICK_METHOD,
        client_width=args.client_width,
        client_height=args.client_height,
        force_client_size=args.force_client_size,
    )
    out = ctrl.screenshot(Path(args.out))
    print(f"saved: {out}")


if __name__ == "__main__":
    main()
