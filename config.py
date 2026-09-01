from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
TEMPLATE_DIR = BASE_DIR / "templates"
SCREENSHOT_DIR = BASE_DIR / "screenshots"
LOG_DIR = BASE_DIR / "logs"
RUNTIME_DIR = BASE_DIR / ".runtime"

# 运行产物保存开关。
# save_screenshots=False 时，程序仍会截取一张临时图用于识别，但会覆盖 .runtime/current_screenshot.png，
# 不再在 screenshots/ 下保存每一步的历史截图。
DEFAULT_SAVE_SCREENSHOTS = False
DEFAULT_SAVE_LOGS = False
DEFAULT_ENABLE_RESOURCE_SALE = False

# 电脑端微信窗口模式。
# 主流程固定精确匹配以下两个窗口标题；辅助工具仍可通过 --window-title 指定其他窗口。
DEFAULT_WINDOW_TITLE = "雷霆战机：集结"
DEFAULT_TOOLBOX_WINDOW_TITLE = "Yang昜工具箱"
DEFAULT_CAPTURE_METHOD = "printwindow"  # printwindow 或 mss
DEFAULT_CLICK_METHOD = "message"        # message 或 foreground

# 目标客户区尺寸。模板、ROI、固定点击坐标均默认基于这个坐标系。
# 电脑微信窗口大小变化会导致模板尺寸和坐标偏移，因此默认启动时强制调整到目标尺寸。
TARGET_CLIENT_WIDTH = 720
TARGET_CLIENT_HEIGHT = 1280
TOOLBOX_CLIENT_WIDTH = 414
TOOLBOX_CLIENT_HEIGHT = 780
DEFAULT_FORCE_CLIENT_SIZE = True

# 巡航/超限共用的 Windows 战斗辅助。所有坐标均基于 720x1280 客户区。
# 护盾优先；爆弹每条命最多一次且有较长冷却；钻石复活只接受连续两帧识别到 40。
BATTLE_ASSIST_CONFIG = {
    "enabled": True,
    "action_poll_seconds": 1.0,
    "shield_enabled": True,
    "shield_position": (639, 1096),
    "shield_retry_seconds": 10.0,
    "shield_protection_seconds": 5.0,
    "bomb_enabled": True,
    "bomb_initial_delay_seconds": 18.0,
    "bomb_min_interval_seconds": 45.0,
    "max_bombs_per_life": 1,
    "move_enabled": True,
    "move_initial_delay_seconds": 3.0,
    "move_interval_seconds": 5.0,
    "move_duration_seconds": 0.30,
    "move_positions": ((360, 980), (170, 980), (550, 980)),
    "revive_by_40_diamonds": True,
    "allowed_diamond_revive_costs": (40,),
    "revive_cost_roi": (250, 610, 470, 760),
    "diamond_revive_position": (360, 700),
    "max_paid_revives_per_battle": 1,
}

# 普通巡航节点详情页的战机选择。OCR 无法可靠读取战力时保留当前战机。
CRUISE_FIGHTER_CONFIG = {
    "enabled": True,
    "change_fighter_position": (111, 991),
    "fighter_list_roi": (0, 740, 720, 1000),
    "sortie_position": (360, 1026),
    "close_position": (662, 181),
    "list_wait_seconds": 0.8,
    "minimum_power": 1000,
    "maximum_power": 999999,
}

# 关卡扫荡配置。
# sweeps 表示该关卡扫荡几次；double_rewards 表示该关前几次扫荡领取广告双倍奖励。
# 深空巡航配置。先自动完成当期普通星域巡航，再进入真正的深空巡航。
DEEP_SPACE_CRUISE_CONFIG = {
    "complete_normal_cruise": True,
    # 普通星域巡航共 3 章，每章 7 个普通节点 + 1 个 BOSS，24 是完整周期的安全上限。
    "normal_max_battles": 24,
    # 普通巡航优先品质；深空巡航在 OCR 可用时优先攻略关键方程，再比较品质。
    "normal_equation_pick_strategy": "highest_quality",
    "deep_equation_pick_strategy": "priority",
    # 三张动态卡牌的识别范围、点击中心和下方确认按钮，均基于 720x1280 客户区。
    "equation_card_rois": (
        (0, 410, 240, 890),
        (240, 410, 480, 890),
        (480, 410, 720, 890),
    ),
    "equation_card_centers": ((120, 650), (360, 650), (600, 650)),
    "equation_confirm_position": (360, 977),
    "equation_fallback_card_index": 1,
    # 受击流兼顾普通挂机的优先表；前面的词条优先级更高。
    "equation_priority_keywords": (
        "检修面板",
        "检修模板",
        "方程重置",
        "反转装置",
        "狂暴协议",
        "拆解协议",
        "维修回路",
        "强力结构",
        "精炼模块",
        "晶化装甲",
        "虹吸模块",
        "自动基站",
        "协同模块",
        "组装模块",
        "稳态过载",
        "转化模块",
        "升级催化",
        "高效模块",
        "震荡催化",
        "无双指令",
        "烈性炸药",
    ),
    # 方程页可能连续弹出多次；超过上限说明页面没有正常关闭，停止继续点击。
    "max_equation_picks_per_pause": 40,
    "max_runs": 1,
    "initial_wait_seconds": 30.0,
    "poll_interval_seconds": 5.0,
    # 普通节点数分钟内应结束；深空 333 波可能持续很久，分别设置超时。
    "normal_battle_timeout_seconds": 480.0,
    "battle_timeout_seconds": 7200.0,
    "revive_by_ad": True,
}

# 超限模式配置。四个空间站分别达到 9/12 后停止，后三个目标不管。
# 超限挑战使用 200 钻 MAX 装备试用；付费前后都要连续两帧确认。
OVERLIMIT_MODE_CONFIG = {
    "boards": ("draco", "cygnus", "pegasus", "andromeda"),
    "run_normal_challenge": True,
    "run_overlimit_challenge": True,
    "target_runs_per_board": 9,
    # 每个空间站有 6 个 BOSS，每个 BOSS 各有普通、超限两个完成槽位。
    "stages_per_board": 6,
    "stage_header_roi": (0, 210, 520, 350),
    "use_max_equipment_trial": True,
    "max_equipment_trial_expected_cost": 200,
    "max_equipment_trial_min_confidence": 0.90,
    "max_equipment_trial_label_roi": (40, 930, 490, 1010),
    "max_equipment_trial_cost_roi": (500, 930, 680, 1015),
    "max_equipment_trial_prompt_roi": (50, 470, 670, 610),
    "max_equipment_trial_confirm_frames": 2,
    "max_equipment_trial_poll_seconds": 0.35,
    "max_equipment_trial_confirm_timeout_seconds": 6.0,
    "max_equipment_trial_point_tolerance": 25.0,
    # 从 0/12 补到 9/12 每站最多有 4 次超限挑战，四站总计最多 16 次。
    "max_equipment_trial_purchase_attempt_limit": 16,
    "initial_wait_seconds": 12.0,
    "poll_interval_seconds": 5.0,
    "battle_timeout_seconds": 240.0,
    "revive_by_ad": True,
}

LEVEL_SWEEP_PLAN = {
    "normal": [
        {"level": 128, "sweeps": 2, "double_rewards": 2},
        {"level": 124, "sweeps": 2, "double_rewards": 2},
        {"level": 104, "sweeps": 2, "double_rewards": 1},
        {"level": 100, "sweeps": 2, "double_rewards": 0},
        {"level": 114, "sweeps": 1, "double_rewards": 0},
    ],
    "hero": [
        {"level": 34, "sweeps": 1, "double_rewards": 1},
        {"level": 33, "sweeps": 1, "double_rewards": 1},
        {"level": 32, "sweeps": 1, "double_rewards": 1},
        {"level": 31, "sweeps": 1, "double_rewards": 1},
        {"level": 30, "sweeps": 1, "double_rewards": 1},
        {"level": 29, "sweeps": 1, "double_rewards": 0},
        {"level": 28, "sweeps": 1, "double_rewards": 0},
        {"level": 27, "sweeps": 1, "double_rewards": 0},
        {"level": 26, "sweeps": 1, "double_rewards": 0},
        {"level": 25, "sweeps": 1, "double_rewards": 0},
        {"level": 24, "sweeps": 1, "double_rewards": 0},
        {"level": 23, "sweeps": 1, "double_rewards": 0},
        {"level": 22, "sweeps": 1, "double_rewards": 0},
        {"level": 21, "sweeps": 1, "double_rewards": 0},
        {"level": 20, "sweeps": 1, "double_rewards": 0},
        {"level": 19, "sweeps": 1, "double_rewards": 0},
        # {"level": 18, "sweeps": 1, "double_rewards": 0},
        {"level": 17, "sweeps": 1, "double_rewards": 0},
        {"level": 16, "sweeps": 1, "double_rewards": 0},
        {"level": 15, "sweeps": 1, "double_rewards": 0},
    ],
}

