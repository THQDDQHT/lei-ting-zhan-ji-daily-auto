# 雷霆战机：集结 - 电脑端微信窗口日活脚本

本版本已经去掉 ADB / 模拟器控制层，改为直接控制 **主机 Windows 上的电脑端微信小程序窗口**。

核心流程仍然复用模拟器版的 `runner.py` 业务逻辑：

```text
星际探索领取
商城礼包领取
战队征讨与捐献
体力获取
```

但底层控制方式已经替换为：

```text
Windows 窗口客户区截图 → OpenCV 模板匹配 → Windows 窗口坐标点击
```


---

## 0. 图形界面启动器（推荐）

如果不想每次手动输入命令，可以直接双击：

```text
start_gui.bat
```

首次使用前先双击安装依赖：

```text
install_deps.bat
```

GUI 默认显示“一键运行”“执行模块”和输出日志。勾选所需模块后，直接点击“一键运行”区域中的“运行选中模块”即可。

首次调试时勾选“显示更多功能”，再按顺序操作：

```text
1. 列出窗口：确认窗口标题是否是“雷霆战机：集结”
2. 刷新窗口状态：置前窗口，并通过 resize nudge 恢复 client rect 到 720×1280
3. 截图保存：确认截图是否是小程序游戏画面
4. 测试点击：确认 message 或 foreground 点击是否有效
5. 测试滑动：确认列表拖拽是否有效
6. 取消“显示更多功能”，返回日常运行界面
```

GUI 启动器文件：

```text
gui_launcher.py       # Tkinter 图形界面
start_gui.bat         # 双击启动 GUI
install_deps.bat      # 双击安装 requirements.txt 中的依赖
run_all_default.bat   # 使用默认参数直接运行全部模块
```

其中 `message` 点击模式尽量不移动真实鼠标，但电脑端微信小游戏不一定响应；如果测试无效，再切换为 `foreground`。

## 1. 安装依赖

建议在 Windows 的 Python 环境中安装：

```bash
pip install -r requirements.txt
```

依赖包括：

```text
opencv-python：模板匹配
numpy：OpenCV数组处理
Pillow：截图保存和图像处理
mss：窗口客户区截图备用方案
pyautogui：前台真实点击模式
pywin32：窗口枚举、PrintWindow截图、后台消息点击
```

---

## 2. 先确认微信窗口标题

打开电脑端微信和《雷霆战机：集结》小程序窗口。只有执行兑换码模块时才需要额外打开 `Yang昜工具箱`；未选择兑换码模块时不会查找或创建工具箱控制器。兑换码流程要求游戏窗口客户区默认为 720×1280，工具箱窗口客户区默认为 414×780；默认会自动调整，也可分别通过 `--client-width/height` 和 `--toolbox-client-width/height` 覆盖。

然后运行：

```bash
python tools/window_probe.py --keyword 微信
```

或者：

```bash
python tools/window_probe.py --keyword 雷霆
```

它会列出匹配窗口，例如：

```text
hwnd        : 123456
title       : '雷霆战机：集结'
class       : Chrome_WidgetWin_0
client rect : (100, 80, 820, 1360), size=720x1280
```

主程序固定精确匹配 `config.py` 中的 `DEFAULT_WINDOW_TITLE`；辅助工具仍可通过 `--window-title` 指定窗口。如果只想按关键词查找窗口，请使用 `tools/window_probe.py`。

---

## 3. 运行脚本

默认精确查找标题为“雷霆战机：集结”的窗口：

```bash
python main.py
```

只运行某个模块：

```bash
python main.py --sections redemption_code
python main.py --sections game_circle
python main.py --sections decade_reunion
python main.py --sections shop
python main.py --sections interstellar
python main.py --sections stamina
python main.py --sections team
python main.py --sections backpack
python main.py --sections treasure_hunt
python main.py --sections event_stage
python main.py --sections level_sweep
python main.py --sections boss_mode
python main.py --sections endless_mode
python main.py --sections daily_rewards
```

运行多个模块：

```bash
python main.py --sections redemption_code,game_circle,decade_reunion,shop,interstellar,stamina,team,backpack,treasure_hunt,event_stage,level_sweep,boss_mode,endless_mode,daily_rewards
```

模块的执行顺序由 Runner 固定，不取决于 `--sections` 参数中的书写顺序。完整流程中 `backpack` 会执行三次：第一次完成装备合成与拆分、资源出售和经验合成；第二次仅在启用资源出售时再次出售；第三次只执行装备合成与拆分。残骸出售涉及物品消耗，需要额外传 `--enable-resource-sale` 或在 GUI 的“背包空间处理（资源出售）”中勾选；具体出售范围由 `config.py` 的 `RESOURCE_SALE_WRECKS` 统一配置。

