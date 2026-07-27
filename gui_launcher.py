from __future__ import annotations

import os
import queue
import subprocess
import sys
import threading
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

try:
    from config import (
        DEFAULT_CAPTURE_METHOD,
        DEFAULT_CLICK_METHOD,
        DEFAULT_ENABLE_RESOURCE_SALE,
        DEFAULT_FORCE_CLIENT_SIZE,
        DEFAULT_TOOLBOX_WINDOW_TITLE,
        DEFAULT_WINDOW_TITLE,
        TARGET_CLIENT_WIDTH,
        TARGET_CLIENT_HEIGHT,
        TOOLBOX_CLIENT_WIDTH,
        TOOLBOX_CLIENT_HEIGHT,
        DEFAULT_SAVE_SCREENSHOTS,
        DEFAULT_SAVE_LOGS,
        TEMPLATE_SPECS,
    )
except Exception:
    DEFAULT_CAPTURE_METHOD = "printwindow"
    DEFAULT_CLICK_METHOD = "message"
    DEFAULT_ENABLE_RESOURCE_SALE = False
    DEFAULT_FORCE_CLIENT_SIZE = True
    DEFAULT_TOOLBOX_WINDOW_TITLE = "Yang昜工具箱"
    DEFAULT_WINDOW_TITLE = "雷霆战机：集结"
    TARGET_CLIENT_WIDTH = 720
    TARGET_CLIENT_HEIGHT = 1280
    TOOLBOX_CLIENT_WIDTH = 414
    TOOLBOX_CLIENT_HEIGHT = 780
    DEFAULT_SAVE_SCREENSHOTS = False
    DEFAULT_SAVE_LOGS = False
    TEMPLATE_SPECS = {}

ROOT = Path(__file__).resolve().parent
PYTHON = sys.executable

SECTION_ITEMS = [
    ("redemption_code", "兑换码"),
    ("game_circle", "微信游戏圈"),
    ("decade_reunion", "十年集结"),
    ("shop", "商城"),
    ("interstellar", "星际探索"),
    ("stamina", "体力获取"),
    ("team", "战队征讨与捐献"),
    ("backpack", "背包空间处理"),
    ("treasure_hunt", "夺宝"),
    ("event_stage", "活动关卡"),
    ("level_sweep", "关卡扫荡"),
    ("boss_mode", "BOSS模式"),
    ("endless_mode", "无尽模式"),
    ("daily_rewards", "消息、活跃度、奖励领取"),
]


class CommandRunner:
    def __init__(self, log_callback, done_callback):
        self.log_callback = log_callback
        self.done_callback = done_callback
        self.proc: subprocess.Popen | None = None
        self.thread: threading.Thread | None = None
        self._lock = threading.Lock()

    def is_running(self) -> bool:
        with self._lock:
            return self.proc is not None and self.proc.poll() is None

    def run(self, cmd: list[str]) -> None:
        if self.is_running():
            messagebox.showwarning("正在运行", "已有命令正在运行，请等待结束或先停止。")
            return

        def worker():
            code = -1
            try:
                self.log_callback("\n" + "=" * 80 + "\n")
                self.log_callback("执行命令：\n" + command_to_text(cmd) + "\n\n")
                env = os.environ.copy()
                env.setdefault("PYTHONIOENCODING", "utf-8")
                with self._lock:
                    self.proc = subprocess.Popen(
                        cmd,
                        cwd=str(ROOT),
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        text=True,
                        encoding="utf-8",
                        errors="replace",
                        bufsize=1,
                        env=env,
                    )
                assert self.proc.stdout is not None
                for line in self.proc.stdout:
                    self.log_callback(line)
                code = self.proc.wait()
                self.log_callback(f"\n命令结束，退出码：{code}\n")
            except Exception as exc:
                self.log_callback(f"\n命令执行异常：{exc}\n")
            finally:
                with self._lock:
                    self.proc = None
                self.done_callback(code)

        self.thread = threading.Thread(target=worker, daemon=True)
        self.thread.start()

    def stop(self) -> None:
        with self._lock:
            proc = self.proc
        if proc is not None and proc.poll() is None:
            self.log_callback("\n正在终止当前命令...\n")
            try:
                proc.terminate()
            except Exception as exc:
                self.log_callback(f"终止失败：{exc}\n")