# 背包资源出售配置。True 表示出售，False 表示保留。
RESOURCE_SALE_WRECKS = {
    "boss_wreck_lv1": True,
    "boss_wreck_lv2": True,
    "boss_wreck_lv3": True,
    "boss_wreck_lv4": True,
    "boss_wreck_lv5": True,
    "boss_wreck_lv6": False,
    "boss_wreck_lv7": False,
    "boss_wreck_lv8": True,
    "boss_wreck_lv9": True,
    "big_enemy_wreck_lv1": True,
    "big_enemy_wreck_lv2": True,
    "big_enemy_wreck_lv3": True,
    "big_enemy_wreck_lv4": True,
    "big_enemy_wreck_lv5": True,
    "big_enemy_wreck_lv6": True,
    "big_enemy_wreck_lv7": True,
    "big_enemy_wreck_lv8": True,
    "big_enemy_wreck_lv9": True,
    "small_enemy_wreck_lv1": True,
    "small_enemy_wreck_lv2": True,
    "small_enemy_wreck_lv3": True,
    "small_enemy_wreck_lv4": True,
    "small_enemy_wreck_lv5": True,
    "small_enemy_wreck_lv6": True,
    "small_enemy_wreck_lv7": True,
    "small_enemy_wreck_lv8": True,
    "small_enemy_wreck_lv9": True,
}