`redemption_code` 是完整流程的第一项：进入 `Yang昜工具箱` 的雷霆兑换码列表，通过“关闭”按钮判断兑换码详情已经打开，点击兑换码文本使其选中后以 `Ctrl+C` 复制，再将识别出的兑换码输入游戏设置的兑换弹窗并领取奖励。若兑换后出现通用确认弹窗，表示兑换码无效或已经使用，程序会关闭提示，并只在输入下一条兑换码前清空上一次残留内容。列表清空后关闭工具箱窗口，并退出游戏兑换与设置弹窗。

`game_circle` 会打开微信小游戏侧边栏，领取可用礼包，给两条未点赞动态点赞并发送评论；关闭侧边栏后继续领取游戏圈、添加桌面的社区奖励和首页消息奖励。`message` 模式会尝试通过 Windows 消息后台输入评论，不激活窗口；如果当前微信版本不响应后台键盘消息，可切换为 `foreground`。

`daily_rewards` 会领取活跃度和奖励页中的可用奖励，默认作为总流程的最后一个模块执行；消息奖励已在 `game_circle` 末尾领取，不会重复执行。

`endless_mode` 会进入无尽模式世界竞赛，默认执行两轮闪击：参赛、选择助战、购买烈火、闪击进入战斗；战斗中检测到宝箱数量达到 5 后，会将飞机拖到屏幕上半部分等待坠机，然后领取奖励并返回竞赛页。

`event_stage` 会进入闯关模式的活动关卡，执行第一个活动“陨石陷阱”的闪击；战斗中若坠机会点击广告复活并在广告结束后继续等待；战斗结束后轮询结算页并点击“继续”，回到活动关卡页后点击左上角首页返回。

`boss_mode` 会进入闯关模式的 BOSS 模式，并按当天日期选择两个板块：偶数日期挑战第1、2板块，奇数日期挑战第3、4板块；每个板块进入后会以敌方战力 `15682` 判断“极难”，未命中时通过固定位置切换难度，再执行闪击。战斗中若坠机会点击广告复活并继续等待，结算后点击“继续”并返回板块选择页。

`level_sweep` 会进入闯关模式，先处理逐星长阶的逐星信标和逐星补给，再按 `config.py` 中的 `LEVEL_SWEEP_PLAN` 配置执行普通/英雄难度快速扫荡。每个关卡条目使用 `level` 指定关卡号，并可分别设置 `sweeps` 扫荡次数和 `double_rewards` 广告双倍次数；若扫荡后触发突发事件，会进入后返回闯关模式，并重新打开快速扫荡继续剩余关卡；首次累计实际扫荡 5 个关卡后，会退出快速扫荡领取顶部奖励，再恢复扫荡。

---

## 4. 截图方式与点击方式

### 截图方式

```bash
--capture-method printwindow
```

默认方式。尝试使用 Win32 `PrintWindow` 捕获窗口客户区。理论上可以在窗口被遮挡时截图，但微信小游戏属于 Chromium/WebGL/Canvas 渲染，不保证所有机器都能正确捕获。

```bash
--capture-method mss
```

截取窗口客户区在屏幕上的实际区域。稳定直观，但要求窗口可见且不能被遮挡。

### 点击方式

```bash
--click-method message
```

默认方式。通过 Win32 `PostMessage` 向微信窗口/子窗口发送鼠标消息，通常不会移动物理鼠标，也不一定抢你的主机鼠标。但微信小游戏不保证一定响应这种后台点击。

```bash
--click-method foreground
```

激活微信窗口后用 `pyautogui` 执行真实鼠标点击。响应最稳定，但会占用鼠标和前台焦点，运行时不适合同时正常操作电脑。

建议先测试：

```bash
python tools/click_test.py --window-title 雷霆 --x 360 --y 640 --click-method message
python tools/swipe_test.py --window-title 雷霆 --x1 360 --y1 1030 --x2 360 --y2 520 --duration 0.5 --press-delay 0.12 --release-delay 0.28 --click-method message
```

如果游戏不响应后台点击，再改用：

```bash
python main.py --click-method foreground
```

---

## 5. 固定窗口客户区尺寸

本工程默认尝试把电脑端微信小程序窗口的 **client rect** 调整为：

```text
720 × 1280
```

原因是模板图片、ROI 区域和固定点击坐标都基于这个坐标系。窗口大小变化后，按钮在截图中的尺寸和位置都会变化，OpenCV 匹配分数会下降，点击坐标也会偏移。

