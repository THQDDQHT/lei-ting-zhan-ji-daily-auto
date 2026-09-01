# 《雷霆战机：集结》日活挂机脚本

这是一个面向 Windows 电脑端微信小程序《雷霆战机：集结》的本地自动化工具。它通过窗口截图、OpenCV 模板识别和 Windows 输入控制，自动完成常见日活、奖励领取、关卡扫荡及部分战斗流程。

项目提供图形界面，可自由选择本次执行的模块、查看实时日志，并在首次使用或游戏界面变化时测试截图、点击、滑动和模板识别。

> 本项目不是游戏官方工具。微信版本、游戏界面、账号进度和电脑环境不同，都可能影响识别与操作结果。建议第一次运行时全程观察。

## 主要功能

- 自动执行常见日活流程，并按照固定顺序衔接各模块。
- 支持兑换码、微信游戏圈、商城、体力、战队、夺宝和日常奖励领取。
- 支持活动关卡、普通/英雄关卡扫荡、深空巡航、BOSS 模式、超限模式及无尽模式。
- 巡航和超限战斗可自动开护盾、限量使用爆弹、横向移动，并仅在精确识别到价格 `40` 时使用一次钻石复活。
- 支持背包装备合成、拆分和经验合成。
- 提供可选的残骸资源出售功能，默认关闭，避免误售。
- 自动调整并检查微信小程序窗口尺寸，保证模板与点击坐标一致。
- 支持后台消息点击，也可切换为前台真实鼠标操作。
- 提供 GUI 日志、窗口调试、截图、点击、滑动和模板匹配工具。

## 运行环境

- Windows 10/11
- 电脑端微信
- Python 3.10 或更高版本（建议安装时勾选 `Add Python to PATH`）
- 《雷霆战机：集结》微信小程序窗口
- `Yang昜工具箱` 窗口，仅在使用“兑换码”模块时需要

程序默认精确查找以下窗口标题：

```text
雷霆战机：集结
Yang昜工具箱
```

游戏窗口目标客户区为 `720 × 1280`，工具箱目标客户区为 `414 × 780`。程序默认会自动调整并校验尺寸，请勿在运行过程中手动拖动窗口大小。

## 快速开始

### 1. 获取项目

使用 Git：

```powershell
git clone https://github.com/PigeonGO2004/lei-ting-zhan-ji-daily-auto.git
cd lei-ting-zhan-ji-daily-auto
```

也可以直接在 GitHub 下载 ZIP，解压后进入项目目录。

### 2. 安装依赖

