from __future__ import annotations

import ctypes
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

from PIL import Image, ImageStat

# 避免 Windows 显示缩放导致坐标被 DPI 虚拟化。
# 如果系统缩放不是 100%，不设置 DPI aware 时，程序读到的窗口坐标可能和实际屏幕坐标不一致。
try:  # pragma: no cover - 仅 Windows 生效
    ctypes.windll.user32.SetProcessDPIAware()
except Exception:
    pass


class WindowsControllerError(RuntimeError):
    pass


@dataclass
class WindowInfo:
    hwnd: int
    title: str
    class_name: str
    rect: tuple[int, int, int, int]
    client_rect_screen: tuple[int, int, int, int]


class WindowsController:
    """Windows 微信小程序窗口控制层。

    截图坐标系：微信窗口客户区坐标，即截图左上角为 (0, 0)。
    点击坐标系：同样使用客户区坐标，因此 runner.py 和 OpenCV 匹配结果可以直接点击。

    capture_method:
        - printwindow: 优先使用 Win32 PrintWindow 捕获窗口客户区。理论上可在窗口被遮挡时截图，
          但微信/Chromium/小游戏渲染不一定总能被 PrintWindow 正常捕获。
        - mss: 截取窗口客户区在屏幕上的区域。要求窗口可见且不能被遮挡。

    click_method:
        - message: 通过 Win32 PostMessage 向窗口/子窗口发送鼠标消息。不会移动物理鼠标，
          但微信小游戏不保证一定响应后台消息。
        - foreground: 激活窗口后使用 pyautogui 真实点击。最稳，但会占用鼠标和前台焦点。

    client_width/client_height:
        同时传入时作为该窗口实例的目标客户区尺寸。构造时默认自动调整并严格校验；
        force_client_size=False 时跳过自动调整，尺寸不匹配只记录警告。
    """

    def __init__(
        self,
        window_title: str = "雷霆战机：集结",
        capture_method: str = "printwindow",
        click_method: str = "message",
        client_width: int = 720,
        client_height: int = 1280,
        force_client_size: bool = True,
    ):
        if client_width <= 0 or client_height <= 0:
            raise ValueError("客户区宽高必须大于 0")

        self.window_title = window_title
        self.capture_method = capture_method.lower().strip()
        self.click_method = click_method.lower().strip()
        self.client_width = client_width
        self.client_height = client_height
        self.force_client_size = force_client_size
        self.hwnd: Optional[int] = None

        if self.capture_method not in {"printwindow", "mss"}:
            raise ValueError("capture_method 只能是 printwindow 或 mss")
        if self.click_method not in {"message", "foreground"}:
            raise ValueError("click_method 只能是 message 或 foreground")

        try:
            import win32con  # noqa: F401
            import win32gui  # noqa: F401
            import win32ui   # noqa: F401
            import win32api  # noqa: F401
            import mss       # noqa: F401
            import pyautogui # noqa: F401
        except Exception as exc:  # pragma: no cover - 仅 Windows 运行
            raise WindowsControllerError(
                "WindowsController 需要在 Windows 中安装 pywin32、mss、pyautogui。"
                "请先执行：pip install -r requirements.txt"
            ) from exc

        self.refresh_window()
        if self.force_client_size and not self.resize_client_to(
            self.client_width,
            self.client_height,
        ):
            raise WindowsControllerError(
                f"无法将 {self.window_title!r} 客户区调整为 {self.client_width}x{self.client_height}"
            )
        self.assert_client_size()

    # ---------- 窗口枚举与定位 ----------

    @staticmethod
    def list_windows(keyword: str = "") -> list[WindowInfo]:
        import win32gui

        keyword_lower = keyword.lower()
        items: list[WindowInfo] = []

        def enum_proc(hwnd: int, _param) -> None:
            if not win32gui.IsWindowVisible(hwnd):
                return
            title = win32gui.GetWindowText(hwnd) or ""
            if not title:
                return
            if keyword_lower and keyword_lower not in title.lower():
                return
            try:
                class_name = win32gui.GetClassName(hwnd) or ""
                rect = win32gui.GetWindowRect(hwnd)
                client_rect = WindowsController._client_rect_screen_static(hwnd)
            except Exception:
                return
            items.append(WindowInfo(hwnd=hwnd, title=title, class_name=class_name, rect=rect, client_rect_screen=client_rect))

        win32gui.EnumWindows(enum_proc, None)
        return items

    @staticmethod
    def _client_rect_screen_static(hwnd: int) -> tuple[int, int, int, int]:
        import win32gui

        left_top = win32gui.ClientToScreen(hwnd, (0, 0))
        client = win32gui.GetClientRect(hwnd)
        width = client[2] - client[0]
        height = client[3] - client[1]
        return (left_top[0], left_top[1], left_top[0] + width, left_top[1] + height)

    def refresh_window(self) -> int:
        candidates = self.list_windows(self.window_title)
        candidates = [w for w in candidates if w.title == self.window_title]
        if not candidates:
            raise WindowsControllerError(
                f"未找到标题等于 {self.window_title!r} 的窗口。"
                "可以先运行：python tools/window_probe.py --keyword 雷霆"
            )

        # 优先选择客户区面积最大的窗口，通常是小程序主窗口。
        candidates.sort(
            key=lambda w: (w.client_rect_screen[2] - w.client_rect_screen[0]) * (w.client_rect_screen[3] - w.client_rect_screen[1]),
            reverse=True,
        )
        self.hwnd = candidates[0].hwnd
        logging.info(
            "已选择窗口 hwnd=%s title=%r class=%s client_rect=%s",
            self.hwnd,
            candidates[0].title,
            candidates[0].class_name,
            candidates[0].client_rect_screen,
        )
        return self.hwnd

    def _ensure_hwnd(self) -> int:
        import win32gui

        if self.hwnd is None or not win32gui.IsWindow(self.hwnd):
            return self.refresh_window()
        return self.hwnd

    def get_window_rect(self) -> tuple[int, int, int, int]:
        """返回整个窗口外框在屏幕坐标中的矩形：left, top, right, bottom。"""
        import win32gui

        return win32gui.GetWindowRect(self._ensure_hwnd())

    def get_client_rect_screen(self) -> tuple[int, int, int, int]:
        """返回窗口客户区在屏幕坐标中的矩形：left, top, right, bottom。"""
        return self._client_rect_screen_static(self._ensure_hwnd())

    def get_client_size(self) -> tuple[int, int]:
        """返回窗口客户区尺寸：width, height。"""
        left, top, right, bottom = self.get_client_rect_screen()
        return right - left, bottom - top

    def resize_client_to(
        self,
        target_width: int,
        target_height: int,
    ) -> bool:
        """尝试一次性把窗口客户区调整到 target_width × target_height。

        Windows API 直接设置的是整个 window rect，不是 client rect。
        因此这里先测出边框/标题栏等非客户区占用尺寸，再反推应设置的外框尺寸。
        """
        import win32con
        import win32gui

        if target_width <= 0 or target_height <= 0:
            raise ValueError("客户区宽高必须大于 0")
        hwnd = self._ensure_hwnd()

        # 最小化时无法可靠调整客户区，先恢复。
        try:
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        except Exception:
            pass

        win_left, win_top, win_right, win_bottom = win32gui.GetWindowRect(hwnd)
        client_left, client_top, client_right, client_bottom = self.get_client_rect_screen()

        window_width = win_right - win_left
        window_height = win_bottom - win_top
        client_width = client_right - client_left
        client_height = client_bottom - client_top

        if client_width == target_width and client_height == target_height:
            logging.info("窗口客户区尺寸已满足要求：%dx%d", client_width, client_height)
            return True

        border_width = window_width - client_width
        border_height = window_height - client_height
        target_window_width = target_width + border_width
        target_window_height = target_height + border_height

        logging.info(
            "调整窗口尺寸：当前 window=%dx%d client=%dx%d；目标 client=%dx%d；设置 window=%dx%d",
            window_width,
            window_height,
            client_width,
            client_height,
            target_width,
            target_height,
            target_window_width,
            target_window_height,
        )

        win32gui.SetWindowPos(
            hwnd,
            None,
            win_left,
            win_top,
            int(target_window_width),
            int(target_window_height),
            win32con.SWP_NOZORDER | win32con.SWP_NOACTIVATE,
        )
        time.sleep(0.5)

        final_width, final_height = self.get_client_size()
        ok = final_width == target_width and final_height == target_height
        if ok:
            logging.info("窗口客户区尺寸调整成功：%dx%d", final_width, final_height)
        else:
            logging.warning(
                "窗口客户区尺寸调整后仍不符合目标：当前 %dx%d，目标 %dx%d",
                final_width,
                final_height,
                target_width,
                target_height,
            )
        return ok

    def refresh_window_resize_nudge(
        self,
        nudge_pixels: int = 1,
        settle_seconds: float = 0.2,
    ) -> bool:
        """轻微改变客户区尺寸再恢复，用于唤醒完全遮挡后可能失效的 WebView/Canvas 输入层。"""
        if nudge_pixels <= 0:
            raise ValueError("nudge_pixels 必须大于 0")

        self.activate()
        current_width, current_height = self.get_client_size()
        restore_width = self.client_width
        restore_height = self.client_height
        nudge_width = restore_width + nudge_pixels

        logging.info(
            "刷新窗口状态：client %dx%d -> %dx%d -> %dx%d",
            current_width,
            current_height,
            nudge_width,
            restore_height,
            restore_width,
            restore_height,
        )

        nudge_ok = self.resize_client_to(nudge_width, restore_height)
        time.sleep(settle_seconds)
        restore_ok = self.resize_client_to(restore_width, restore_height)
        return nudge_ok and restore_ok

    def assert_client_size(self) -> bool:
        """检查客户区尺寸；未强制调整时，尺寸不匹配只记录警告。"""
        width, height = self.get_client_size()
        logging.info("当前窗口客户区尺寸：%dx%d；期望：%dx%d", width, height, self.client_width, self.client_height)
        if width == self.client_width and height == self.client_height:
            return True

        message = (
            f"窗口客户区尺寸不符合要求：当前 {width}x{height}，"
            f"期望 {self.client_width}x{self.client_height}"
        )
        if self.force_client_size:
            raise WindowsControllerError(message)

        logging.warning("%s；未启用强制调整，继续运行", message)
        return False

    def _ensure_client_size_before_interaction(self) -> None:
        if not self.force_client_size:
            return

        width, height = self.get_client_size()
        if width == self.client_width and height == self.client_height:
            return

        logging.warning(
            "窗口交互前发现客户区尺寸变化：当前 %dx%d，目标 %dx%d，开始调整",
            width,
            height,
            self.client_width,
            self.client_height,
        )
        if not self.resize_client_to(self.client_width, self.client_height):
            self.assert_client_size()

    def activate(self) -> None:
        import pyautogui
        import win32con
        import win32gui

        self._ensure_client_size_before_interaction()
        hwnd = self._ensure_hwnd()
        try:
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            win32gui.SetForegroundWindow(hwnd)
        except Exception:
            # Windows 有前台切换限制时，借助 Alt 键提升成功率。
            try:
                pyautogui.press("alt")
                win32gui.SetForegroundWindow(hwnd)
            except Exception as exc:
                logging.warning("窗口激活失败：%s", exc)
        time.sleep(0.2)

    # ---------- 截图 ----------

    def screenshot(self, save_path: str | Path) -> Path:
        self._ensure_client_size_before_interaction()
        save_path = Path(save_path)
        save_path.parent.mkdir(parents=True, exist_ok=True)

        if self.capture_method == "printwindow":
            try:
                img = self._screenshot_printwindow_client()
                # PrintWindow 在部分 Chromium/WebGL 窗口上可能返回纯黑/纯透明图。
                stat = ImageStat.Stat(img.convert("L"))
                if max(stat.stddev) < 1.0:
                    logging.warning("PrintWindow 截图疑似无效，自动回退到 mss 客户区截图")
                    img = self._screenshot_mss_client()
            except Exception as exc:
                logging.warning("PrintWindow 截图失败，回退到 mss：%s", exc)
                img = self._screenshot_mss_client()
        else:
            self.activate()
            img = self._screenshot_mss_client()

        img.save(save_path)
        return save_path

    def _screenshot_mss_client(self) -> Image.Image:
        import mss

        left, top, right, bottom = self.get_client_rect_screen()
        width = right - left
        height = bottom - top
        if width <= 0 or height <= 0:
            raise WindowsControllerError(f"窗口客户区尺寸异常: {(left, top, right, bottom)}")
        with mss.mss() as sct:
            raw = sct.grab({"left": left, "top": top, "width": width, "height": height})
            return Image.frombytes("RGB", raw.size, raw.rgb)

    def _screenshot_printwindow_client(self) -> Image.Image:
        import win32con
        import win32gui
        import win32ui

        hwnd = self._ensure_hwnd()
        win_left, win_top, win_right, win_bottom = win32gui.GetWindowRect(hwnd)
        win_w = win_right - win_left
        win_h = win_bottom - win_top
        if win_w <= 0 or win_h <= 0:
            raise WindowsControllerError(f"窗口尺寸异常: {(win_left, win_top, win_right, win_bottom)}")

        hwnd_dc = win32gui.GetWindowDC(hwnd)
        mfc_dc = win32ui.CreateDCFromHandle(hwnd_dc)
        save_dc = mfc_dc.CreateCompatibleDC()
        bitmap = win32ui.CreateBitmap()
        bitmap.CreateCompatibleBitmap(mfc_dc, win_w, win_h)
        save_dc.SelectObject(bitmap)

        try:
            # 2 = PW_RENDERFULLCONTENT，Win8+ 支持；失败时返回0。
            result = ctypes.windll.user32.PrintWindow(hwnd, save_dc.GetSafeHdc(), 2)
            if result != 1:
                result = ctypes.windll.user32.PrintWindow(hwnd, save_dc.GetSafeHdc(), 0)
            if result != 1:
                raise WindowsControllerError("PrintWindow 返回失败")
            bmp_info = bitmap.GetInfo()
            bmp_str = bitmap.GetBitmapBits(True)
            full = Image.frombuffer(
                "RGB",
                (bmp_info["bmWidth"], bmp_info["bmHeight"]),
                bmp_str,
                "raw",
                "BGRX",
                0,
                1,
            )
        finally:
            win32gui.DeleteObject(bitmap.GetHandle())
            save_dc.DeleteDC()
            mfc_dc.DeleteDC()
            win32gui.ReleaseDC(hwnd, hwnd_dc)

        client_left, client_top, client_right, client_bottom = self.get_client_rect_screen()
        ox = client_left - win_left
        oy = client_top - win_top
        cw = client_right - client_left
        ch = client_bottom - client_top
        return full.crop((ox, oy, ox + cw, oy + ch))

    # ---------- 点击与滑动 ----------

    def tap(self, x: float, y: float, delay: float = 0.8) -> None:
        self._ensure_client_size_before_interaction()
        if self.click_method == "message":
            ok = self._tap_by_message(x, y)
            if not ok:
                logging.warning("后台消息点击失败，回退到前台真实点击")
                self._tap_foreground(x, y)
        else:
            self._tap_foreground(x, y)
        time.sleep(delay)

    def _tap_foreground(self, x: float, y: float) -> None:
        import pyautogui
        import win32gui

        self.activate()
        hwnd = self._ensure_hwnd()
        sx, sy = win32gui.ClientToScreen(hwnd, (int(round(x)), int(round(y))))
        pyautogui.click(sx, sy)

    @staticmethod
    def _make_lparam(x: int, y: int) -> int:
        return (y & 0xFFFF) << 16 | (x & 0xFFFF)

    def _tap_by_message(self, x: float, y: float) -> bool:
        import win32api
        import win32con

        hwnd = self._ensure_hwnd()
        try:
            cx = int(round(x))
            cy = int(round(y))
            lparam = self._make_lparam(cx, cy)
            win32api.PostMessage(hwnd, win32con.WM_MOUSEMOVE, 0, lparam)
            time.sleep(0.03)
            win32api.PostMessage(hwnd, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, lparam)
            time.sleep(0.08)
            win32api.PostMessage(hwnd, win32con.WM_LBUTTONUP, 0, lparam)
            logging.info("后台消息点击 hwnd=%s client=(%d,%d)", hwnd, cx, cy)
            return True
        except Exception as exc:
            logging.warning("后台消息点击异常：%s", exc)
            return False

    def swipe(
        self,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        duration: float = 0.5,
        press_delay: float = 0.1,
        release_delay: float = 0.5,
        delay: float = 0.8,
    ) -> None:
        """简单滑动。

        duration 表示从起点移动到终点的持续时间，单位为秒；
        press_delay 表示按下鼠标后到开始移动前的等待时间；
        release_delay 表示移动到终点后到抬起鼠标前的等待时间。
        """
        self._ensure_client_size_before_interaction()
        if self.click_method == "message":
            ok = self._swipe_by_message(
                x1,
                y1,
                x2,
                y2,
                duration=duration,
                press_delay=press_delay,
                release_delay=release_delay,
            )
            if not ok:
                logging.warning("后台消息滑动失败，回退到前台真实滑动")
                self._swipe_foreground(
                    x1,
                    y1,
                    x2,
                    y2,
                    duration=duration,
                    press_delay=press_delay,
                    release_delay=release_delay,
                )
        else:
            self._swipe_foreground(
                x1,
                y1,
                x2,
                y2,
                duration=duration,
                press_delay=press_delay,
                release_delay=release_delay,
            )
        time.sleep(delay)

    def _swipe_foreground(
        self,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        duration: float,
        press_delay: float,
        release_delay: float,
    ) -> None:
        import pyautogui
        import win32gui

        self.activate()
        hwnd = self._ensure_hwnd()
        sx1, sy1 = win32gui.ClientToScreen(hwnd, (int(round(x1)), int(round(y1))))
        sx2, sy2 = win32gui.ClientToScreen(hwnd, (int(round(x2)), int(round(y2))))
        pyautogui.moveTo(sx1, sy1)
        pyautogui.mouseDown(button="left")
        time.sleep(press_delay)
        pyautogui.moveTo(sx2, sy2, duration=max(0.05, duration))
        time.sleep(release_delay)
        pyautogui.mouseUp(button="left")
        logging.info(
            "前台真实滑动 client=(%.1f,%.1f)->(%.1f,%.1f) duration=%.2fs",
            x1,
            y1,
            x2,
            y2,
            duration,
        )

    def _swipe_by_message(
        self,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        duration: float,
        press_delay: float,
        release_delay: float,
    ) -> bool:
        import win32api
        import win32con

        hwnd = self._ensure_hwnd()
        duration = max(0.05, duration)
        steps = max(3, int(duration / 0.05))
        try:
            start_lparam = self._make_lparam(int(round(x1)), int(round(y1)))
            win32api.PostMessage(hwnd, win32con.WM_MOUSEMOVE, 0, start_lparam)
            time.sleep(0.03)
            win32api.PostMessage(hwnd, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, start_lparam)
            time.sleep(press_delay)

            lparam = start_lparam
            for i in range(1, steps + 1):
                t = i / steps
                cx = int(round(x1 + (x2 - x1) * t))
                cy = int(round(y1 + (y2 - y1) * t))
                lparam = self._make_lparam(cx, cy)
                win32api.PostMessage(hwnd, win32con.WM_MOUSEMOVE, win32con.MK_LBUTTON, lparam)
                time.sleep(duration / steps)

            time.sleep(release_delay)
            win32api.PostMessage(hwnd, win32con.WM_LBUTTONUP, 0, lparam)
            logging.info(
                "后台消息滑动 hwnd=%s client=(%.1f,%.1f)->(%.1f,%.1f) duration=%.2fs",
                hwnd,
                x1,
                y1,
                x2,
                y2,
                duration,
            )
            return True
        except Exception as exc:
            logging.warning("后台消息滑动异常：%s", exc)
            return False

    def type_text(self, text: str, interval: float = 0.05, delay: float = 0.8) -> None:
        """按当前点击模式向已经点击获得焦点的输入框输入文本。"""
        if not text:
            raise ValueError("输入文本不能为空")

        self._ensure_client_size_before_interaction()
        if self.click_method == "message":
            self._type_text_by_message(text, interval=interval)
        else:
            self._type_text_foreground(text, interval=interval)
        logging.info("已向当前输入框输入 %d 个字符", len(text))
        time.sleep(delay)

    def _type_text_foreground(self, text: str, interval: float) -> None:
        """激活窗口后使用真实键盘事件输入文本。"""
        import pyautogui

        self.activate()
        pyautogui.write(text, interval=interval)

    def _type_text_by_message(self, text: str, interval: float) -> None:
        """向微信主窗口发送键盘消息，不激活窗口。"""
        import win32api
        import win32con

        target = self._ensure_hwnd()

        for char in text:
            win32api.PostMessage(target, win32con.WM_CHAR, ord(char), 1)
            time.sleep(interval)

        logging.info("后台消息输入 hwnd=%s text_length=%d", target, len(text))

    def clear_text(self, delay: float = 0.5) -> None:
        """按当前点击模式清空已经获得焦点的输入框。"""
        self._ensure_client_size_before_interaction()
        if self.click_method == "message":
            self._clear_text_by_message()
        else:
            self._clear_text_foreground()
        logging.info("已清空当前输入框")
        time.sleep(delay)

    def _clear_text_foreground(self) -> None:
        import pyautogui

        self.activate()
        pyautogui.press("backspace", presses=8, interval=0.05)

    def _clear_text_by_message(self) -> None:
        import win32api
        import win32con

        target = self._ensure_hwnd()
        for _ in range(8):
            win32api.PostMessage(target, win32con.WM_KEYDOWN, win32con.VK_BACK, 0)
            win32api.PostMessage(target, win32con.WM_CHAR, 8, 1)
            win32api.PostMessage(target, win32con.WM_KEYUP, win32con.VK_BACK, 0)
            time.sleep(0.05)

    def press_key(self, key: str, delay: float = 0.8) -> None:
        """按当前点击模式发送单个按键。"""
        key = key.lower().strip()
        self._ensure_client_size_before_interaction()
        if self.click_method == "message":
            self._press_key_by_message(key)
        else:
            self._press_key_foreground(key)
        logging.info("已向窗口发送按键 %s", key)
        time.sleep(delay)

    def _press_key_foreground(self, key: str) -> None:
        import pyautogui

        self.activate()
        pyautogui.press(key)

    def _press_key_by_message(self, key: str) -> None:
        import win32api
        import win32con

        if key != "enter":
            raise ValueError(f"后台消息按键暂不支持: {key}")
        target = self._ensure_hwnd()
        win32api.PostMessage(target, win32con.WM_KEYDOWN, win32con.VK_RETURN, 1)
        win32api.PostMessage(target, win32con.WM_CHAR, 13, 1)
        win32api.PostMessage(target, win32con.WM_KEYUP, win32con.VK_RETURN, 0xC0000001)

    @staticmethod
    def _open_clipboard(retries: int = 10, interval: float = 0.05) -> None:
        import win32clipboard

        for attempt in range(1, retries + 1):
            try:
                win32clipboard.OpenClipboard()
                return
            except Exception:
                if attempt == retries:
                    raise
                time.sleep(interval)

    @classmethod
    def get_clipboard_text(cls) -> str:
        import win32clipboard

        cls._open_clipboard()
        try:
            if not win32clipboard.IsClipboardFormatAvailable(win32clipboard.CF_UNICODETEXT):
                return ""
            return str(win32clipboard.GetClipboardData(win32clipboard.CF_UNICODETEXT))
        finally:
            win32clipboard.CloseClipboard()

    @classmethod
    def clear_clipboard(cls) -> None:
        import win32clipboard

        cls._open_clipboard()
        try:
            win32clipboard.EmptyClipboard()
        finally:
            win32clipboard.CloseClipboard()

    def copy_selected_text(self, delay: float = 0.5) -> str:
        """复制窗口中已经选中的文本并返回剪贴板内容。"""
        self._ensure_client_size_before_interaction()
        self.clear_clipboard()
        if self.click_method == "message":
            self._copy_selected_text_by_message()
        else:
            self._copy_selected_text_foreground()
        time.sleep(delay)
        text = self.get_clipboard_text()
        if not text and self.click_method == "message":
            logging.warning("后台消息复制未得到文本，回退到前台真实复制")
            self._copy_selected_text_foreground()
            time.sleep(delay)
            text = self.get_clipboard_text()
        logging.info("已复制选中文本，text_length=%d", len(text))
        return text

    def _copy_selected_text_foreground(self) -> None:
        import pyautogui

        self.activate()
        pyautogui.hotkey("ctrl", "c")

    def _copy_selected_text_by_message(self) -> None:
        import win32api
        import win32con

        target = self._ensure_hwnd()
        win32api.PostMessage(target, win32con.WM_KEYDOWN, win32con.VK_CONTROL, 0)
        win32api.PostMessage(target, win32con.WM_KEYDOWN, ord("C"), 0)
        win32api.PostMessage(target, win32con.WM_CHAR, 3, 1)
        win32api.PostMessage(target, win32con.WM_KEYUP, ord("C"), 0)
        win32api.PostMessage(target, win32con.WM_KEYUP, win32con.VK_CONTROL, 0)
