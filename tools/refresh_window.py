"""通过轻微改变窗口客户区尺寸再恢复，刷新微信小程序窗口状态。

用于处理窗口被完全遮挡后，message 点击可能不再被 WebView/Canvas 输入层响应的情况。
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from config import DEFAULT_WINDOW_TITLE, TARGET_CLIENT_WIDTH, TARGET_CLIENT_HEIGHT
from windows_controller import WindowsController


def main() -> None:
    parser = argparse.ArgumentParser(description="通过 resize nudge 刷新微信小程序窗口状态")
    parser.add_argument("--window-title", default=DEFAULT_WINDOW_TITLE, help="窗口完整标题")
    parser.add_argument("--client-width", type=int, default=TARGET_CLIENT_WIDTH, help="恢复后的目标客户区宽度，默认720")
    parser.add_argument("--client-height", type=int, default=TARGET_CLIENT_HEIGHT, help="恢复后的目标客户区高度，默认1280")
    parser.add_argument("--nudge-pixels", type=int, default=1, help="临时增加的客户区宽度像素，默认1")
    parser.add_argument("--settle-seconds", type=float, default=0.2, help="临时尺寸停留秒数，默认0.2")
    args = parser.parse_args()

    ctrl = WindowsController(
        window_title=args.window_title,
        client_width=args.client_width,
        client_height=args.client_height,
    )
    before = ctrl.get_client_size()
    print(f"before client size: {before[0]}x{before[1]}")

    ok = ctrl.refresh_window_resize_nudge(
        nudge_pixels=args.nudge_pixels,
        settle_seconds=args.settle_seconds,
    )

    after = ctrl.get_client_size()
    print(f"after client size : {after[0]}x{after[1]}, ok={ok}")
    ctrl.assert_client_size()


if __name__ == "__main__":
    main()