推荐使用 [uv](https://docs.astral.sh/uv/) 创建独立环境并安装依赖：

```powershell
uv venv .venv
uv pip install --python .venv\Scripts\python.exe -r requirements.txt
```

也可以双击：

```text
install_deps.bat
```

或直接使用 `pip`：

```powershell
python -m pip install -r requirements.txt
```

`start_gui.bat` 检测到 `.venv` 后会优先使用其中的 Python。巡航和超限模式使用 `rapidocr-onnxruntime` 读取战机战力、复活价格及挑战进度，该依赖已列入 `requirements.txt`。

运行测试时另安装开发依赖：

```powershell
uv pip install --python .venv\Scripts\python.exe -r requirements-dev.txt
.venv\Scripts\python.exe -m pytest -q
```

### 3. 准备游戏窗口

1. 登录电脑端微信。
2. 打开《雷霆战机：集结》，让它成为一个独立的小程序窗口。
3. 如果要执行兑换码模块，同时打开 `Yang昜工具箱`。
4. 第一次运行时不要完全遮挡游戏窗口，以便观察识别和点击是否正常。

### 4. 启动图形界面

双击：

```text
start_gui.bat
```

在“执行模块”中勾选本次需要完成的内容，然后点击“运行选中模块”。运行日志会直接显示在窗口下方。

“背包空间处理（资源出售）”默认不启用。只有确认 `config.py` 中的出售范围符合自己的需求后，才应勾选该选项。“深空巡航”和“超限模式”也默认不勾选，需要显式启用。

## 可用模块

| 模块 | 标识 | 功能 |
| --- | --- | --- |
| 兑换码 | `redemption_code` | 从 `Yang昜工具箱` 获取兑换码并在游戏内兑换 |
| 微信游戏圈 | `game_circle` | 处理游戏圈互动、礼包及相关社区奖励 |
| 十年集结 | `decade_reunion` | 领取十年集结相关奖励 |
| 商城 | `shop` | 领取商城中的免费资源和免费礼包 |
| 星际探索 | `interstellar` | 领取星际探索相关资源 |
| 体力获取 | `stamina` | 领取免费体力及好友体力 |
| 战队 | `team` | 处理战队征讨、奖励和捐献 |
| 背包空间处理 | `backpack` | 进行装备合成、拆分、经验合成及可选资源出售 |
| 夺宝 | `treasure_hunt` | 领取和使用可用的免费夺宝机会 |
| 活动关卡 | `event_stage` | 执行当前配置的活动关卡流程 |
| 关卡扫荡 | `level_sweep` | 按配置扫荡普通和英雄关卡，并处理相关奖励 |
| 深空巡航 | `deep_space_cruise` | 自动推进本期普通星域巡航，再进入深空巡航，处理战机选择、方程、战斗动作、复活与结算 |
| BOSS 模式 | `boss_mode` | 根据当天日期选择板块并执行 BOSS 模式 |
| 超限模式 | `overlimit_mode` | 依次将天龙、白鸟、天马、仙女四站各补到 9/12；普通挑战后，超限挑战自动购买 200 钻 MAX 装备试用 |
| 无尽模式 | `endless_mode` | 执行无尽模式世界竞赛及奖励领取 |
| 日常奖励 | `daily_rewards` | 领取活跃度和首页可领取奖励 |

勾选多个模块时，程序始终按内置日活顺序执行，不受勾选顺序影响。完整流程中背包处理会在不同阶段多次运行，以及时释放空间；残骸出售仍受单独开关控制。

## 首次运行建议

默认运行方式是：

```text
截图：printwindow
点击：message
```

这种组合会尽量在后台截图和点击，不移动真实鼠标。但电脑端微信使用 Chromium 渲染，不同版本对后台截图和输入的支持可能不同。

第一次使用时，可以勾选 GUI 中的“显示更多功能”，依次检查：

1. “列出窗口”能否找到正确窗口。
2. “刷新窗口状态”能否恢复目标尺寸。
3. “截图保存”得到的是否为当前游戏画面。
4. “测试点击”和“测试滑动”是否能让游戏响应。
5. “模板匹配调试”是否能识别当前界面按钮。

遇到问题时可按下表调整：

| 现象 | 建议 |
| --- | --- |
| 截图黑屏、停留在旧画面或内容不完整 | 改用 `mss`，并保持游戏窗口可见且不被遮挡 |
| 后台点击没有反应 | 改用 `foreground` |
| 窗口被遮挡后不再响应 | 使用“刷新窗口状态”，并避免完全遮挡窗口 |
| 大量模板无法识别 | 检查窗口尺寸；游戏更新后可能需要重新制作模板 |

使用 `foreground` 时，程序会激活游戏窗口并移动真实鼠标，运行期间不要同时操作鼠标和键盘。

## 常用配置

日常使用通常只需要修改项目根目录的 `config.py`：

### 关卡扫荡计划

`LEVEL_SWEEP_PLAN` 控制普通和英雄关卡的扫荡内容：

```python
{"level": 128, "sweeps": 2, "double_rewards": 2}
```

- `level`：关卡编号
- `sweeps`：扫荡次数
- `double_rewards`：其中前几次领取广告双倍奖励

请根据自己的关卡进度、体力和每日需求调整。

### 残骸资源出售

`RESOURCE_SALE_WRECKS` 控制各类残骸是否允许出售：

```python
"boss_wreck_lv1": True
```

- `True`：允许出售
- `False`：保留

配置为 `True` 并不会自动出售；还必须在 GUI 中勾选“资源出售”，或在命令行添加 `--enable-resource-sale`。首次使用前务必逐项检查，资源出售造成的物品消耗无法由脚本撤销。

### 深空巡航与超限模式

这两个模块目前是显式启用项：命令行默认流程不执行，GUI 初始也不勾选。建议先单独运行并观察。

- `DEEP_SPACE_CRUISE_CONFIG.complete_normal_cruise`：入口未解锁时，是否自动完成普通星域巡航。开启后会依次挑战可识别节点、处理低战力确认、结算和连续方程页。
- `normal_max_battles`：普通星域巡航的安全战斗上限，默认 `24`，对应三章各 7 个普通节点和 1 个 BOSS。
- `normal_equation_pick_strategy`：普通巡航默认选三张卡中品质最高的一张。
- `deep_equation_pick_strategy`：深空巡航默认按攻略关键方程表优先；OCR 未识别到关键名称时比较卡牌品质，仍无法判断才选中间卡。
- `equation_priority_keywords`：深空巡航的方程关键词优先表，默认按受击流挂机思路配置，可按自己的装备流派调整。
- `max_equation_picks_per_pause`：一次暂停中最多连续选择多少个方程，避免方程页未关闭时无限点击。
- `max_runs`：一次启动最多进行多少次真正的深空巡航出击。无尽战斗中出现方程页时会暂停结算轮询，选择完毕后继续等待战斗。
- `normal_battle_timeout_seconds` / `battle_timeout_seconds`：普通节点默认最多等待 8 分钟，真正深空巡航默认最多等待 2 小时，避免 333 波长跑被原来的短超时截断。
- `BATTLE_ASSIST_CONFIG`：普通巡航、深空巡航和超限挑战共用的战斗辅助。确认战斗 HUD 后按“护盾、爆弹、移动”执行，每次轮询至多一个动作。
- `shield_retry_seconds`：护盾尝试间隔，默认 `10` 秒；护盾优先级最高。
- `max_bombs_per_life` / `bomb_min_interval_seconds`：每条命最多使用 `1` 个爆弹，且不连续点击。
- `move_interval_seconds` / `move_positions`：按配置的三个位置周期性横移战机。
- `revive_by_40_diamonds`：广告不可用时允许一次钻石复活；必须连续两帧确认复活弹窗，并由 OCR 在两帧中都唯一、精确识别出 `40`。识别为 `20`、`60`、多个价格、两帧不一致或无法识别时都会关闭弹窗。
- `CRUISE_FIGHTER_CONFIG`：普通巡航节点会尝试选择 OCR 识别到的最高战力战机；读取不可靠时保留当前战机。
- `OVERLIMIT_MODE_CONFIG.boards`：默认按 `draco` / `cygnus` / `pegasus` / `andromeda` 的顺序处理天龙座、白鸟座、天马座和仙女座。
- `run_normal_challenge` / `run_overlimit_challenge`：是否执行普通挑战和超限挑战。
- `target_runs_per_board`：每个空间站的目标聚合完成槽位数。默认 `9`；某站显示“完成挑战 9/12”后立即停止该站，然后继续检查下一站。脚本按 BOSS 顺序只补达到 9 所需的挑战。
- `use_max_equipment_trial`：默认开启。仅超限挑战会购买 MAX，普通挑战绝不进入购买逻辑。
- `max_equipment_trial_expected_cost`：固定为 `200`。扣钻前必须在连续两帧中同时确认“超限挑战”弹窗、主挑战按钮、完整的“试用[MAX]装备（试用不进入排行榜单）”说明，以及价格区域唯一且精确的 `200`。
- 点击 `200` 后不会重试购买；只有连续两帧识别到“将以所拥有的超限挑战装备进行战斗”且价格 `200` 消失，才点击主挑战。弹窗原本已启用 MAX 时也不会重复购买。
- `max_equipment_trial_purchase_attempt_limit`：单次四站流程最多 `16` 次付费点击，即最多消耗 `3200` 钻。任何价格、弹窗或启用状态不确定时都会停止，不会降级为不买 MAX 直接开打。
- 两个配置中的等待、超时和 `revive_by_ad` 分别控制战斗轮询与广告复活。

按当前配置，超限挑战会自动购买 MAX；挑战确认失败则停止该站后续挑战。钻石复活另外遵守上面的 `40` 钻严格识别规则。

### 模板与坐标

`templates/`、`TEMPLATE_SPECS` 和固定坐标均基于目标窗口尺寸。只有在游戏界面更新、模板失效或主动更改窗口尺寸时，才需要调整这些内容。

仓库内模板基于当前项目环境制作，不保证适用于所有微信版本、显示环境或游戏版本。

## 命令行使用

推荐普通用户使用 GUI。需要脚本化运行时，可以直接执行：

```powershell
python main.py
```

只运行部分模块：

```powershell
python main.py --sections deep_space_cruise,overlimit_mode
```

使用可见窗口截图和真实点击：

```powershell
python main.py --capture-method mss --click-method foreground
```

启用残骸资源出售：

```powershell
python main.py --sections backpack --enable-resource-sale
```

查看全部参数：

```powershell
python main.py --help
```

默认不保存历史截图和日志文件，只在 GUI 或终端显示日志，并覆盖 `.runtime/current_screenshot.png` 供识别使用。需要保留运行记录时，可在 GUI 中开启对应选项，或使用：

```powershell
python main.py --save-screenshots --save-logs
```

## 常见问题

### 找不到游戏窗口

确认小程序已经作为独立窗口打开，且标题为 `雷霆战机：集结`。可以使用：

```powershell
python tools\window_probe.py --keyword 雷霆
```

### 游戏窗口尺寸调整失败

模板和点击坐标依赖 `720 × 1280` 客户区。如果显示器可用高度不足、微信限制窗口大小或系统环境特殊，程序可能无法达到目标尺寸并停止运行。

不建议简单关闭尺寸检查后继续使用，因为识别位置和点击坐标可能随之偏移。更换尺寸通常需要同时重做模板、ROI 和固定坐标。

### 游戏更新后无法识别

先使用 GUI 的截图和模板匹配调试确认失败模板。必要时重新截取对应按钮，替换 `templates/` 中的图片，并同步调整 `config.py` 中的识别区域和阈值。

### 运行中断

查看 GUI 输出日志，确认停止在哪个模块。界面动画、广告、网络加载、活动变化和临时弹窗都可能导致流程与预期不同。建议先单独运行失败模块，确认稳定后再执行完整流程。

## 项目结构

```text
main.py                 命令行入口
gui_launcher.py         图形界面入口
runner.py               日活流程与模块调度
windows_controller.py   微信窗口截图和输入控制
vision.py               OpenCV 模板识别
config.py               用户配置、模板和坐标参数
templates/              图像识别模板
tools/                  窗口、截图、点击、滑动和模板调试工具
```

## 使用说明

- 建议先单独运行少量低风险模块，再逐步启用完整流程。
- 游戏活动、奖励入口和广告页面可能随版本更新而变化。
- 使用前请自行确认账号状态、资源消耗和出售配置。
- 请遵守微信、游戏及所在地区的相关规则；使用本项目产生的风险由使用者自行承担。