def command_to_text(cmd: list[str]) -> str:
    def quote(arg: str) -> str:
        if not arg:
            return '""'
        if any(ch.isspace() for ch in arg) or any(ch in arg for ch in ['"', '&', '|', '^', '<', '>']):
            return '"' + arg.replace('"', '\\"') + '"'
        return arg
    return " ".join(quote(str(x)) for x in cmd)


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("雷霆战机日活工具 - 电脑微信窗口版")
        self.geometry("1040x840")
        self.minsize(940, 720)

        self.log_queue: queue.Queue[str] = queue.Queue()
        self.runner = CommandRunner(self.enqueue_log, self.command_done)

        self.window_title = tk.StringVar(value=DEFAULT_WINDOW_TITLE)
        self.capture_method = tk.StringVar(value=DEFAULT_CAPTURE_METHOD)
        self.click_method = tk.StringVar(value=DEFAULT_CLICK_METHOD)
        self.force_client_size = tk.BooleanVar(value=DEFAULT_FORCE_CLIENT_SIZE)
        self.client_width = tk.IntVar(value=TARGET_CLIENT_WIDTH)
        self.client_height = tk.IntVar(value=TARGET_CLIENT_HEIGHT)
        self.toolbox_client_width = tk.IntVar(value=TOOLBOX_CLIENT_WIDTH)
        self.toolbox_client_height = tk.IntVar(value=TOOLBOX_CLIENT_HEIGHT)
        self.save_screenshots = tk.BooleanVar(value=DEFAULT_SAVE_SCREENSHOTS)
        self.save_logs = tk.BooleanVar(value=DEFAULT_SAVE_LOGS)
        self.enable_resource_sale = tk.BooleanVar(value=DEFAULT_ENABLE_RESOURCE_SALE)
        self.click_x = tk.DoubleVar(value=360)
        self.click_y = tk.DoubleVar(value=640)
        self.swipe_x1 = tk.DoubleVar(value=360)
        self.swipe_y1 = tk.DoubleVar(value=1030)
        self.swipe_x2 = tk.DoubleVar(value=360)
        self.swipe_y2 = tk.DoubleVar(value=520)
        self.swipe_duration = tk.DoubleVar(value=0.5)
        self.swipe_press_delay = tk.DoubleVar(value=0.1)
        self.swipe_release_delay = tk.DoubleVar(value=0.5)
        self.sections_vars = {key: tk.BooleanVar(value=True) for key, _ in SECTION_ITEMS}
        self.template_image_path = tk.StringVar(value="")
        self.template_names = list(TEMPLATE_SPECS.keys())
        self.template_sort_by_score = tk.BooleanVar(value=True)
        self.template_listbox: tk.Listbox | None = None
        self.show_more_features = tk.BooleanVar(value=False)

        self._build_ui()
        self.after(100, self.flush_log_queue)

    def _build_ui(self) -> None:
        outer = ttk.Frame(self, padding=10)
        outer.pack(fill=tk.BOTH, expand=True)

        style = ttk.Style(self)
        style.configure(
            "RunAction.TButton",
            font=("Microsoft YaHei UI", 12, "bold"),
            padding=(24, 12),
            foreground="#188038",
        )
        style.map(
            "RunAction.TButton",
            foreground=[
                ("pressed", "#0b5725"),
                ("active", "#126b31"),
            ],
        )
        style.configure(
            "StopAction.TButton",
            font=("Microsoft YaHei UI", 12, "bold"),
            padding=(24, 12),
            foreground="#c5221f",
        )
        style.map(
            "StopAction.TButton",
            foreground=[
                ("pressed", "#8f1714"),
                ("active", "#a91d19"),
            ],
        )

        quick_run = ttk.LabelFrame(outer, text="一键运行", padding=12)
        quick_run.pack(fill=tk.X)
        ttk.Button(
            quick_run,
            text="运行选中模块",
            command=self.run_selected,
            style="RunAction.TButton",
        ).grid(row=0, column=0, padx=(0, 8), sticky="we")
        ttk.Button(
            quick_run,
            text="停止当前命令",
            command=self.runner.stop,
            style="StopAction.TButton",
        ).grid(row=0, column=1, padx=(8, 0), sticky="we")
        quick_run.columnconfigure(0, weight=1)
        quick_run.columnconfigure(1, weight=1)

        sections = ttk.LabelFrame(outer, text="执行模块", padding=10)
        sections.pack(fill=tk.X, pady=(10, 0))
        for idx, (key, label) in enumerate(SECTION_ITEMS):
            row, column = divmod(idx, 5)
            if key == "backpack":
                backpack_frame = ttk.Frame(sections)
                backpack_frame.grid(row=row, column=column, sticky="w", padx=(0, 18), pady=(0, 6))
                ttk.Checkbutton(backpack_frame, text=label, variable=self.sections_vars[key]).pack(side=tk.LEFT)
                ttk.Label(backpack_frame, text="(").pack(side=tk.LEFT)
                ttk.Checkbutton(backpack_frame, text="资源出售", variable=self.enable_resource_sale).pack(side=tk.LEFT)
                ttk.Label(backpack_frame, text=")").pack(side=tk.LEFT)
            else:
                ttk.Checkbutton(sections, text=label, variable=self.sections_vars[key]).grid(row=row, column=column, sticky="w", padx=(0, 18), pady=(0, 6))

        ttk.Checkbutton(
            outer,
            text="显示更多功能",
            variable=self.show_more_features,
            command=self._toggle_more_features,
        ).pack(anchor="w", pady=(10, 0))

        self.debug_frame = ttk.LabelFrame(outer, text="调试工具", padding=10)

        settings_frame = ttk.Frame(self.debug_frame)
        settings_frame.pack(fill=tk.X)
        ttk.Label(settings_frame, text="窗口标题：").grid(row=0, column=0, sticky="w")
        ttk.Combobox(
            settings_frame,
            textvariable=self.window_title,
            values=[DEFAULT_WINDOW_TITLE, DEFAULT_TOOLBOX_WINDOW_TITLE],
            width=24,
            state="readonly",
        ).grid(row=0, column=1, sticky="w", padx=(4, 16))
        ttk.Label(settings_frame, text="截图方式：").grid(row=0, column=2, sticky="w")
        ttk.Combobox(
            settings_frame,
            textvariable=self.capture_method,
            values=["printwindow", "mss"],
            width=14,
            state="readonly",
        ).grid(row=0, column=3, sticky="w", padx=(4, 16))
        ttk.Label(settings_frame, text="点击方式：").grid(row=0, column=4, sticky="w")
        ttk.Combobox(
            settings_frame,
            textvariable=self.click_method,
            values=["message", "foreground"],
            width=14,
            state="readonly",
        ).grid(row=0, column=5, sticky="w", padx=(4, 0))

        ttk.Checkbutton(
            settings_frame,
            text="强制调整尺寸",
            variable=self.force_client_size,
        ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(8, 0))
        ttk.Checkbutton(
            settings_frame,
            text="保存运行截图",
            variable=self.save_screenshots,
        ).grid(row=1, column=2, columnspan=2, sticky="w", pady=(8, 0))
        ttk.Checkbutton(
            settings_frame,
            text="保存日志文件",
            variable=self.save_logs,
        ).grid(row=1, column=4, columnspan=2, sticky="w", pady=(8, 0))

        game_size_frame = ttk.Frame(settings_frame)
        game_size_frame.grid(row=2, column=0, columnspan=3, sticky="w", pady=(8, 0))
        ttk.Label(game_size_frame, text="游戏 client：").pack(side=tk.LEFT)
        ttk.Entry(game_size_frame, textvariable=self.client_width, width=5).pack(side=tk.LEFT)
        ttk.Label(game_size_frame, text="×").pack(side=tk.LEFT)
        ttk.Entry(game_size_frame, textvariable=self.client_height, width=5).pack(side=tk.LEFT)

        toolbox_size_frame = ttk.Frame(settings_frame)
        toolbox_size_frame.grid(row=2, column=3, columnspan=3, sticky="w", pady=(8, 0))
        ttk.Label(toolbox_size_frame, text="工具箱 client：").pack(side=tk.LEFT)
        ttk.Entry(toolbox_size_frame, textvariable=self.toolbox_client_width, width=5).pack(side=tk.LEFT)
        ttk.Label(toolbox_size_frame, text="×").pack(side=tk.LEFT)
        ttk.Entry(toolbox_size_frame, textvariable=self.toolbox_client_height, width=5).pack(side=tk.LEFT)

        ttk.Separator(self.debug_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=10)

        actions_frame = ttk.Frame(self.debug_frame)
        actions_frame.pack(fill=tk.X)
        ttk.Button(actions_frame, text="列出窗口", command=self.list_windows).grid(row=0, column=0, padx=4, pady=4, sticky="we")
        ttk.Button(actions_frame, text="截图保存", command=self.capture_window).grid(row=0, column=1, padx=4, pady=4, sticky="we")
        ttk.Button(actions_frame, text="刷新窗口状态", command=self.refresh_window).grid(row=0, column=2, padx=4, pady=4, sticky="we")
        ttk.Button(actions_frame, text="生成运行命令", command=self.preview_run_command).grid(row=0, column=3, padx=4, pady=4, sticky="we")
        ttk.Button(actions_frame, text="打开 screenshots", command=lambda: self.open_folder(ROOT / "screenshots")).grid(row=0, column=4, padx=4, pady=4, sticky="we")
        ttk.Button(actions_frame, text="打开 logs", command=lambda: self.open_folder(ROOT / "logs")).grid(row=0, column=5, padx=4, pady=4, sticky="we")

        click_frame = ttk.Frame(actions_frame)
        click_frame.grid(row=1, column=0, columnspan=6, sticky="we", pady=(6, 0))
        ttk.Label(click_frame, text="测试点击坐标 x/y：").pack(side=tk.LEFT)
        ttk.Entry(click_frame, textvariable=self.click_x, width=8).pack(side=tk.LEFT, padx=(4, 4))
        ttk.Entry(click_frame, textvariable=self.click_y, width=8).pack(side=tk.LEFT, padx=(4, 10))
        ttk.Button(click_frame, text="测试点击", command=self.click_test).pack(side=tk.LEFT, padx=(0, 8))

        swipe_frame = ttk.Frame(actions_frame)
        swipe_frame.grid(row=2, column=0, columnspan=6, sticky="we", pady=(6, 0))
        ttk.Label(swipe_frame, text="测试滑动 x1/y1 → x2/y2：").pack(side=tk.LEFT)
        ttk.Entry(swipe_frame, textvariable=self.swipe_x1, width=7).pack(side=tk.LEFT, padx=(4, 4))
        ttk.Entry(swipe_frame, textvariable=self.swipe_y1, width=7).pack(side=tk.LEFT, padx=(0, 4))
        ttk.Label(swipe_frame, text="→").pack(side=tk.LEFT)
        ttk.Entry(swipe_frame, textvariable=self.swipe_x2, width=7).pack(side=tk.LEFT, padx=(4, 4))
        ttk.Entry(swipe_frame, textvariable=self.swipe_y2, width=7).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Label(swipe_frame, text="持续/s：").pack(side=tk.LEFT)
        ttk.Entry(swipe_frame, textvariable=self.swipe_duration, width=6).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Label(swipe_frame, text="按下/s：").pack(side=tk.LEFT)
        ttk.Entry(swipe_frame, textvariable=self.swipe_press_delay, width=5).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Label(swipe_frame, text="抬起/s：").pack(side=tk.LEFT)
        ttk.Entry(swipe_frame, textvariable=self.swipe_release_delay, width=5).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(swipe_frame, text="测试滑动", command=self.swipe_test).pack(side=tk.LEFT)

        for i in range(6):
            actions_frame.columnconfigure(i, weight=1)

        self.template_frame = ttk.LabelFrame(outer, text="模板匹配调试", padding=10)
        ttk.Label(self.template_frame, text="图片：").grid(row=0, column=0, sticky="w")
        ttk.Entry(self.template_frame, textvariable=self.template_image_path).grid(row=0, column=1, columnspan=3, sticky="we", padx=(4, 8))
        ttk.Button(self.template_frame, text="选择图片", command=self.browse_template_image).grid(row=0, column=4, padx=(0, 4), sticky="we")

        ttk.Label(self.template_frame, text="模板：").grid(row=1, column=0, sticky="w", pady=(8, 0))
        list_frame = ttk.Frame(self.template_frame)
        list_frame.grid(row=1, column=1, columnspan=3, sticky="nsew", padx=(4, 12), pady=(8, 0))
        self.template_listbox = tk.Listbox(
            list_frame,
            selectmode=tk.EXTENDED,
            height=6,
            exportselection=False,
        )
        template_scroll = ttk.Scrollbar(list_frame, orient="vertical", command=self.template_listbox.yview)
        self.template_listbox.configure(yscrollcommand=template_scroll.set)
        for name in self.template_names:
            self.template_listbox.insert(tk.END, name)
        self.template_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        template_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        template_actions = ttk.Frame(self.template_frame)
        template_actions.grid(row=1, column=4, padx=(0, 4), pady=(8, 0), sticky="nwe")
        ttk.Button(template_actions, text="全选模板", command=self.select_all_templates).pack(fill=tk.X, pady=(0, 4))
        ttk.Button(template_actions, text="清空选择", command=self.clear_template_selection).pack(fill=tk.X, pady=(0, 4))
        ttk.Checkbutton(template_actions, text="按分数排序", variable=self.template_sort_by_score).pack(anchor="w", pady=(0, 4))
        ttk.Button(template_actions, text="匹配选中", command=self.run_template_match).pack(fill=tk.X)
        self.template_frame.columnconfigure(1, weight=1)

        self.log_frame = ttk.LabelFrame(outer, text="输出日志", padding=8)
        self.log_frame.pack(fill=tk.BOTH, expand=True, pady=(10, 0))
        self.log_text = tk.Text(self.log_frame, wrap="word", height=18)
        yscroll = ttk.Scrollbar(self.log_frame, orient="vertical", command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=yscroll.set)
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        yscroll.pack(side=tk.RIGHT, fill=tk.Y)

        status = ttk.Frame(outer)
        status.pack(fill=tk.X, pady=(8, 0))
        self.status_var = tk.StringVar(value="就绪")
        ttk.Label(status, textvariable=self.status_var).pack(side=tk.LEFT)

        self.log_text.insert(
            tk.END,
            "日常使用：勾选执行模块后点击“运行选中模块”；需要窗口、点击或模板调试时勾选“显示更多功能”。\n",
        )

    def _toggle_more_features(self) -> None:
        if self.show_more_features.get():
            self.debug_frame.pack(fill=tk.X, pady=(10, 0), before=self.log_frame)
            self.template_frame.pack(fill=tk.X, pady=(10, 0), before=self.log_frame)
        else:
            self.debug_frame.pack_forget()
            self.template_frame.pack_forget()

    def base_args(self) -> list[str]:
        args = ["--capture-method", self.capture_method.get()]
        args += ["--click-method", self.click_method.get()]
        if not self.force_client_size.get():
            args.append("--no-force-client-size")
        args += ["--client-width", str(int(self.client_width.get()))]
        args += ["--client-height", str(int(self.client_height.get()))]
        args += ["--toolbox-client-width", str(int(self.toolbox_client_width.get()))]
        args += ["--toolbox-client-height", str(int(self.toolbox_client_height.get()))]
        if self.save_screenshots.get():
            args.append("--save-screenshots")
        if self.save_logs.get():
            args.append("--save-logs")
        if self.enable_resource_sale.get():
            args.append("--enable-resource-sale")
        return args

    def selected_sections(self) -> str:
        selected = [key for key, _ in SECTION_ITEMS if self.sections_vars[key].get()]
        if not selected:
            raise ValueError("至少选择一个执行模块。")
        return ",".join(selected)

    def main_cmd(self) -> list[str]:
        return [PYTHON, "-u", "main.py"] + self.base_args()

    def selected_window_client_size(self) -> tuple[int, int]:
        if self.window_title.get() == DEFAULT_TOOLBOX_WINDOW_TITLE:
            return (
                int(self.toolbox_client_width.get()),
                int(self.toolbox_client_height.get()),
            )
        return int(self.client_width.get()), int(self.client_height.get())

    def list_windows(self) -> None:
        cmd = [
            PYTHON,
            "-u",
            str(Path("tools") / "window_probe.py"),
            "--keyword",
            self.window_title.get(),
            "--exact-title",
        ]
        self.run(cmd)

    def capture_window(self) -> None:
        client_width, client_height = self.selected_window_client_size()
        out = ROOT / "screenshots" / f"gui_capture_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        cmd = [
            PYTHON, "-u", str(Path("tools") / "capture_window.py"),
            "--window-title", self.window_title.get().strip(),
            "--capture-method", self.capture_method.get(),
            "--client-width", str(client_width),
            "--client-height", str(client_height),
            "--out", str(out),
        ]
        if not self.force_client_size.get():
            cmd.append("--no-force-client-size")
        self.run(cmd)

    def refresh_window(self) -> None:
        client_width, client_height = self.selected_window_client_size()
        cmd = [
            PYTHON, "-u", str(Path("tools") / "refresh_window.py"),
            "--window-title", self.window_title.get().strip(),
            "--client-width", str(client_width),
            "--client-height", str(client_height),
        ]
        self.run(cmd)

    def click_test(self) -> None:
        client_width, client_height = self.selected_window_client_size()
        cmd = [
            PYTHON, "-u", str(Path("tools") / "click_test.py"),
            "--window-title", self.window_title.get().strip(),
            "--capture-method", self.capture_method.get(),
            "--click-method", self.click_method.get(),
            "--client-width", str(client_width),
            "--client-height", str(client_height),
            "--x", str(float(self.click_x.get())),
            "--y", str(float(self.click_y.get())),
        ]
        if not self.force_client_size.get():
            cmd.append("--no-force-client-size")
        self.run(cmd)

    def swipe_test(self) -> None:
        client_width, client_height = self.selected_window_client_size()
        cmd = [
            PYTHON, "-u", str(Path("tools") / "swipe_test.py"),
            "--window-title", self.window_title.get().strip(),
            "--capture-method", self.capture_method.get(),
            "--click-method", self.click_method.get(),
            "--client-width", str(client_width),
            "--client-height", str(client_height),
            "--x1", str(float(self.swipe_x1.get())),
            "--y1", str(float(self.swipe_y1.get())),
            "--x2", str(float(self.swipe_x2.get())),
            "--y2", str(float(self.swipe_y2.get())),
            "--duration", str(float(self.swipe_duration.get())),
            "--press-delay", str(float(self.swipe_press_delay.get())),
            "--release-delay", str(float(self.swipe_release_delay.get())),
        ]
        if not self.force_client_size.get():
            cmd.append("--no-force-client-size")
        self.run(cmd)

    def run_selected(self) -> None:
        try:
            sections = self.selected_sections()
        except Exception as exc:
            messagebox.showerror("参数错误", str(exc))
            return
        cmd = self.main_cmd() + [
            "--sections", sections,
        ]
        self.run(cmd)

    def browse_template_image(self) -> None:
        initial_dir = ROOT / "screenshots"
        initial_dir.mkdir(parents=True, exist_ok=True)
        path = filedialog.askopenfilename(
            title="选择待匹配图片",
            initialdir=str(initial_dir),
            filetypes=[
                ("图片文件", "*.png *.jpg *.jpeg *.bmp"),
                ("所有文件", "*.*"),
            ],
        )
        if path:
            self.template_image_path.set(path)

    def selected_template_names(self) -> list[str]:
        if self.template_listbox is None:
            return []
        return [self.template_listbox.get(index) for index in self.template_listbox.curselection()]

    def select_all_templates(self) -> None:
        if self.template_listbox is not None:
            self.template_listbox.selection_set(0, tk.END)

    def clear_template_selection(self) -> None:
        if self.template_listbox is not None:
            self.template_listbox.selection_clear(0, tk.END)

    def run_template_match(self) -> None:
        image_path = self.template_image_path.get().strip()
        if not image_path:
            messagebox.showerror("参数错误", "请选择待匹配图片。")
            return

        template_names = self.selected_template_names()
        if not template_names:
            messagebox.showerror("参数错误", "请至少选择一个模板。")
            return

        cmd = [
            PYTHON, "-u", str(Path("tools") / "template_debug.py"),
            image_path,
            "--template", ",".join(template_names),
        ]
        if self.template_sort_by_score.get():
            cmd.append("--sort-by-score")
        self.run(cmd)

    def preview_run_command(self) -> None:
        try:
            sections = self.selected_sections()
            cmd = self.main_cmd() + [
                "--sections", sections,
            ]
            self.enqueue_log("\n运行命令：\n" + command_to_text(cmd) + "\n")
            self.clipboard_clear()
            self.clipboard_append(command_to_text(cmd))
            self.enqueue_log("已复制到剪贴板。\n")
        except Exception as exc:
            messagebox.showerror("参数错误", str(exc))

    def run(self, cmd: list[str]) -> None:
        self.status_var.set("运行中...")
        self.runner.run(cmd)

    def command_done(self, code: int) -> None:
        self.enqueue_log("" if code == 0 else "")
        self.status_var.set("就绪" if code == 0 else f"结束，退出码 {code}")

    def enqueue_log(self, text: str) -> None:
        self.log_queue.put(text)

    def flush_log_queue(self) -> None:
        try:
            while True:
                text = self.log_queue.get_nowait()
                self.log_text.insert(tk.END, text)
                self.log_text.see(tk.END)
        except queue.Empty:
            pass
        self.after(100, self.flush_log_queue)

    def open_folder(self, path: Path) -> None:
        path.mkdir(parents=True, exist_ok=True)
        try:
            os.startfile(str(path))  # type: ignore[attr-defined]
        except Exception as exc:
            messagebox.showerror("打开失败", str(exc))


if __name__ == "__main__":
    App().mainloop()