# ROI 使用 (x1, y1, x2, y2)，坐标基于“微信窗口客户区截图”。
# 注意：以下模板和 ROI 原始来源于模拟器 720x1280 版本。电脑端微信窗口尺寸/布局不同的话，
# 需要使用 tools/capture_window.py 重新截图、重新裁剪模板，并同步修正 ROI。
# threshold 是模板匹配最低置信度。若实际界面有轻微变化，可适当下调 0.03~0.08。
TEMPLATE_SPECS = {
    # ===== 加载图标 =====
    "loading": {
        "file": "loading.png",
        "threshold": 0.77,
        "roi": (270, 600, 450, 670),
        "grayscale": False, # 使用颜色模式可以提高区分度
        "desc": "加载图标",
    },

    # ===== 首页入口 =====
    "home_interstellar": {
        "file": "home_interstellar.png",
        "threshold": 0.86,
        "roi": (11, 690, 180, 860),
        "desc": "首页左下角：星际探索图标",
    },
    "home_shop": {
        "file": "home_shop.png",
        "threshold": 0.70,
        "roi": (11, 200, 150, 360),
        "desc": "首页左上方：商城图标", # home_shop图标会有跳动，容易识别失败，应降低threshold
    },
    "home_treasure_hunt": {
        "file": "home_treasure_hunt.png",
        "threshold": 0.86,
        "roi": (520, 100, 700, 210),
        "desc": "首页右上方：寻宝图标",
    },
    "home_team": {
        "file": "home_team.png",
        "threshold": 0.86,
        "roi": (530, 860, 700, 920),
        "desc": "首页右下方：战队图标",
    },
    "home_energy_plus": {
        "file": "home_energy_plus.png",
        "threshold": 0.86,
        "roi": (11, 44, 80, 110),
        "desc": "首页最左上：体力加号图标",
    },
    "home_friend": {
        "file": "home_friend.png",
        "threshold": 0.86,
        "roi": (11, 960, 140, 1110),
        "desc": "首页左下角：好友图标",
    },
    "home_warehouse": {
        "file": "home_warehouse.png",
        "threshold": 0.86,
        "roi": (340, 1000, 560, 1115),
        "desc": "首页右下角：仓库图标",
    },
    "home_community_reward": {
        "file": "home_community_reward.png",
        "threshold": 0.75,
        "roi": (570, 400, 710, 550),
        "desc": "首页右侧：社区奖励入口",
    },
    "home_information": {
        "file": "home_information.png",
        "threshold": 0.86,
        "roi": (90, 90, 230, 230),
        "desc": "首页顶部：消息入口",
    },
    "home_activity": {
        "file": "home_activity.png",
        "threshold": 0.86,
        "roi": (190, 90, 310, 230),
        "desc": "首页顶部：活跃度入口",
    },
    "home_decade_reunion": {
        "file": "home_decade_reunion.png",
        "threshold": 0.75,
        "roi": (660, 210, 707, 260),
        "desc": "首页右上侧：十年集结入口",
    },
    "home_sub_decade_reunion": {
        "file": "home_sub_decade_reunion.png",
        "threshold": 0.86,
        "roi": (485, 340, 695, 440),
        "desc": "首页右上侧：出现多项活动时，十年集结入口",
    },
    "home_challenge_mode": {
        "file": "home_challenge_mode.png",
        "threshold": 0.86,
        "roi": (360, 1060, 715, 1275),
        "grayscale": False,
        "desc": "首页右下：闯关模式入口",
    },
    "home_endless_mode": {
        "file": "home_endless_mode.png",
        "threshold": 0.82,
        "roi": (0, 1080, 360, 1260),
        "grayscale": False,
        "desc": "首页左下：无尽模式入口",
    },
    "home_reward": {
        "file": "home_reward.png",
        "threshold": 0.82,
        "roi": (280, 110, 395, 210),
        "desc": "首页、闯关模式顶部：奖励页签",
    },
    "nav_home": {
        "file": "nav_home.png",
        "threshold": 0.86,
        "roi": (11, 100, 130, 225),
        "desc": "各功能页左上：返回首页图标",
    },

    # ===== 通用模板 =====
    "endless_limited_time_group_match": {
        "file": "endless_limited_time_group_match.png",
        "threshold": 0.86,
        "roi": (80, 240, 660, 400),
        "desc": "无尽限时小组赛",
    },
    "endless_championship": {
        "file": "endless_championship.png",
        "threshold": 0.86,
        "roi": (80, 240, 660, 400),
        "desc": "无尽争霸赛",
    },
    "join_now": {
        "file": "join_now.png",
        "threshold": 0.86,
        "roi": (370, 1080, 660, 1210),
        "desc": "无尽限时小组赛/无尽争霸赛：立即参加按钮",
    },
    "limited_time_group_match_close": {
        "file": "limited_time_group_match_close.png",
        "threshold": 0.86,
        "roi": (630, 100, 709, 180),
        "desc": "无尽限时小组赛：关闭页面按钮",
    },
    "blitz": {
        "file": "blitz.png",
        "threshold": 0.86,
        "roi": (120, 1120, 390, 1260),
        "desc": "通用底部闪击按钮：无尽模式/BOSS模式",
    },
    "blitz_popup": {
        "file": "blitz_popup.png",
        "threshold": 0.86,
        "roi": (170, 880, 540, 1150),
        "desc": "通用闪击弹窗按钮：无尽模式/BOSS模式/活动关卡",
    },
    "confirm": {
        "file": "confirm.png",
        "threshold": 0.86,
        "roi": (200, 650, 625, 885),
        "desc": "通用确认按钮",
    },
    "ad_revive": {
        "file": "ad_revive.png",
        "threshold": 0.86,
        "roi": (350, 620, 620, 750),
        "grayscale": False,
        "desc": "活动关卡/BOSS模式坠机弹窗：右侧广告复活按钮",
    },
    "reward_claim": {
        "file": "reward_claim.png",
        "threshold": 0.86,
        "roi": (180, 1000, 540, 1160),
        "desc": "恭喜获得奖励页面：领取按钮",
    },
    "continue": {
        "file": "continue.png",
        "threshold": 0.86,
        "roi": (200, 1040, 530, 1200),
        "desc": "战斗结算页：继续按钮",
    },
    "back": {
        "file": "back.png",
        "threshold": 0.86,
        "roi": (510, 1180, 709, 1280),
        "desc": "右下角返回按钮",
    },

    # ===== 兑换码 =====
    "toolbox_redemption_entry": {
        "file": "toolbox_redemption_entry.png",
        "threshold": 0.78,
        "roi": (120, 380, 290, 520),
        "desc": "Yang昜工具箱首页：雷霆兑换码入口",
    },
    "toolbox_preview_close": {
        "file": "toolbox_preview_close.png",
        "threshold": 0.82,
        "roi": (30, 420, 220, 530),
        "desc": "Yang昜工具箱兑换码预览：关闭按钮",
    },
    "home_settings": {
        "file": "home_settings.png",
        "threshold": 0.86,
        "roi": (580, 950, 720, 1160),
        "grayscale": False,
        "desc": "首页右下方：设置入口",
    },
    "settings_redemption": {
        "file": "settings_redemption.png",
        "threshold": 0.86,
        "roi": (400, 680, 550, 860),
        "desc": "设置页面：兑换入口",
    },
    "redemption_input": {
        "file": "redemption_input.png",
        "threshold": 0.86,
        "roi": (100, 580, 620, 720),
        "desc": "兑换码弹窗：请输入兑换码输入框",
    },
    "redemption_code_title": {
        "file": "redemption_code_title.png",
        "threshold": 0.86,
        "roi": (250, 480, 470, 610),
        "desc": "兑换码弹窗：兑换码标题，用于向下偏移点击输入框",
    },
    "redemption_submit": {
        "file": "redemption_submit.png",
        "threshold": 0.86,
        "roi": (180, 690, 540, 830),
        "grayscale": False,
        "desc": "兑换码弹窗：绿色兑换按钮",
    },

    # ===== 微信游戏圈 =====
    "sidebar_open": {
        "file": "sidebar_open.png",
        "threshold": 0.86,
        "roi": (0, 0, 60, 60),
        "desc": "微信小游戏窗口左上角：打开侧边栏",
    },
    "sidebar_close": {
        "file": "sidebar_close.png",
        "threshold": 0.86,
        "roi": (0, 0, 60, 60),
        "desc": "微信小游戏窗口左上角：关闭侧边栏",
    },
    "sidebar_circle_tab": {
        "file": "sidebar_circle_tab.png",
        "threshold": 0.80,
        "roi": (80, 100, 170, 170),
        "desc": "微信小游戏侧边栏：游戏圈页签",
    },
    "sidebar_gift": {
        "file": "sidebar_gift.png",
        "threshold": 0.86,
        "roi": (150, 200, 260, 260),
        "desc": "游戏圈顶部：带红点的可领取礼包",
    },
    "sidebar_gift_claim_all": {
        "file": "sidebar_gift_claim_all.png",
        "threshold": 0.95,
        "roi": (290, 190, 410, 270),
        "grayscale": False,
        "desc": "微信游戏福利中心：一键领取",
    },
    "sidebar_gift_back": {
        "file": "sidebar_gift_back.png",
        "threshold": 0.86,
        "roi": (0, 40, 60, 110),
        "desc": "微信游戏福利中心左上角：返回游戏圈",
    },
    "sidebar_like": {
        "file": "sidebar_like.png",
        "threshold": 0.95,
        "roi": (0, 260, 150, 1280),
        "grayscale": False,
        "desc": "游戏圈动态：未点赞按钮",
    },
    "sidebar_comment": {
        "file": "sidebar_comment.png",
        "threshold": 0.95,
        "roi": (140, 260, 260, 1280),
        "grayscale": False,
        "desc": "游戏圈动态：评论入口",
    },
    "sidebar_comment_input": {
        "file": "sidebar_comment_input.png",
        "threshold": 0.86,
        "roi": (20, 1160, 300, 1240),
        "desc": "评论弹窗底部：评论输入框提示文字",
    },
    "sidebar_comment_send": {
        "file": "sidebar_comment_send.png",
        "threshold": 0.95,
        "roi": (320, 1160, 410, 1240),
        "grayscale": False,
        "desc": "评论弹窗底部：发送按钮",
    },
    "sidebar_comment_close": {
        "file": "sidebar_comment_close.png",
        "threshold": 0.86,
        "roi": (350, 180, 420, 930),
        "desc": "游戏圈评论弹窗右上角：关闭评论弹窗",
    },
    "community_reward_circle_claim": {
        "file": "community_reward_circle_claim.png",
        "threshold": 0.86,
        "roi": (460, 820, 640, 1040),
        "desc": "社区奖励游戏圈页：点赞或评论奖励领取按钮",
    },
    "community_reward_desktop_tab": {
        "file": "community_reward_desktop_tab.png",
        "threshold": 0.86,
        "roi": (200, 1030, 410, 1140),
        "desc": "社区奖励底部：添加桌面页签",
    },
    "community_reward_desktop_claim": {
        "file": "community_reward_desktop_claim.png",
        "threshold": 0.86,
        "roi": (230, 900, 490, 1030),
        "desc": "社区奖励添加桌面页：领取按钮",
    },

    # ===== 十年集结 =====
    "send_comment": {
        "file": "send_comment.png",
        "threshold": 0.86,
        "roi": (120, 840, 360, 970),
        "desc": "十年集结：发弹幕",
    },
    "send": {
        "file": "send.png",
        "threshold": 0.86,
        "roi": (500, 300, 670, 410),
        "desc": "十年集结：发送",
    },

    # ===== 商城礼包领取 =====
    "shop_free_resource": {
        "file": "shop_free_resource.png",
        "threshold": 0.86,
        "roi": (11, 980, 709, 1080),
        "desc": "免费资源列表：看广告领取按钮",
    },
    "shop_gift_tab": {
        "file": "shop_gift_tab.png",
        "threshold": 0.86,
        "roi": (130, 1120, 310, 1280),
        "desc": "商城底部：礼包页签",
    },
    "shop_gift_first_free": {
        "file": "shop_gift_first_free.png",
        "threshold": 0.86,
        "roi": (11, 800, 270, 970),
        "desc": "商城礼包页：第一个免费礼包卡片",
    },

    # ===== 星际探索 =====
    "star_claim": {
        "file": "star_claim.png",
        "threshold": 0.86,
        "roi": (360, 1000, 660, 1150),
        "desc": "星际探索页面底部右侧：领取按钮",
    },
    "star_claim_cd": {
        "file": "star_claim_cd.png",
        "threshold": 0.86,
        "roi": (360, 1000, 660, 1150),
        "desc": "星际探索页面底部右侧：xx分xx秒后可领取",
    },
    "star_quick": {
        "file": "star_quick.png",
        "threshold": 0.95,
        "roi": (70, 1000, 360, 1150),
        "grayscale": False,
        "desc": "星际探索页面底部左侧：快速探索按钮",
    },
    "star_quick_used_up": {
        "file": "star_quick_used_up.png",
        "threshold": 0.95,
        "roi": (70, 1000, 360, 1150),
        "grayscale": False,
        "desc": "星际探索页面底部左侧：快速探索按钮",
    },
    "quick_free_claim": {
        "file": "quick_free_claim.png",
        "threshold": 0.86,
        "roi": (200, 820, 520, 970),
        "desc": "快速探索弹窗：免费领取按钮",
    },
    "quick_ad_claim": {
        "file": "quick_ad_claim.png",
        "threshold": 0.86,
        "roi": (200, 820, 520, 970),
        "desc": "快速探索弹窗：看广告领取按钮",
    },

    # ===== 体力获取 =====
    "stamina_free": {
        "file": "stamina_free.png",
        "threshold": 0.95,
        "roi": (380, 720, 660, 850),
        "grayscale": False,
        "desc": "体力购买弹窗右侧：免费按钮",
    },
    "stamina_free_used_up": {
        "file": "stamina_free_used_up.png",
        "threshold": 0.95,
        "roi": (380, 720, 660, 850),
        "grayscale": False,
        "desc": "体力购买弹窗右侧：免费次数已用尽状态",
    },
    "friend_collect": {
        "file": "friend_collect.png",
        "threshold": 0.86,
        "roi": (330, 1120, 590, 1280),
        "desc": "好友列表底部：一键收赠按钮",
    },

    # ===== 战队征讨与捐献 =====
    "team_expedition_announced": {
        "file": "team_expedition_announced.png",
        "threshold": 0.86,
        "roi": (340, 520, 500, 560),
        "desc": "战队界面BOSS征讨：公示中",
    },
    "team_expedition_going_on": {
        "file": "team_expedition_going_on.png",
        "threshold": 0.86,
        "roi": (340, 520, 500, 560),
        "desc": "战队界面BOSS征讨：挑战中",
    },
    "team_expedition_known": {
        "file": "known.png",
        "threshold": 0.86,
        "roi": (210, 1020, 510, 1130),
        "desc": "BOSS征讨战术武装：知道了",
    },
    "team_expedition_sortie": {
        "file": "sortie.png",
        "threshold": 0.86,
        "roi": (170, 1110, 550, 1220),
        "desc": "BOSS征讨：出击",
    },
    "team_expedition_confirm": {
        "file": "team_expedition_confirm.png",
        "threshold": 0.86,
        "roi": (200, 1110, 520, 1240),
        "desc": "BOSS征讨：挑战完成",
    },
    "team_expedition_claim": {
        "file": "team_expedition_claim.png",
        "threshold": 0.86,
        "roi": (580, 960, 640, 1010),
        "desc": "BOSS征讨：今日伤害奖励",
    },
    "team_donate_entry": {
        "file": "team_donate_entry.png",
        "threshold": 0.86,
        "roi": (520, 760, 690, 910),
        "desc": "战队界面右侧：捐献入口",
    },
    "team_coin_donate": {
        "file": "team_coin_donate.png",
        "threshold": 0.86,
        "roi": (50, 870, 330, 1000),
        "desc": "战队捐献页左侧：金币2000捐献按钮",
    },
    "team_diamond_donate": {
        "file": "team_diamond_donate.png",
        "threshold": 0.86,
        "roi": (380, 870, 660, 1000),
        "desc": "战队捐献页右侧：钻石50捐献按钮",
    },
    "team_diamond_donate_confirm": {
        "file": "team_diamond_donate_confirm.png",
        "threshold": 0.86,
        "roi": (360, 700, 630, 800),
        "desc": "战队捐献：确认钻石50捐献按钮",
    },

    # ===== 背包空间处理 =====
    ## 改造
    "modification": {
        "file": "modification.png",
        "threshold": 0.86,
        "roi": (340, 1150, 570, 1245),
        "desc": "仓库右下角：改造按钮",
    },
    "automatic_synthesis": {
        "file": "automatic_synthesis.png",
        "threshold": 0.86,
        "roi": (150, 1150, 360, 1245),
        "desc": "装备合成界面左下角：自动合成按钮",
    },
    "stop_synthesis": {
        "file": "stop_synthesis.png",
        "threshold": 0.86,
        "roi": (150, 1150, 360, 1245),
        "desc": "装备合成界面左下角：停止合成按钮",
    },
    "white_equipment": {
        "file": "white_equipment.png",
        "threshold": 0.86,
        "roi": (40, 1020, 200, 1100),
        "desc": "装备合成界面：白色装备按钮",
    },
    "green_equipment": {
        "file": "green_equipment.png",
        "threshold": 0.86,
        "roi": (185, 1020, 330, 1100),
        "desc": "装备合成界面：绿色装备按钮",
    },
    "blue_equipment": {
        "file": "blue_equipment.png",
        "threshold": 0.86,
        "roi": (315, 1020, 460, 1100),
        "desc": "装备合成界面：蓝色装备按钮",
    },
    "enter_split": {
        "file": "enter_split.png",
        "threshold": 0.86,
        "roi": (11, 1170, 200, 1280),
        "desc": "装备合成界面最左下：进入拆分界面按钮",
    },
    "select_split_equipment": {
        "file": "select_split_equipment.png",
        "threshold": 0.86,
        "roi": (200, 360, 520, 630),
        "desc": "装备拆分界面：选择装备",
    },
    "blue_plus_one_equipment": {
        "file": "blue_plus_one_equipment.png",
        "threshold": 0.86,
        "roi": (300, 1070, 450, 1150),
        "desc": "装备拆分选择：蓝色+1装备按钮",
    },
    "confirm_selected_split_equipment": {
        "file": "confirm_selected_split_equipment.png",
        "threshold": 0.86,
        "roi": (530, 1070, 680, 1150),
        "desc": "装备拆分选择：确认所选的拆分装备按钮",
    },
    "split": {
        "file": "split.png",
        "threshold": 0.86,
        "roi": (180, 1140, 540, 1280),
        "desc": "装备拆分界面：拆分按钮",
    },
    "enter_synthesis": {
        "file": "enter_synthesis.png",
        "threshold": 0.86,
        "roi": (11, 1170, 200, 1280),
        "desc": "装备拆分界面最左下：进入合成界面按钮",
    },

    ## 经验合成
    "backpack": {
        "file": "backpack.png",
        "threshold": 0.86,
        "roi": (11, 1170, 200, 1280),
        "desc": "背包",
    },
    "experience_synthesis": {
        "file": "experience_synthesis.png",
        "threshold": 0.86,
        "roi": (420, 1070, 560, 1150),
        "desc": "经验合成",
    },
    "chosen": {
        "file": "chosen.png",
        "threshold": 0.95,
        "roi": (560, 850, 660, 990),
        "grayscale": False,
        "desc": "经验合成：选择合成超级强化魔方",
    },
    "not_chosen": {
        "file": "not_chosen.png",
        "threshold": 0.95,
        "roi": (560, 850, 660, 990),
        "grayscale": False,
        "desc": "经验合成：不选择合成超级强化魔方",
    },
    "not_enough_amount": {
        "file": "not_enough_amount.png",
        "threshold": 0.86,
        "roi": (560, 850, 660, 990),
        "desc": "经验合成：合成超级强化魔方所需原料数量不足",
    },
    "confirm_experience_synthesis": {
        "file": "confirm_experience_synthesis.png",
        "threshold": 0.95,
        "roi": (390, 1040, 660, 1150),
        "grayscale": False,
        "desc": "经验合成：确认合成",
    },
    "cannot_experience_synthesis": {
        "file": "cannot_experience_synthesis.png",
        "threshold": 0.95,
        "roi": (390, 1040, 660, 1150),
        "grayscale": False,
        "desc": "经验合成：数量不足，无法合成",
    },

    ## 资源出售
    "sale": {
        "file": "sale.png",
        "threshold": 0.86,
        "roi": (540, 1070, 680, 1150),
        "desc": "出售",
    },
    "quick_sale": {
        "file": "quick_sale.png",
        "threshold": 0.86,
        "roi": (300, 1070, 470, 1150),
        "desc": "资源出售：快速出售",
    },
    "immediate_sale": {
        "file": "immediate_sale.png",
        "threshold": 0.86,
        "roi": (220, 730, 500, 850),
        "desc": "资源出售：立即出售",
    },
    "sale_enabled": {
        "file": "sale_enabled.png",
        "threshold": 0.95,
        "roi": (220, 1040, 500, 1160),
        "grayscale": False,
        "desc": "资源出售：已选择对象后的出售按钮",
    },
    "resource_sale_slider_thumb": {
        "file": "resource_sale_slider_thumb.png",
        "threshold": 0.86,
        "roi": (400, 220, 640, 1020),
        "desc": "资源出售：出售数量滑条滑块",
    },
    "boss_wreck_lv1": {
        "file": "boss_wreck_lv1.png",
        "threshold": 0.958,
        "roi": (170, 220, 400, 1020),
        "desc": "资源出售：BOSS的残骸lv1",
    },
    "boss_wreck_lv2": {
        "file": "boss_wreck_lv2.png",
        "threshold": 0.958,
        "roi": (170, 220, 400, 1020),
        "desc": "资源出售：BOSS的残骸lv2",
    },
    "boss_wreck_lv3": {
        "file": "boss_wreck_lv3.png",
        "threshold": 0.958,
        "roi": (170, 220, 400, 1020),
        "desc": "资源出售：BOSS的残骸lv3",
    },
    "boss_wreck_lv4": {
        "file": "boss_wreck_lv4.png",
        "threshold": 0.958,
        "roi": (170, 220, 400, 1020),
        "desc": "资源出售：BOSS的残骸lv4",
    },
    "boss_wreck_lv5": {
        "file": "boss_wreck_lv5.png",
        "threshold": 0.958,
        "roi": (170, 220, 400, 1020),
        "desc": "资源出售：BOSS的残骸lv5",
    },
    "boss_wreck_lv6": {
        "file": "boss_wreck_lv6.png",
        "threshold": 0.958,
        "roi": (170, 220, 400, 1020),
        "desc": "资源出售：BOSS的残骸lv6",
    },
    "boss_wreck_lv7": {
        "file": "boss_wreck_lv7.png",
        "threshold": 0.958,
        "roi": (170, 220, 400, 1020),
        "desc": "资源出售：BOSS的残骸lv7",
    },
    "boss_wreck_lv8": {
        "file": "boss_wreck_lv8.png",
        "threshold": 0.958,
        "roi": (170, 220, 400, 1020),
        "desc": "资源出售：BOSS的残骸lv8",
    },
    "boss_wreck_lv9": {
        "file": "boss_wreck_lv9.png",
        "threshold": 0.958,
        "roi": (170, 220, 400, 1020),
        "desc": "资源出售：BOSS的残骸lv9",
    },
    "big_enemy_wreck_lv1": {
        "file": "big_enemy_wreck_lv1.png",
        "threshold": 0.958,
        "roi": (170, 220, 400, 1020),
        "desc": "资源出售：大敌机残骸lv1",
    },
    "big_enemy_wreck_lv2": {
        "file": "big_enemy_wreck_lv2.png",
        "threshold": 0.958,
        "roi": (170, 220, 400, 1020),
        "desc": "资源出售：大敌机残骸lv2",
    },
    "big_enemy_wreck_lv3": {
        "file": "big_enemy_wreck_lv3.png",
        "threshold": 0.958,
        "roi": (170, 220, 400, 1020),
        "desc": "资源出售：大敌机残骸lv3",
    },
    "big_enemy_wreck_lv4": {
        "file": "big_enemy_wreck_lv4.png",
        "threshold": 0.958,
        "roi": (170, 220, 400, 1020),
        "desc": "资源出售：大敌机残骸lv4",
    },
    "big_enemy_wreck_lv5": {
        "file": "big_enemy_wreck_lv5.png",
        "threshold": 0.958,
        "roi": (170, 220, 400, 1020),
        "desc": "资源出售：大敌机残骸lv5",
    },
    "big_enemy_wreck_lv6": {
        "file": "big_enemy_wreck_lv6.png",
        "threshold": 0.958,
        "roi": (170, 220, 400, 1020),
        "desc": "资源出售：大敌机残骸lv6",
    },
    "big_enemy_wreck_lv7": {
        "file": "big_enemy_wreck_lv7.png",
        "threshold": 0.958,
        "roi": (170, 220, 400, 1020),
        "desc": "资源出售：大敌机残骸lv7",
    },
    "big_enemy_wreck_lv8": {
        "file": "big_enemy_wreck_lv8.png",
        "threshold": 0.958,
        "roi": (170, 220, 400, 1020),
        "desc": "资源出售：大敌机残骸lv8",
    },
    "big_enemy_wreck_lv9": {
        "file": "big_enemy_wreck_lv9.png",
        "threshold": 0.958,
        "roi": (170, 220, 400, 1020),
        "desc": "资源出售：大敌机残骸lv9",
    },
    "small_enemy_wreck_lv1": {
        "file": "small_enemy_wreck_lv1.png",
        "threshold": 0.958,
        "roi": (170, 220, 400, 1020),
        "desc": "资源出售：小敌机残骸lv1",
    },
    "small_enemy_wreck_lv2": {
        "file": "small_enemy_wreck_lv2.png",
        "threshold": 0.958,
        "roi": (170, 220, 400, 1020),
        "desc": "资源出售：小敌机残骸lv2",
    },
    "small_enemy_wreck_lv3": {
        "file": "small_enemy_wreck_lv3.png",
        "threshold": 0.958,
        "roi": (170, 220, 400, 1020),
        "desc": "资源出售：小敌机残骸lv3",
    },
    "small_enemy_wreck_lv4": {
        "file": "small_enemy_wreck_lv4.png",
        "threshold": 0.958,
        "roi": (170, 220, 400, 1020),
        "desc": "资源出售：小敌机残骸lv4",
    },
    "small_enemy_wreck_lv5": {
        "file": "small_enemy_wreck_lv5.png",
        "threshold": 0.958,
        "roi": (170, 220, 400, 1020),
        "desc": "资源出售：小敌机残骸lv5",
    },
    "small_enemy_wreck_lv6": {
        "file": "small_enemy_wreck_lv6.png",
        "threshold": 0.958,
        "roi": (170, 220, 400, 1020),
        "desc": "资源出售：小敌机残骸lv6",
    },
    "small_enemy_wreck_lv7": {
        "file": "small_enemy_wreck_lv7.png",
        "threshold": 0.958,
        "roi": (170, 220, 400, 1020),
        "desc": "资源出售：小敌机残骸lv7",
    },
    "small_enemy_wreck_lv8": {
        "file": "small_enemy_wreck_lv8.png",
        "threshold": 0.958,
        "roi": (170, 220, 400, 1020),
        "desc": "资源出售：小敌机残骸lv8",
    },
    "small_enemy_wreck_lv9": {
        "file": "small_enemy_wreck_lv9.png",
        "threshold": 0.958,
        "roi": (170, 220, 400, 1020),
        "desc": "资源出售：小敌机残骸lv9",
    },

    # ===== 夺宝领取 =====
    "treasure_hunt_free_chest": {
        "file": "treasure_hunt_free_chest.png",
        "threshold": 0.86,
        "roi": (11, 980, 530, 1180),
        "desc": "寻宝页面：转盘按钮",
    },
    "treasure_hunt_wheel": {
        "file": "treasure_hunt_wheel.png",
        "threshold": 0.86,
        "roi": (130, 1120, 310, 1280),
        "desc": "寻宝页面：转盘按钮",
    },
    "treasure_hunt_redeem": {
        "file": "treasure_hunt_redeem.png",
        "threshold": 0.86,
        "roi": (260, 1120, 440, 1280),
        "desc": "寻宝页面：兑换按钮",
    },
    "wheel_first_free": {
        "file": "wheel_first_free.png",
        "threshold": 0.86,
        "roi": (220, 610, 500, 720),
        "desc": "寻宝转盘页面：每日首次免费",
    },
    "claim_star": {
        "file": "claim_star.png",
        "threshold": 0.86,
        "roi": (320, 310, 460, 440),
        "desc": "星辉领取",
    },

    # ===== 活动关卡 =====
    "challenge_event_stage": {
        "file": "challenge_event_stage.png",
        "threshold": 0.86,
        "roi": (320, 1120, 590, 1260),
        "desc": "闯关模式底部：活动关卡入口",
    },
    "event_stage_meteor_blitz": {
        "file": "event_stage_meteor_blitz.png",
        "threshold": 0.86,
        "roi": (390, 430, 570, 550),
        "desc": "活动关卡：陨石陷阱闪击按钮",
    },

    # ===== 关卡扫荡 =====
    "challenge_starry_ladder": {
        "file": "challenge_starry_ladder.png",
        "threshold": 0.82,
        "roi": (520, 430, 710, 550),
        "desc": "闯关模式：逐星长阶入口",
    },
    "challenge_quick_sweep": {
        "file": "challenge_quick_sweep.png",
        "threshold": 0.86,
        "roi": (0, 1050, 180, 1160),
        "desc": "闯关模式：快速扫荡入口",
    },
    "starry_ladder_beacon": {
        "file": "starry_ladder_beacon.png",
        "threshold": 0.80, # 动画有跳动，降低阈值
        "roi": (280, 760, 450, 910),
        "desc": "逐星长阶：开始挑战上方逐星信标",
    },
    "starry_ladder_supply": {
        "file": "starry_ladder_supply.png",
        "threshold": 0.86,
        "roi": (40, 760, 190, 930),
        "desc": "逐星长阶：逐星补给入口",
    },
    "starry_ladder_supply_claim_5": {
        "file": "starry_ladder_supply_claim_5.png",
        "threshold": 0.86,
        "roi": (370, 780, 640, 900),
        "desc": "逐星补给：领5次",
    },
    "quick_sweep_double_reward": {
        "file": "quick_sweep_double_reward.png",
        "threshold": 0.86,
        "roi": (220, 800, 500, 920),
        "desc": "快速扫荡完成：双倍奖励",
    },
    "quick_sweep_hero_tab": {
        "file": "quick_sweep_hero_tab.png",
        "threshold": 0.82,
        "roi": (520, 1110, 690, 1200),
        "desc": "快速扫荡：英雄难度切换",
    },
    "quick_sweep_sweep_button": {
        "file": "quick_sweep_sweep_button.png",
        "threshold": 0.86,
        "roi": (470, 360, 670, 1120),
        "grayscale": False,
        "desc": "快速扫荡：关卡行右侧扫荡按钮",
    },
    # "quick_sweep_sweep_button_used_up": {
    #     "file": "quick_sweep_sweep_button_used_up.png",
    #     "threshold": 0.86,
    #     "roi": (470, 360, 670, 1120),
    #     "grayscale": False,
    #     "desc": "快速扫荡：关卡行右侧次数用尽的灰色扫荡按钮",
    # },
    "quick_sweep_normal_138": {
        "file": "quick_sweep_normal_138.png",
        "threshold": 0.90,
        "roi": (50, 360, 430, 1120),
        "desc": "快速扫荡普通难度：第138关",
    },
    "quick_sweep_normal_134": {
        "file": "quick_sweep_normal_134.png",
        "threshold": 0.90,
        "roi": (50, 360, 430, 1120),
        "desc": "快速扫荡普通难度：第134关",
    },
    "quick_sweep_normal_128": {
        "file": "quick_sweep_normal_128.png",
        "threshold": 0.90,
        "roi": (50, 360, 430, 1120),
        "desc": "快速扫荡普通难度：第128关",
    },
    "quick_sweep_normal_124": {
        "file": "quick_sweep_normal_124.png",
        "threshold": 0.90,
        "roi": (50, 360, 430, 1120),
        "desc": "快速扫荡普通难度：第124关",
    },
    "quick_sweep_normal_118": {
        "file": "quick_sweep_normal_118.png",
        "threshold": 0.90,
        "roi": (50, 360, 430, 1120),
        "desc": "快速扫荡普通难度：第118关",
    },
    "quick_sweep_normal_114": {
        "file": "quick_sweep_normal_114.png",
        "threshold": 0.90,
        "roi": (50, 360, 430, 1120),
        "desc": "快速扫荡普通难度：第114关",
    },
    "quick_sweep_normal_104": {
        "file": "quick_sweep_normal_104.png",
        "threshold": 0.90,
        "roi": (50, 360, 430, 1120),
        "desc": "快速扫荡普通难度：第104关",
    },
    "quick_sweep_normal_100": {
        "file": "quick_sweep_normal_100.png",
        "threshold": 0.90,
        "roi": (50, 360, 430, 1120),
        "desc": "快速扫荡普通难度：第100关",
    },
    "quick_sweep_normal_94": {
        "file": "quick_sweep_normal_94.png",
        "threshold": 0.90,
        "roi": (50, 360, 430, 1120),
        "desc": "快速扫荡普通难度：第94关",
    },
    "quick_sweep_hero_35": {
        "file": "quick_sweep_hero_35.png",
        "threshold": 0.90,
        "roi": (50, 360, 430, 1120),
        "desc": "快速扫荡英雄难度：第35关",
    },
    "quick_sweep_hero_34": {
        "file": "quick_sweep_hero_34.png",
        "threshold": 0.90,
        "roi": (50, 360, 430, 1120),
        "desc": "快速扫荡英雄难度：第34关",
    },
    "quick_sweep_hero_33": {
        "file": "quick_sweep_hero_33.png",
        "threshold": 0.90,
        "roi": (50, 360, 430, 1120),
        "desc": "快速扫荡英雄难度：第33关",
    },
    "quick_sweep_hero_32": {
        "file": "quick_sweep_hero_32.png",
        "threshold": 0.90,
        "roi": (50, 360, 430, 1120),
        "desc": "快速扫荡英雄难度：第32关",
    },
    "quick_sweep_hero_31": {
        "file": "quick_sweep_hero_31.png",
        "threshold": 0.90,
        "roi": (50, 360, 430, 1120),
        "desc": "快速扫荡英雄难度：第31关",
    },
    "quick_sweep_hero_30": {
        "file": "quick_sweep_hero_30.png",
        "threshold": 0.90,
        "roi": (50, 360, 430, 1120),
        "desc": "快速扫荡英雄难度：第30关",
    },
    "quick_sweep_hero_29": {
        "file": "quick_sweep_hero_29.png",
        "threshold": 0.90,
        "roi": (50, 360, 430, 1120),
        "desc": "快速扫荡英雄难度：第29关",
    },
    "quick_sweep_hero_28": {
        "file": "quick_sweep_hero_28.png",
        "threshold": 0.90,
        "roi": (50, 360, 430, 1120),
        "desc": "快速扫荡英雄难度：第28关",
    },
    "quick_sweep_hero_27": {
        "file": "quick_sweep_hero_27.png",
        "threshold": 0.90,
        "roi": (50, 360, 430, 1120),
        "desc": "快速扫荡英雄难度：第27关",
    },
    "quick_sweep_hero_26": {
        "file": "quick_sweep_hero_26.png",
        "threshold": 0.90,
        "roi": (50, 360, 430, 1120),
        "desc": "快速扫荡英雄难度：第26关",
    },
    "quick_sweep_hero_25": {
        "file": "quick_sweep_hero_25.png",
        "threshold": 0.90,
        "roi": (50, 360, 430, 1120),
        "desc": "快速扫荡英雄难度：第25关",
    },
    "quick_sweep_hero_24": {
        "file": "quick_sweep_hero_24.png",
        "threshold": 0.90,
        "roi": (50, 360, 430, 1120),
        "desc": "快速扫荡英雄难度：第24关",
    },
    "quick_sweep_hero_23": {
        "file": "quick_sweep_hero_23.png",
        "threshold": 0.90,
        "roi": (50, 360, 430, 1120),
        "desc": "快速扫荡英雄难度：第23关",
    },
    "quick_sweep_hero_22": {
        "file": "quick_sweep_hero_22.png",
        "threshold": 0.90,
        "roi": (50, 360, 430, 1120),
        "desc": "快速扫荡英雄难度：第22关",
    },
    "quick_sweep_hero_21": {
        "file": "quick_sweep_hero_21.png",
        "threshold": 0.90,
        "roi": (50, 360, 430, 1120),
        "desc": "快速扫荡英雄难度：第21关",
    },
    "quick_sweep_hero_20": {
        "file": "quick_sweep_hero_20.png",
        "threshold": 0.90,
        "roi": (50, 360, 430, 1120),
        "desc": "快速扫荡英雄难度：第20关",
    },
    "quick_sweep_hero_19": {
        "file": "quick_sweep_hero_19.png",
        "threshold": 0.90,
        "roi": (50, 360, 430, 1120),
        "desc": "快速扫荡英雄难度：第19关",
    },
    "quick_sweep_hero_18": {
        "file": "quick_sweep_hero_18.png",
        "threshold": 0.90,
        "roi": (50, 360, 430, 1120),
        "desc": "快速扫荡英雄难度：第18关",
    },
    "quick_sweep_hero_17": {
        "file": "quick_sweep_hero_17.png",
        "threshold": 0.90,
        "roi": (50, 360, 430, 1120),
        "desc": "快速扫荡英雄难度：第17关",
    },
    "quick_sweep_hero_16": {
        "file": "quick_sweep_hero_16.png",
        "threshold": 0.90,
        "roi": (50, 360, 430, 1120),
        "desc": "快速扫荡英雄难度：第16关",
    },
    "quick_sweep_hero_15": {
        "file": "quick_sweep_hero_15.png",
        "threshold": 0.90,
        "roi": (50, 360, 430, 1120),
        "desc": "快速扫荡英雄难度：第15关",
    },
    "quick_sweep_hero_14": {
        "file": "quick_sweep_hero_14.png",
        "threshold": 0.90,
        "roi": (50, 360, 430, 1120),
        "desc": "快速扫荡英雄难度：第14关",
    },
    "quick_sweep_hero_13": {
        "file": "quick_sweep_hero_13.png",
        "threshold": 0.90,
        "roi": (50, 360, 430, 1120),
        "desc": "快速扫荡英雄难度：第13关",
    },
    "quick_sweep_hero_12": {
        "file": "quick_sweep_hero_12.png",
        "threshold": 0.90,
        "roi": (50, 360, 430, 1120),
        "desc": "快速扫荡英雄难度：第12关",
    },
    "quick_sweep_hero_11": {
        "file": "quick_sweep_hero_11.png",
        "threshold": 0.90,
        "roi": (50, 360, 430, 1120),
        "desc": "快速扫荡英雄难度：第11关",
    },
    "quick_sweep_hero_10": {
        "file": "quick_sweep_hero_10.png",
        "threshold": 0.90,
        "roi": (50, 360, 430, 1120),
        "desc": "快速扫荡英雄难度：第10关",
    },
    "quick_sweep_hero_9": {
        "file": "quick_sweep_hero_9.png",
        "threshold": 0.90,
        "roi": (50, 360, 430, 1120),
        "desc": "快速扫荡英雄难度：第9关",
    },
    "quick_sweep_hero_8": {
        "file": "quick_sweep_hero_8.png",
        "threshold": 0.90,
        "roi": (50, 360, 430, 1120),
        "desc": "快速扫荡英雄难度：第8关",
    },
    "quick_sweep_hero_7": {
        "file": "quick_sweep_hero_7.png",
        "threshold": 0.90,
        "roi": (50, 360, 430, 1120),
        "desc": "快速扫荡英雄难度：第7关",
    },
    "quick_sweep_hero_6": {
        "file": "quick_sweep_hero_6.png",
        "threshold": 0.90,
        "roi": (50, 360, 430, 1120),
        "desc": "快速扫荡英雄难度：第6关",
    },
    "quick_sweep_hero_5": {
        "file": "quick_sweep_hero_5.png",
        "threshold": 0.90,
        "roi": (50, 360, 430, 1120),
        "desc": "快速扫荡英雄难度：第5关",
    },
    "quick_sweep_hero_4": {
        "file": "quick_sweep_hero_4.png",
        "threshold": 0.90,
        "roi": (50, 360, 430, 1120),
        "desc": "快速扫荡英雄难度：第4关",
    },
    "quick_sweep_hero_3": {
        "file": "quick_sweep_hero_3.png",
        "threshold": 0.90,
        "roi": (50, 360, 430, 1120),
        "desc": "快速扫荡英雄难度：第3关",
    },
    "quick_sweep_hero_2": {
        "file": "quick_sweep_hero_2.png",
        "threshold": 0.90,
        "roi": (50, 360, 430, 1120),
        "desc": "快速扫荡英雄难度：第2关",
    },
    "quick_sweep_hero_1": {
        "file": "quick_sweep_hero_1.png",
        "threshold": 0.90,
        "roi": (50, 360, 430, 1120),
        "desc": "快速扫荡英雄难度：第1关",
    },

    # ===== BOSS模式 =====
    "challenge_boss_mode": {
        "file": "challenge_boss_mode.png",
        "threshold": 0.86,
        "roi": (130, 1100, 390, 1260),
        "desc": "闯关模式底部：BOSS模式入口",
    },
    "boss_mode_board_draco": {
        "file": "boss_mode_board_draco.png",
        "threshold": 0.86,
        "roi": (45, 450, 360, 570),
        "desc": "BOSS模式：天龙座空间站",
    },
    "boss_mode_board_cygnus": {
        "file": "boss_mode_board_cygnus.png",
        "threshold": 0.86,
        "roi": (370, 595, 700, 720),
        "desc": "BOSS模式：白鸟座空间站",
    },
    "boss_mode_board_pegasus": {
        "file": "boss_mode_board_pegasus.png",
        "threshold": 0.86,
        "roi": (40, 860, 360, 985),
        "desc": "BOSS模式：天马座空间站",
    },
    "boss_mode_board_andromeda": {
        "file": "boss_mode_board_andromeda.png",
        "threshold": 0.86,
        "roi": (360, 995, 705, 1125),
        "desc": "BOSS模式：仙女座空间站",
    },
    "boss_mode_enemy_power_extreme": {
        "file": "boss_mode_enemy_power_extreme.png",
        "threshold": 0.86,
        "roi": (170, 910, 270, 955),
        "desc": "BOSS模式：极难难度敌方战力15682",
    },
    "high_energy_bomb": {
        "file": "high_energy_bomb.png",
        "threshold": 0.82,
        "roi": (0, 980, 180, 1180),
        "grayscale": False,
        "desc": "战斗页左下角：高能爆弹按钮",
    },

    # ===== 普通星域巡航与深空巡航 =====
    "challenge_deep_space_cruise": {
        "file": "challenge_deep_space_cruise.png",
        "threshold": 0.86,
        "roi": (500, 300, 660, 450),
        "grayscale": False,
        "desc": "闯关模式右上：巡航入口",
    },
    "expedition_page": {
        "file": "expedition_page.png",
        "threshold": 0.90,
        "roi": (150, 40, 450, 130),
        "desc": "普通星域巡航：本期巡航剩余时间静态标题（不含动态倒计时）",
    },
    "expedition_agent": {
        "file": "expedition_agent.png",
        "threshold": 0.86,
        "roi": (0, 970, 200, 1080),
        "desc": "普通星域巡航左下：作战代理",
    },
    "expedition_available_enemy": {
        "file": "expedition_available_enemy.png",
        "threshold": 0.90,
        "roi": (0, 300, 720, 1120),
        "grayscale": False,
        "desc": "普通星域巡航地图：任意可挑战节点的蓝色目标台",
    },
    "expedition_available_enemy_right": {
        "file": "expedition_available_enemy_right.png",
        "threshold": 0.90,
        "roi": (530, 810, 690, 950),
        "grayscale": False,
        "desc": "普通星域巡航地图右下：动态节点视觉模板",
    },
    "expedition_enemy": {
        "file": "expedition_enemy.png",
        "threshold": 0.86,
        "roi": (20, 160, 330, 340),
        "desc": "普通星域巡航敌人详情：一组敌机与推荐战力（仅用于调试）",
    },
    "expedition_challenge": {
        "file": "expedition_challenge.png",
        "threshold": 0.86,
        "roi": (260, 1060, 460, 1180),
        "grayscale": False,
        "desc": "普通星域巡航敌人详情：挑战按钮",
    },
    "expedition_force_challenge_confirm": {
        "file": "expedition_force_challenge_confirm.png",
        "threshold": 0.90,
        "roi": (420, 630, 580, 760),
        "grayscale": False,
        "desc": "普通星域巡航低战力提示：确认强制挑战（不消耗资源）",
    },
    "cruise_revive_close": {
        "file": "cruise_revive_close.png",
        "threshold": 0.90,
        "roi": (550, 540, 660, 640),
        "grayscale": False,
        "desc": "巡航战斗坠机弹窗：关闭按钮",
    },
    "cruise_ad_revive": {
        "file": "cruise_ad_revive.png",
        "threshold": 0.90,
        "roi": (400, 620, 580, 740),
        "grayscale": False,
        "desc": "巡航战斗坠机弹窗：广告复活按钮",
    },
    "cruise_result_continue": {
        "file": "cruise_result_continue.png",
        "threshold": 0.90,
        "roi": (270, 1050, 450, 1190),
        "grayscale": False,
        "desc": "巡航通用结算：继续按钮",
    },
    "cruise_result_victory": {
        "file": "cruise_result_victory.png",
        "threshold": 0.94,
        "roi": (500, 920, 700, 1040),
        "grayscale": False,
        "desc": "普通星域巡航胜利结算：右侧空白区",
    },
    "cruise_result_defeat": {
        "file": "cruise_result_defeat.png",
        "threshold": 0.94,
        "roi": (500, 920, 700, 1040),
        "grayscale": False,
        "desc": "普通星域巡航失败结算：强化提示",
    },
    "expedition_equation_page": {
        "file": "expedition_equation_page.png",
        "threshold": 0.86,
        "roi": (170, 250, 550, 370),
        "desc": "普通星域巡航胜利后：选择增益方程",
    },
    "expedition_equation_middle": {
        "file": "expedition_equation_middle.png",
        "threshold": 0.86,
        "roi": (220, 420, 510, 880),
        "grayscale": False,
        "desc": "普通星域巡航：一组中间增益方程卡片（仅用于调试）",
    },
    "deep_space_cruise_entry": {
        "file": "deep_space_cruise_entry.png",
        "threshold": 0.78,
        "roi": (80, 500, 640, 860),
        "grayscale": False,
        "desc": "普通星域巡航完成后：真正深空巡航入口",
    },
    "deep_space_cruise_page": {
        "file": "deep_space_cruise_page.png",
        "threshold": 0.78,
        "roi": (100, 40, 620, 230),
        "grayscale": False,
        "desc": "真正深空巡航页面静态标志",
    },
    "deep_space_cruise_sortie": {
        "file": "deep_space_cruise_sortie.png",
        "threshold": 0.86,
        "roi": (190, 1140, 540, 1270),
        "grayscale": False,
        "desc": "真正深空巡航底部出击按钮",
    },
    "deep_space_cruise_info_close": {
        "file": "deep_space_cruise_info_close.png",
        "threshold": 0.86,
        "roi": (580, 190, 715, 300),
        "grayscale": False,
        "desc": "真正深空巡航首次规则弹窗关闭按钮",
    },

    # ===== 超限模式 =====
    "boss_mode_overlimit_entry": {
        "file": "boss_mode_overlimit_entry.png",
        "threshold": 0.86,
        "roi": (200, 1120, 520, 1260),
        "grayscale": False,
        "desc": "BOSS模式底部：超限模式入口",
    },
    "overlimit_mode_page": {
        "file": "overlimit_mode_page.png",
        "threshold": 0.86,
        "roi": (180, 210, 540, 340),
        "grayscale": False,
        "desc": "超限模式：页面标题与活动时间",
    },
    "overlimit_mode_board_draco": {
        "file": "overlimit_mode_board_draco.png",
        "threshold": 0.86,
        "roi": (80, 430, 370, 620),
        "desc": "超限模式：天龙座空间站",
    },
    "overlimit_mode_board_cygnus": {
        "file": "overlimit_mode_board_cygnus.png",
        "threshold": 0.86,
        "roi": (410, 590, 700, 770),
        "desc": "超限模式：白鸟座空间站",
    },
    "overlimit_mode_board_pegasus": {
        "file": "overlimit_mode_board_pegasus.png",
        "threshold": 0.86,
        "roi": (70, 840, 370, 1030),
        "desc": "超限模式：天马座空间站",
    },
    "overlimit_mode_board_andromeda": {
        "file": "overlimit_mode_board_andromeda.png",
        "threshold": 0.86,
        "roi": (400, 970, 700, 1160),
        "desc": "超限模式：仙女座空间站",
    },
    "overlimit_mode_stage_page": {
        "file": "overlimit_mode_stage_page.png",
        "threshold": 0.86,
        "roi": (60, 230, 400, 330),
        "desc": "超限模式：特定未完成 BOSS 标题（兼容旧模板）",
    },
    "overlimit_mode_stage_prev": {
        "file": "boss_mode_difficulty_prev.png",
        "threshold": 0.84,
        "roi": (0, 400, 100, 900),
        "grayscale": False,
        "desc": "超限模式：上一个 BOSS 黄色左箭头",
    },
    "overlimit_mode_stage_next": {
        "file": "overlimit_mode_stage_next.png",
        "threshold": 0.84,
        "roi": (620, 400, 720, 900),
        "grayscale": False,
        "desc": "超限模式：下一个 BOSS 黄色右箭头",
    },
    "overlimit_mode_normal_cleared": {
        "file": "overlimit_mode_normal_cleared.png",
        "threshold": 0.94,
        "roi": (200, 220, 430, 340),
        "grayscale": False,
        "desc": "超限模式：普通挑战已通关",
    },
    "overlimit_mode_ranking_closed": {
        "file": "overlimit_mode_challenge_ended.png",
        "threshold": 0.90,
        "roi": (25, 505, 180, 560),
        "grayscale": False,
        "desc": "超限模式：排行榜已截止（仍可挑战领奖）",
    },
    "overlimit_mode_normal_challenge": {
        "file": "overlimit_mode_normal_challenge.png",
        "threshold": 0.86,
        "roi": (80, 840, 300, 970),
        "grayscale": False,
        "desc": "超限模式：普通挑战按钮",
    },
    "overlimit_mode_overlimit_challenge": {
        "file": "overlimit_mode_overlimit_challenge.png",
        "threshold": 0.86,
        "roi": (420, 840, 670, 970),
        "grayscale": False,
        "desc": "超限模式：超限挑战按钮",
    },
    "overlimit_mode_overlimit_dialog": {
        "file": "overlimit_mode_overlimit_dialog.png",
        "threshold": 0.86,
        "roi": (240, 390, 480, 500),
        "desc": "超限模式：超限挑战确认弹窗",
    },
    "overlimit_mode_start_challenge": {
        "file": "overlimit_mode_start_challenge.png",
        "threshold": 0.86,
        "roi": (280, 750, 450, 880),
        # 真实 MAX 购买前后弹窗会改变周边色彩，灰度匹配更稳定。
        "grayscale": True,
        "desc": "超限模式：确认弹窗挑战按钮",
    },
    "overlimit_mode_crystal_invalid": {
        "file": "overlimit_mode_crystal_invalid.png",
        "threshold": 0.90,
        "roi": (250, 470, 520, 570),
        "grayscale": False,
        "desc": "超限模式：预设原晶失效弹窗标题",
    },
    "overlimit_mode_continue_battle": {
        "file": "overlimit_mode_continue_battle.png",
        "threshold": 0.90,
        "roi": (400, 750, 610, 880),
        "grayscale": False,
        "desc": "超限模式：预设原晶失效弹窗继续战斗按钮",
    },
    "overlimit_mode_revive_close": {
        "file": "overlimit_mode_revive_close.png",
        "threshold": 0.90,
        "roi": (550, 540, 660, 640),
        "grayscale": False,
        "desc": "超限模式坠机弹窗：关闭按钮",
    },
    "overlimit_mode_ad_revive": {
        "file": "overlimit_mode_ad_revive.png",
        "threshold": 0.90,
        "roi": (400, 620, 580, 740),
        "grayscale": False,
        "desc": "超限模式坠机弹窗：广告复活按钮",
    },
    "overlimit_mode_result_continue": {
        "file": "overlimit_mode_result_continue.png",
        "threshold": 0.90,
        "roi": (270, 1050, 450, 1190),
        "grayscale": False,
        "desc": "超限模式结算：继续按钮",
    },

    # ===== 无尽模式 =====
    "endless_mode_known": {
        "file": "known.png",
        "threshold": 0.86,
        "roi": (210, 840, 510, 990),
        "desc": "BOSS征讨战术武装：知道了",
    },
    "endless_world_competition": {
        "file": "endless_world_competition.png",
        "threshold": 0.86,
        "roi": (330, 1120, 600, 1260),
        "desc": "无尽模式底部：世界竞赛",
    },
    "endless_entry_diamond_20": {
        "file": "endless_entry_diamond_20.png",
        "threshold": 0.86,
        "roi": (380, 620, 670, 760),
        "desc": "无尽模式世界竞赛：参赛钻石20",
    },
    "endless_sortie": {
        "file": "sortie.png",
        "threshold": 0.86,
        "roi": (180, 1120, 540, 1260),
        "desc": "无尽模式助战机选择：出击",
    },
    "endless_fire_buy_200": {
        "file": "endless_fire_buy_200.png",
        "threshold": 0.86,
        "roi": (500, 520, 700, 670),
        "desc": "无尽模式战前准备：购买烈火金币200",
    },
    "endless_chest_1": {
        "file": "endless_chest_1.png",
        "threshold": 0.86,
        "roi": (390, 35, 530, 90),
        "desc": "无尽模式战斗顶部：宝箱x1",
    },
    "endless_chest_2": {
        "file": "endless_chest_2.png",
        "threshold": 0.86,
        "roi": (390, 35, 530, 90),
        "desc": "无尽模式战斗顶部：宝箱x2",
    },
    "endless_chest_3": {
        "file": "endless_chest_3.png",
        "threshold": 0.86,
        "roi": (390, 35, 530, 90),
        "desc": "无尽模式战斗顶部：宝箱x3",
    },
    "endless_chest_4": {
        "file": "endless_chest_4.png",
        "threshold": 0.86,
        "roi": (390, 35, 530, 90),
        "desc": "无尽模式战斗顶部：宝箱x4",
    },
    "endless_chest_5": {
        "file": "endless_chest_5.png",
        "threshold": 0.86,
        "roi": (390, 35, 530, 90),
        "desc": "无尽模式战斗顶部：宝箱x5",
    },
    "endless_chest_6": {
        "file": "endless_chest_6.png",
        "threshold": 0.86,
        "roi": (390, 35, 530, 90),
        "desc": "无尽模式战斗顶部：宝箱x6",
    },

    # ===== 消息、活跃度、奖励领取 =====
    "home_information_assist_battle": {
        "file": "home_information_assist_battle.png",
        "threshold": 0.86,
        "roi": (11, 1030, 170, 1160),
        "desc": "消息页面：助战",
    },
    "home_information_system": {
        "file": "home_information_system.png",
        "threshold": 0.86,
        "roi": (170, 1030, 360, 1160),
        "desc": "消息页面：系统",
    },
    "home_information_claim_all": {
        "file": "home_information_claim_all.png",
        "threshold": 0.86,
        "roi": (420, 1030, 700, 1160),
        "desc": "消息页面：全部领取",
    },
    "activity_claim_all": {
        "file": "activity_claim_all.png",
        "threshold": 0.86,
        "roi": (520, 430, 680, 540),
        "desc": "活跃任务页面：一键领取",
    },
    "home_reward_claim": {
        "file": "home_reward_claim.png",
        "threshold": 0.86,
        "roi": (520, 250, 680, 360),
        "desc": "奖励页面：第一个领取按钮",
    },

}