正式运行建议：

```bash
python main.py
```

如果窗口被完全遮挡后 `message` 点击不响应，可以用 resize nudge 刷新窗口状态。该工具会先显示并置前窗口，再轻微改变客户区尺寸并恢复到目标尺寸：

```bash
python tools/refresh_window.py --window-title 雷霆战机：集结
```

截图制作模板时，也建议使用同样尺寸：

```bash
python tools/capture_window.py --window-title 雷霆战机：集结 --out screenshots/pc_home.png
```

如果微信窗口受显示器高度或自身限制，无法调整到 720×1280，程序会停止运行。此时应固定一个实际可达尺寸，然后重新截图、裁剪模板并同步修改 `config.py` 里的 ROI 和固定点击坐标。

---

## 6. 重要：电脑端微信需要重新制作模板

当前 `templates/` 中保留的是模拟器 720×1280 版本裁剪出的模板。电脑端微信的窗口比例、字体渲染、按钮大小可能不同，因此可能不能直接识别。

推荐流程：

1. 固定电脑端微信小程序窗口客户区尺寸，主程序和截图工具默认会调整到 720×1280。
2. 使用工具截图：

```bash
python tools/capture_window.py --window-title 雷霆战机：集结 --out screenshots/pc_home.png
```

3. 用截图软件或图片工具裁剪按钮模板，覆盖 `templates/` 中对应文件。
4. 修改 `config.py` 中对应模板的 `roi`。
5. 用调试工具检查匹配分数：

```bash
python tools/template_debug.py screenshots/pc_home.png
```

模板坐标和点击坐标都基于 **微信窗口客户区截图**，也就是截图左上角为 `(0, 0)`。

---

## 7. 参数说明

```bash
python main.py --help
```

主要参数：

```text
--capture-method          printwindow 或 mss
--click-method            message 或 foreground
--no-force-client-size    不自动调整两个窗口的客户区尺寸；仍会严格检查当前尺寸
--client-width            游戏窗口目标客户区宽度，默认720
--client-height           游戏窗口目标客户区高度，默认1280
--toolbox-client-width    Yang昜工具箱目标客户区宽度，默认414
--toolbox-client-height   Yang昜工具箱目标客户区高度，默认780
--save-screenshots        保存运行过程中的历史截图；不加时只覆盖 .runtime/current_screenshot.png
--save-logs               保存 logs/daily_run_*.log 日志文件；不加时只输出到终端或 GUI 日志窗口
--enable-resource-sale    在 backpack 模块中额外执行资源残骸出售；默认关闭
--sections                选择执行模块；固定顺序：redemption_code,game_circle,decade_reunion,shop,interstellar,stamina,team,backpack,treasure_hunt,event_stage,level_sweep,boss_mode,endless_mode,daily_rewards
--list-windows            精确列出 config.py 中配置的游戏窗口后退出
```

---

## 8. 目录说明

```text
thunder_daily_auto_windows_host/
├── main.py                  # 程序入口
├── gui_launcher.py          # 图形界面启动器
├── start_gui.bat            # 双击启动 GUI
├── install_deps.bat         # 双击安装依赖
├── run_all_default.bat      # 默认参数运行全部模块
├── runner.py                # 日活流程逻辑与模块调度
├── windows_controller.py    # Windows微信窗口截图与点击控制层
├── vision.py                # OpenCV模板匹配
├── config.py                # 模板、ROI、阈值、窗口默认参数
├── requirements.txt         # Python依赖
├── templates/               # 按钮模板；电脑端微信建议重新裁剪覆盖
├── screenshots/             # 运行时截图、调试截图
├── logs/                    # 运行日志
└── tools/
    ├── window_probe.py      # 枚举窗口标题、客户区尺寸
    ├── capture_window.py    # 截取微信窗口客户区
    ├── click_test.py        # 测试后台/前台点击是否有效
    ├── swipe_test.py        # 测试后台/前台滑动是否有效
    ├── refresh_window.py    # 轻微改变客户区尺寸再恢复，用于刷新窗口状态
    └── template_debug.py    # 对一张截图测试所有模板匹配分数
```

---

## 9. 运行建议

主机电脑微信窗口方案无法像虚拟机那样彻底隔离。实际稳定性取决于两个因素：

```text
PrintWindow 是否能正确截取微信小游戏画面；
PostMessage 后台点击是否能被微信小游戏响应。
```

如果二者都可用，你可以在脚本运行时继续轻度使用电脑；如果不稳定，就需要切换到：

```bash
--capture-method mss --click-method foreground
```

这种方式最稳，但会影响你正常使用鼠标和前台窗口。