# Yang昜工具箱固定坐标配置，坐标基于 414x780 客户区截图。
TOOLBOX_POSITION_SPECS = {
    "first_code": {
        "pos": (100, 228),
        "desc": "兑换码列表第一条",
    },
    "code_text": {
        "pos": (180, 286),
        "desc": "兑换码预览弹窗中的兑换码文本",
    },
    "close_window": {
        "pos": (385, 42),
        "desc": "窗口右上角圆形关闭按钮",
    },
}

# 固定点击坐标配置。
POSITION_SPECS = {
    "exit_mid_down": {
        # exit_mid_down无法使用的场景：

        # 奖励领取时，必须点击 领取 按钮；
        # 战队征讨出现本期战术武装时，必须点击 知道了 按钮。
        # 装备合成和拆分时，必须点击 确定/取消 按钮。
        # 无尽限时小组赛界面，必须点击 叉 按钮。
        # 无尽模式本周超频装备，必须点击 知道了 按钮。
        "pos": (360, 1260),
        "desc": "点击屏幕中下方空白区域，用于退出弹窗/返回上一层",
    },
    "ad_close": {
        "pos": (683, 76),
        "desc": "广告页右上角关闭位置",
    },
    "boss_mode_difficulty_prev": {
        "pos": (35, 575),
        "desc": "BOSS模式：左侧黄色难度切换按钮",
    },
    "open_chest": {
        "pos": (360, 940),
        "desc": "点击打开装备宝箱",
    },
    # "home_decade_reunion": {
    #     "pos": (600, 280),
    #     "desc": "十年集结固定点击入口",# 由于此处一直有动画，不便于做识别
    # },
}
