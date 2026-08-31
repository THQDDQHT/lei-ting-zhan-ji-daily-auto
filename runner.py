from __future__ import annotations

import argparse
import logging
import re
import time
from datetime import datetime
from enum import Enum
from functools import lru_cache
from pathlib import Path
from typing import Optional

from windows_controller import WindowsController
from config import (
    DEFAULT_CAPTURE_METHOD,
    DEFAULT_CLICK_METHOD,
    DEFAULT_ENABLE_RESOURCE_SALE,
    DEFAULT_SAVE_LOGS,
    DEFAULT_SAVE_SCREENSHOTS,
    DEFAULT_TOOLBOX_WINDOW_TITLE,
    DEFAULT_WINDOW_TITLE,
    TARGET_CLIENT_WIDTH,
    TARGET_CLIENT_HEIGHT,
    TOOLBOX_CLIENT_HEIGHT,
    TOOLBOX_CLIENT_WIDTH,
    DEFAULT_FORCE_CLIENT_SIZE,
    DEEP_SPACE_CRUISE_CONFIG,
    OVERLIMIT_MODE_CONFIG,
    LEVEL_SWEEP_PLAN,
    RESOURCE_SALE_WRECKS,
    POSITION_SPECS,
    TOOLBOX_POSITION_SPECS,
    LOG_DIR,
    RUNTIME_DIR,
    SCREENSHOT_DIR,
    TEMPLATE_DIR,
    TEMPLATE_SPECS,
)
from vision import TemplateMatcher, MatchResult


class BattleResult(str, Enum):
    VICTORY = "victory"
    DEFEAT = "defeat"
    # 只表示结算继续按钮已确认；未匹配到胜负模板时不能据此推断胜利。
    COMPLETE = "complete"


class DailyFlowRunner:

    def __init__(
        self,
        game_controller: WindowsController,
        toolbox_controller: Optional[WindowsController],
        sections: Optional[list[str]] = None,
        save_screenshots: bool = DEFAULT_SAVE_SCREENSHOTS,
        enable_resource_sale: bool = DEFAULT_ENABLE_RESOURCE_SALE,
    ):
        self.ctrl = game_controller
        self.toolbox_ctrl = toolbox_controller
        self.save_screenshots = save_screenshots
        self.enable_resource_sale = enable_resource_sale
        self.matcher = TemplateMatcher(grayscale=True)
        self.level_sweep_swept_count = 0
        self.level_sweep_periodic_reward_claimed = False
        self.level_sweep_double_reward_counts = {"normal": 0, "hero": 0}
        self.sections = sections or [
            "redemption_code",
            "game_circle",
            "decade_reunion",
            "shop",
            "interstellar",
            "stamina",
            "team",
            "backpack",
            "treasure_hunt",
            "event_stage",
            "level_sweep",
            "boss_mode",
            "endless_mode",
            "daily_rewards",
        ]

    def _screenshot_path(self, tag: str) -> Path:
        if self.save_screenshots:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
            return SCREENSHOT_DIR / f"{timestamp}_{tag}.png"
        return RUNTIME_DIR / "current_screenshot.png"

    def screenshot(self, tag: str) -> Path:
        return self.ctrl.screenshot(self._screenshot_path(tag))

    def _require_toolbox_controller(self) -> WindowsController:
        if self.toolbox_ctrl is None:
            raise RuntimeError("兑换码流程需要先打开 Yang昜工具箱 窗口")
        return self.toolbox_ctrl

    def toolbox_screenshot(self, tag: str) -> Path:
        return self._require_toolbox_controller().screenshot(self._screenshot_path(tag))

    def _template_spec(self, name: str) -> dict:
        if name not in TEMPLATE_SPECS:
            raise KeyError(f"未知模板: {name}")
        return TEMPLATE_SPECS[name]

    def match(
        self,
        name: str,
        screenshot: Optional[Path] = None,
        roi: Optional[tuple[int, int, int, int]] = None,
    ) -> MatchResult:
        """对指定截图执行一次模板匹配，不负责重试，也不点击。

        这是底层识别函数：
        - 如果传入 screenshot，就在该截图上识别；
        - 如果不传入 screenshot，就自动截一张当前窗口图再识别。
        """
        spec = self._template_spec(name)
        screenshot = screenshot or self.screenshot(f"match_{name}")
        template_path = TEMPLATE_DIR / spec["file"]
        grayscale = spec.get("grayscale", True)
        res = self.matcher.match(
            screenshot_path=screenshot,
            template_path=template_path,
            threshold=spec["threshold"],
            roi=roi if roi is not None else spec.get("roi"),
            grayscale=grayscale,
        )
        mode = "gray" if grayscale else "color"
        logging.info(
            "识别 %-18s found=%s score=%.3f center=(%.1f, %.1f) mode=%s desc=%s",
            name, res.found, res.score, res.x, res.y, mode, spec.get("desc", "")
        )
        return res

    def wait_until_not_loading(
        self,
        retries: int = 5,
        interval: float = 8.8,
        settle_seconds: float = 0.9,
        loading_template: str = "loading",
    ) -> Path:
        """等待游戏画面脱离 loading 状态，并在短暂切换动画后重新截图。

        click_template 会先调用该方法。若首次检测不是 loading，会等待 settle_seconds 后重新截图；
        若处于 loading，则按 retries/interval 循环检测，超出次数仍未结束时抛出异常。
        返回确认不处于 loading 状态且等待稳定后的截图。
        """
        for attempt in range(1, retries + 1):
            shot = self.screenshot(f"loading_check_{attempt}")
            loading = self.match(loading_template, shot)
            if not loading.found:
                # if attempt == 1:
                #     logging.info("当前画面未处于 loading 状态")
                # else:
                #     logging.info("loading 已结束，attempt=%d", attempt)
                if attempt > 1:
                    logging.info("loading 已结束，attempt=%d", attempt)
                if settle_seconds > 0:
                    time.sleep(settle_seconds)
                    return self.screenshot(f"post_loading_settle_{attempt}")
                return shot

            logging.info(
                "检测到 %s 加载状态，attempt=%d/%d score=%.3f",
                loading_template,
                attempt,
                retries,
                loading.score,
            )
            if attempt < retries:
                time.sleep(interval)

        msg = f"连续 {retries} 次检测仍处于加载状态，loading_template={loading_template}"
        logging.error(msg)
        raise RuntimeError(msg)
    
    def recognize_template(
        self,
        name: str,
        required: bool = True,
        roi: Optional[tuple[int, int, int, int]] = None,
        retries: int = 5,
        interval: float = 8.8,
        settle_seconds: float = 0.9,
        loading_template: str = "loading",
    ) -> MatchResult:
        """识别模板但不点击。

        等待页面不在 loading 状态后，只识别一次目标模板。
        retries/interval 只用于 loading 状态检测，不再用于目标模板的重复识别。
        传入 roi 时，会覆盖模板配置中的默认 ROI。

        返回：
        - 识别成功：返回 found=True 的 MatchResult；
        - 识别失败且 required=False：返回 found=False 的 MatchResult；
        - 识别失败且 required=True：抛出 RuntimeError。
        """
        shot = self.wait_until_not_loading(
            retries=retries,
            interval=interval,
            settle_seconds=settle_seconds,
            loading_template=loading_template,
        )
        res = self.match(name, shot, roi=roi)
        if not res.found:
            msg = f"未识别到模板 {name}，score={res.score:.3f}"
            if required:
                logging.error(msg)
                raise RuntimeError(msg)
            logging.warning(msg)
            return res

        logging.info("识别成功 %-18s at (%.1f, %.1f), score=%.3f", name, res.x, res.y, res.score)
        return res

    def click_template(
        self,
        name: str,
        required: bool = True,
        tap_delay: float = 1.2, # 点击后等待时间
        roi: Optional[tuple[int, int, int, int]] = None,
        retries: int = 5,
        interval: float = 8.8,
        settle_seconds: float = 0.9,
        loading_template: str = "loading",
    ) -> MatchResult:
        """等待页面不在 loading 状态后，只识别一次模板，识别成功后点击模板中心。

        retries/interval 只用于 loading 状态检测，不再用于目标模板的重复识别。
        tap_delay 表示点击后的等待时间，不是点击持续时间。
        传入 roi 时，会覆盖模板配置中的默认 ROI。

        返回：
        - 识别成功并点击：返回 found=True 的 MatchResult；
        - 识别失败且 required=False：返回 found=False 的 MatchResult；
        - 识别失败且 required=True：抛出 RuntimeError。
        """
        shot = self.wait_until_not_loading(
            retries=retries,
            interval=interval,
            settle_seconds=settle_seconds,
            loading_template=loading_template,
        )
        res = self.match(name, shot, roi=roi)
        if not res.found:
            msg = f"未识别到模板 {name}，score={res.score:.3f}，无法点击"
            if required:
                logging.error(msg)
                raise RuntimeError(msg)
            logging.warning(msg)
            return res

        logging.info("点击模板 %-18s at (%.1f, %.1f)", name, res.x, res.y)
        self.ctrl.tap(res.x, res.y, delay=tap_delay)
        return res

    def _position_spec(self, name: str) -> dict:
        if name not in POSITION_SPECS:
            raise KeyError(f"未知固定点击位置: {name}")
        return POSITION_SPECS[name]

    def tap_position(
        self,
        name: str,
        tap_delay: float = 1.2, # 点击后等待时间
        retries: int = 5,
        interval: float = 8.8,
        settle_seconds: float = 0.9,
        loading_template: str = "loading",
    ) -> None:
        """点击 config.POSITION_SPECS 中定义的固定坐标位置。
        固定坐标统一在 config.py 的 POSITION_SPECS 中维护。
        坐标基于微信小程序窗口 client rect，即截图左上角为 (0, 0)。
        """
        self.wait_until_not_loading(
            retries=retries,
            interval=interval,
            settle_seconds=settle_seconds,
            loading_template=loading_template,
        )
        spec = self._position_spec(name)
        x, y = spec["pos"]
        logging.info("点击固定位置 %-18s at (%d,%d) desc=%s", name, x, y, spec.get("desc", ""))
        self.ctrl.tap(x, y, delay=tap_delay)

    # ==================== 通用广告处理 ====================

    def close_ad_after_wait(self, context: str = "广告流程", ad_wait_seconds: float = 40.0) -> None:
        """广告领取后等待广告结束，并关闭广告页面。"""
        logging.info("%s：等待 %d 秒", context, ad_wait_seconds)
        time.sleep(ad_wait_seconds)

        # 鉴于广告按钮受到透明度影响，手动点击固定坐标位置一次，暂时不做识别点击。
        self.tap_position("ad_close", tap_delay=3.6) # 广告点击关闭后等待时间设置稍长一些，确保奖励领取加载。
        logging.info("%s：广告已关闭", context)

    def revive_by_ad_if_needed(self, context: str) -> bool:
        if not self.click_template("ad_revive", required=False, settle_seconds=-1.0).found:
            return False

        logging.info("%s：检测到坠机复活弹窗，开始观看复活广告", context)
        self.close_ad_after_wait(f"{context}复活")
        logging.info("%s：复活完成，继续等待战斗结束", context)
        return True

    # def try_start_ad_or_handle_no_ad(self, button_template: str, context: str, max_attempts: int) -> bool:
    #     """点击广告/免费按钮后判断是正常进入广告，还是出现“没有合适广告”提示。

    #     返回 True：未检测到无广告提示，按正常广告流程继续。
    #     返回 False：达到最大重试次数后仍无广告。
    #     """
    #     for attempt in range(1, max_attempts + 1):
    #         logging.info("%s：第%d次尝试点击 %s", context, attempt, button_template)
    #         # 这次点击后需要等待较长时间，设置较大的 tap_delay，否则无法在点击后检测到无广告提示。
    #         self.click_template(button_template, tap_delay=8.0)

    #         no_ad = self.click_template("confirm") # 无合适广告/收赠体力确认弹窗
    #         if no_ad:
    #             logging.warning("%s：出现无合适广告提示，已点击确认，准备重新尝试", context)
    #             continue

    #         logging.info("%s：未检测到无合适广告提示，按正常广告流程处理", context)
    #         return True

    #     logging.error("%s：连续 %d 次出现无合适广告提示", context, max_attempts)
    #     return False

    # ==================== 返回首页 ====================

    def back_to_home(self) -> None:
        logging.info("返回首页")
        self.click_template("nav_home")
        self.deal_endless_mode_event_when_back_to_home()

    def deal_endless_mode_event_when_back_to_home(self) -> None:
        for _ in range(1, 3):
            if self.recognize_template("join_now", required=False, settle_seconds=1.5).found:
                logging.info("返回首页时出现无尽限时小组赛/无尽争霸赛")
                self.click_template("endless_mode_known", required=False, settle_seconds=4.8) # 可能会出现本周超频装备信息界面，出现在 立即参加 界面之上，需要先点击 知道了 按钮
                if self.recognize_template("endless_limited_time_group_match", required=False).found:
                    logging.info("立即参加无尽限时小组赛")
                    self.click_template("join_now")
                    self.click_template("limited_time_group_match_close") # 无尽限时小组赛关闭按钮
                elif self.recognize_template("endless_championship", required=False).found:
                    logging.info("立即参加无尽争霸赛")
                    self.click_template("join_now")
                    self.click_template("back", settle_seconds=4.8) # 无尽争霸赛返回按钮，返回之后会退回到首页

    # ==================== 兑换码 ====================

    def recognize_toolbox_template(
        self,
        name: str,
        required: bool = True,
    ) -> MatchResult:
        shot = self.toolbox_screenshot(f"toolbox_{name}")
        result = self.match(name, shot)
        if not result.found:
            message = f"Yang昜工具箱未识别到模板 {name}，score={result.score:.3f}"
            if required:
                logging.error(message)
                raise RuntimeError(message)
            logging.warning(message)
        return result

    def click_toolbox_template(
        self,
        name: str,
        required: bool = True,
        tap_delay: float = 2.4,
    ) -> MatchResult:
        result = self.recognize_toolbox_template(name, required=required)
        if result.found:
            logging.info("点击Yang昜工具箱模板 %-18s at (%.1f, %.1f)", name, result.x, result.y)
            self._require_toolbox_controller().tap(result.x, result.y, delay=tap_delay)
        return result

    def tap_toolbox_position(
        self,
        name: str,
        tap_delay: float = 2.4,
    ) -> None:
        if name not in TOOLBOX_POSITION_SPECS:
            raise KeyError(f"未知Yang昜工具箱固定位置: {name}")
        spec = TOOLBOX_POSITION_SPECS[name]
        x, y = spec["pos"]
        logging.info("点击Yang昜工具箱固定位置 %-18s at (%d,%d) desc=%s", name, x, y, spec.get("desc", ""))
        self._require_toolbox_controller().tap(x, y, delay=tap_delay)

    @staticmethod
    def extract_redemption_code(text: str) -> Optional[str]:
        match = re.search(r"(?<![A-Za-z0-9])[A-Za-z0-9]{8}(?![A-Za-z0-9])", text.strip())
        return match.group(0) if match else None

    def copy_next_toolbox_redemption_code(self) -> Optional[str]:
        self.tap_toolbox_position("first_code")
        if not self.recognize_toolbox_template(
            "toolbox_preview_close",
            required=False,
        ).found:
            return None

        self.tap_toolbox_position("code_text")
        code = self.extract_redemption_code(self._require_toolbox_controller().copy_selected_text())

        if code is None:
            raise RuntimeError("未能从Yang昜工具箱复制兑换码")

        self.click_toolbox_template("toolbox_preview_close")
        return code

    def run_redemption_code_flow(self) -> None:
        logging.info("========== 兑换码流程开始 ==========")
        self.click_toolbox_template("toolbox_redemption_entry")
        self.click_template("home_settings")
        self.click_template("settings_redemption")

        processed_count = 0
        redeemed_count = 0
        previous_redemption_failed = False
        while True:
            code = self.copy_next_toolbox_redemption_code()
            if code is None:
                logging.info("Yang昜工具箱已没有可用兑换码")
                break

            processed_count += 1
            logging.info("处理第%d条兑换码", processed_count)
            title = self.recognize_template("redemption_code_title")
            self.ctrl.tap(title.x, title.y + 95)
            if previous_redemption_failed:
                self.ctrl.clear_text()
                previous_redemption_failed = False
            self.ctrl.type_text(code)
            self.ctrl.press_key("enter")
            self.click_template("redemption_submit")

            if self.recognize_template("confirm", required=False).found:
                logging.warning("第%d条兑换码无法兑换，关闭提示并继续下一条", processed_count)
                self.tap_position("exit_mid_down")
                previous_redemption_failed = True
                continue

            self.click_template("reward_claim")
            redeemed_count += 1

        self.tap_toolbox_position("close_window")
        self.tap_position("exit_mid_down")
        self.tap_position("exit_mid_down")
        logging.info(
            "========== 兑换码流程结束，共处理%d条，成功兑换%d条 ==========",
            processed_count,
            redeemed_count,
        )

    # ==================== 微信游戏圈 ====================

    def run_game_circle_flow(self) -> None:
        logging.info("========== 微信游戏圈&社区奖励流程开始 ==========")
        logging.info("打开微信小游戏侧边栏")
        self.click_template("sidebar_open", tap_delay=3.6)
        force_client_size = self.ctrl.force_client_size
        self.ctrl.force_client_size = False

        logging.info("进入游戏圈")
        self.click_template("sidebar_circle_tab", tap_delay=3.6)
        self.click_template("sidebar_circle_tab", tap_delay=3.6) # 再多点一次，防止还有别的弹窗

        self.click_template("sidebar_gift", tap_delay=3.6)
        logging.info("进入微信游戏福利中心")
        if self.click_template("sidebar_gift_claim_all", required=False, tap_delay=3.6).found:
            logging.info("游戏圈礼包已一键领取")
        else:
            logging.info("游戏圈礼包今日已被领取")
        self.click_template("sidebar_gift_back", tap_delay=3.6)
        logging.info("已返回游戏圈")

        for index in range(1, 3):
            logging.info("给第%d条动态点赞", index)
            self.click_template("sidebar_like", required=False, tap_delay=3.6)

        logging.info("打开一条动态的评论入口")
        self.click_template("sidebar_comment", tap_delay=3.6)
        self.click_template("sidebar_comment_input")
        self.ctrl.type_text("20")
        self.click_template("sidebar_comment_send")
        logging.info("游戏圈评论已发送")

        self.click_template("sidebar_comment_close")
        self.click_template("sidebar_close", tap_delay=3.6) # 窗口尺寸还原，等待一段时间后检测尺寸
        self.ctrl.force_client_size = force_client_size
        logging.info("微信小游戏侧边栏已关闭")
        self.ctrl.assert_client_size()

        logging.info("点击首页社区奖励")
        self.click_template("home_community_reward")
        time.sleep(3.0) # 等待社区奖励刷新
        for index in range(1, 3):
            logging.info("领取游戏圈第%d个社区奖励", index)
            if self.click_template("community_reward_circle_claim", required=False).found:
                self.click_template("reward_claim")
        logging.info("领取添加到桌面社区奖励")
        self.click_template("community_reward_desktop_tab")
        if self.click_template("community_reward_desktop_claim", required=False).found:
            self.click_template("reward_claim")
        self.tap_position("exit_mid_down")

        self.claim_information_rewards()
        logging.info("========== 微信游戏圈&社区奖励流程结束 ==========")

    # ==================== 十年集结 ====================

    def run_decade_reunion_flow(self) -> None:
        logging.info("========== 十年集结领取开始 ==========")
        if self.click_template("home_decade_reunion", required=False).found:
            self.click_template("home_sub_decade_reunion", required=False)
            logging.info("十年集结弹幕发送开始")
            if self.click_template("send_comment", required=False, settle_seconds=3.6).found:
                self.click_template("send")
            else:
                logging.info("十年集结弹幕已发送过")
            self.click_template("back")
        else:
            logging.info("十年集结弹幕已发送过")
        logging.info("========== 十年集结领取结束 ==========")

    # ==================== 商城礼包领取 ====================

    def claim_shop_resource(self) -> None:
        logging.info("获取商店免费资源")
        round_idx = 1
        while True:
            if not self.click_template("shop_free_resource", required=False).found:
                logging.info("商店免费资源已领取完毕")
                break
            context = f"领取商店免费资源第{round_idx}次"
            logging.info("%s：执行广告领取", context)
            self.close_ad_after_wait(context)
            self.click_template("reward_claim")
            logging.info("第%d次商店免费资源领取奖励完成", round_idx)
            round_idx += 1

    def run_shop_gift_flow(self) -> None:
        logging.info("========== 商城礼包领取开始 ==========")
        logging.info("进入商城-商店界面")
        self.click_template("home_shop")
        self.claim_shop_resource()
        logging.info("进入商城-礼包界面")
        self.click_template("shop_gift_tab")
        if self.click_template("shop_gift_first_free", required=False).found:
            self.click_template("reward_claim")
        logging.info("商城免费礼包已领取")
        self.back_to_home()
        logging.info("========== 商城礼包领取结束 ==========")

    # ==================== 星际探索领取 ====================

    def enter_interstellar(self) -> None:
        logging.info("进入星际探索")
        self.click_template("home_interstellar")

    def claim_interstellar_income(self) -> None:
        logging.info("星际探索页面领取累计收益，若在冷却中则跳过领取")
        if self.click_template("star_claim", required=False).found:
            self.click_template("reward_claim")

    def run_quick_exploration(self) -> None:
        """开始4次快速探索。"""
        logging.info("执行快速探索")

        if self.click_template("star_quick", required=False).found:
            
            if self.click_template("quick_free_claim", required=False).found:
                logging.info("今日第1次快速探索可领取免费收益，点击领取")
                self.click_template("reward_claim")
            
            logging.info("快速探索广告领取，开始广告领取循环")
            round_idx = 1
            while True:
                if not self.click_template("quick_ad_claim", required=False).found:
                    logging.info("快速探索广告领取次数用尽，将退出星际探索回到首页")
                    self.tap_position("exit_mid_down")
                    self.deal_endless_mode_event_when_back_to_home()
                    break
                context = f"快速探索第{round_idx}次"
                logging.info("%s：执行广告领取", context)
                self.close_ad_after_wait(context)
                self.click_template("reward_claim")
                logging.info("第%d次快速探索广告领取奖励完成", round_idx)
                round_idx += 1
        else:
            logging.info("今日快速探索次数已用尽，将退出星际探索回到首页")
            self.tap_position("exit_mid_down")
            self.deal_endless_mode_event_when_back_to_home()

    def run_interstellar_flow(self) -> None:
        logging.info("========== 星际探索领取开始 ==========")
        self.enter_interstellar()
        self.claim_interstellar_income()
        self.run_quick_exploration()
        logging.info("========== 星际探索领取结束 ==========")

    # ==================== 体力获取 ====================

    def run_stamina_flow(self) -> None:
        logging.info("========== 体力获取开始 ==========")
        self.click_template("home_energy_plus")

        round_idx = 1
        while True:
            context = f"体力广告领取第{round_idx}次"
            if self.click_template("stamina_free", required=False).found:
                self.close_ad_after_wait(context)
                logging.info("第%d次体力免费广告领取完成", round_idx)
                round_idx += 1
                continue
            logging.info("体力购买弹窗：免费体力次数已用尽，退出广告领取循环")
            break

        logging.info("关闭体力购买弹窗，回到主界面")
        self.tap_position("exit_mid_down")
        self.deal_endless_mode_event_when_back_to_home()

        self.click_template("home_friend")
        self.click_template("friend_collect")
        # self.click_template("confirm") # 无合适广告/收赠体力确认弹窗；这里可以用self.tap_position("exit_mid_down")代替
        self.tap_position("exit_mid_down")
        logging.info("好友体力一键收赠完成")

        self.back_to_home()
        logging.info("========== 体力获取结束 ==========")

    # ==================== 战队征讨与捐献 ====================

    def enter_team(self) -> None:
        logging.info("从首页进入战队")
        self.click_template("home_team")

    def wait_and_confirm_team_expedition(self, check_interval: float = 10.0) -> None:
        time.sleep(120) # 固定等待120秒
        round_idx = 1
        while True:
            if self.click_template("team_expedition_confirm", required=False, settle_seconds=-1.0).found:
                logging.info("战队征讨：检测到挑战完成按钮并已点击")
                return
            logging.info("战队征讨：尚未结束，等待%.1f秒后继续检测，当前第%d次检测", check_interval, round_idx)
            time.sleep(check_interval)
            round_idx += 1

    def team_expedition(self) -> None:
        logging.info("战队征讨开始")
        if self.click_template("team_expedition_going_on", required=False).found:
            logging.info("战队征讨——挑战中")
            self.click_template("team_expedition_known", required=False, settle_seconds=3.6) # 可能会出现本期战术武装信息界面，需要先点击 知道了 按钮

            round_idx = 1
            while True:
                logging.info("战队征讨：第%d次出击", round_idx)
                self.click_template("team_expedition_sortie")
                # 可能会出现编队异常（原晶），目前未实现改功能
                if self.recognize_template("confirm", required=False).found: # 战队BOSS挑战次数不足确认按钮
                    logging.info("战队BOSS挑战次数不足，停止战队征讨")
                    self.tap_position("exit_mid_down")
                    break
                logging.info("等待征讨中......")
                self.wait_and_confirm_team_expedition()
                round_idx += 1
            if self.click_template("team_expedition_claim", required=False).found:
                logging.info("已领取今日伤害奖励")
                self.click_template("reward_claim")
            logging.info("返回战队界面")
            self.click_template("back")
        else:
            logging.info("战队征讨——公示中，不进行征讨")
        logging.info("战队征讨结束")
    
    def team_donation(self) -> None:
        logging.info("战队捐献开始")
        self.click_template("team_donate_entry")

        round_idx1 = 1
        while True:
            logging.info("战队金币捐献：第%d次", round_idx1)
            self.click_template("team_coin_donate")
            if not self.click_template("reward_claim", required=False).found:
                logging.info("金币捐献次数不足，退出战队金币捐献")
                self.tap_position("exit_mid_down")
                break
            round_idx1 += 1
        
        round_idx2 = 1
        while True:
            logging.info("战队钻石捐献：第%d次", round_idx2)
            self.click_template("team_diamond_donate")
            if not self.click_template("team_diamond_donate_confirm", required=False).found:
                logging.info("钻石捐献次数不足，退出战队钻石捐献")
                self.tap_position("exit_mid_down")
                break
            self.click_template("reward_claim")
            round_idx2 += 1

        self.tap_position("exit_mid_down")
        logging.info("战队捐献结束")

    def run_team_expedition_and_donation_flow(self) -> None:
        logging.info("========== 战队征讨与捐献开始 ==========")
        self.enter_team()
        self.team_expedition()
        self.team_donation()
        self.back_to_home()
        logging.info("========== 战队征讨与捐献结束 ==========")

    # ==================== 背包空间处理 ====================

    def enter_warehouse(self) -> None:
        logging.info("从首页进入仓库")
        self.click_template("home_warehouse")

    def synthesis_one_type_of_equipment(self, equipment_type: str) -> None:
        type_dict: dict[str, str] = {"white": "白色", "green": "绿色", "blue": "蓝色"}
        self.click_template(f"{equipment_type}_equipment")
        logging.info("改造：选择%s装备", type_dict[equipment_type])
        round_idx = 1
        while True:
            logging.info("改造：尝试第%d次装备合成循环", round_idx)
            self.click_template("automatic_synthesis", settle_seconds=1.2)
            if self.click_template("confirm", required=False).found: # 装备合成确认弹窗
                logging.info("改造：装备合成确认弹窗已识别并点击确认")
                idx = 1
                while True:
                    time.sleep(2.0) # 每2秒识别一次画面
                    if not self.recognize_template("stop_synthesis", required=False, settle_seconds=-1.0).found:
                        logging.info("改造：检测到自动合成已停止，可能由于合成装备不足，或者合成出S装备")
                        break
                    logging.info("改造：自动合成中......")
                    idx += 1
            else:
                logging.info("改造：%s合成装备不足，结束循环，循环次数：%d", type_dict[equipment_type], round_idx)
                break
            round_idx += 1

    def equipment_synthesis_and_split(self) -> None:
        logging.info("点击仓库-改造，开始装备合成和拆分流程")
        self.click_template("modification")

        logging.info("开始装备合成流程")
        self.synthesis_one_type_of_equipment("white")
        self.synthesis_one_type_of_equipment("green")
        self.synthesis_one_type_of_equipment("blue")

        logging.info("装备合成完成，开始拆分流程")
        self.click_template("enter_split")
        self.click_template("select_split_equipment")
        self.click_template("blue_plus_one_equipment")
        self.click_template("confirm_selected_split_equipment")
        if self.click_template("confirm", required=False).found: # 请选择要拆分的装备，当没有选择任何装备并点击确认时，会弹出此提示框
            logging.info("没有可拆分的蓝色+1装备，已点击确认，结束拆分流程")
            self.tap_position("exit_mid_down")
        else:
            logging.info("已选择拆分装备，继续拆分流程")
            self.click_template("split")
            self.click_template("confirm") # 装备拆分确认弹窗
            logging.info("蓝色+1装备拆分完成，再次回到装备合成界面，尝试蓝色装备合成")
            self.click_template("enter_synthesis", settle_seconds=2.4) # 拆分动画占空时间settle_seconds
            self.synthesis_one_type_of_equipment("blue")
        logging.info("装备合成和拆分流程结束，退出改造并回到仓库界面")
        self.click_template("back")

    def resource_sale(self) -> None:
        logging.info("资源出售：进入背包出售流程")
        self.click_template("backpack")
        self.click_template("sale")

        if self.click_template("immediate_sale", required=False).found:
            logging.info("资源出售：已处理立即出售弹窗")
            if not self.enable_resource_sale:
                logging.info("资源出售：未启用残骸出售，退出背包弹窗")
                self.tap_position("exit_mid_down")
                return
            logging.info("资源出售：重新进入出售页，准备处理残骸出售")
            self.click_template("sale")
        elif not self.enable_resource_sale:
            logging.info("资源出售：未出现立即出售弹窗，且未启用残骸出售，退出出售页")
            self.tap_position("exit_mid_down")
            return

        if not any(RESOURCE_SALE_WRECKS.values()):
            logging.info("资源出售：没有配置需要出售的残骸，退出出售页")
            self.tap_position("exit_mid_down")
            return

        self.click_template("quick_sale")

        selected_wrecks: set[str] = set()
        previous_page_wrecks: Optional[set[str]] = None
        scan_index = 1
        while True:
            logging.info("资源出售：扫描快速出售列表第%d页", scan_index)
            page_wrecks = self.select_visible_resource_sale_wrecks(selected_wrecks)
            if previous_page_wrecks is not None and page_wrecks == previous_page_wrecks:
                logging.info("资源出售：下滑后残骸集合未变化，判断已到列表底部")
                break

            previous_page_wrecks = page_wrecks
            logging.info("资源出售：第%d页扫描后，向下滚动列表", scan_index)
            self.ctrl.swipe(
                360,
                950,
                360,
                350,
                duration=0.55,
                press_delay=0.12,
                release_delay=0.45,
                delay=0.8,
            )
            scan_index += 1
            if scan_index > 12:
                raise RuntimeError("资源出售：下滑扫描超过 12 页仍未检测到底部")

        logging.info("资源出售：已选择残骸=%s", sorted(selected_wrecks))
        if selected_wrecks:
            self.click_template("sale_enabled")
            self.click_template("confirm") # 确认出售按钮
        else:
            logging.info("资源出售：没有选择任何残骸，跳过出售按钮")
            self.tap_position("exit_mid_down")
        self.tap_position("exit_mid_down")

    def select_visible_resource_sale_wrecks(self, selected_wrecks: set[str]) -> set[str]:
        page_wrecks: set[str] = set()
        for template_name in RESOURCE_SALE_WRECKS:
            wreck = self.recognize_template(
                template_name,
                required=False,
                settle_seconds=-1.0,
            )
            if not wreck.found:
                continue

            page_wrecks.add(template_name)
            if not RESOURCE_SALE_WRECKS[template_name]:
                continue
            if template_name in selected_wrecks:
                logging.info("资源出售：残骸 %s 已选择过，跳过", template_name)
                continue
            slider_thumb = self.recognize_template(
                "resource_sale_slider_thumb",
                required=False,
                roi=self.get_resource_sale_slider_thumb_roi(wreck),
                settle_seconds=-1.0,
            )
            if not slider_thumb.found:
                logging.info("资源出售：残骸 %s 已出现但滑条未完整露出，等待后续页面处理", template_name)
                continue

            logging.info(
                "资源出售：选择残骸 %s at y=%.1f score=%.3f",
                template_name,
                wreck.y,
                wreck.score,
            )
            self.drag_resource_sale_wreck_slider(slider_thumb)
            selected_wrecks.add(template_name)

        return page_wrecks

    def get_resource_sale_slider_thumb_roi(self, wreck: MatchResult) -> tuple[int, int, int, int]:
        slider_y = int(round(wreck.y + 12.5))
        return (410, max(220, slider_y - 30), 640, min(1020, slider_y + 30))

    def drag_resource_sale_wreck_slider(self, slider_thumb: MatchResult) -> None:
        self.ctrl.swipe(
            slider_thumb.x,
            slider_thumb.y,
            590,
            slider_thumb.y,
        )

    def experience_synthesis(self) -> None:
        logging.info("点击仓库-背包，开始经验合成流程（不合成超级强化魔方）")
        self.click_template("backpack")
        self.click_template("experience_synthesis")
        
        round_idx = 1
        while True:
            if self.click_template("chosen", required=False).found:
                logging.info("已经取消选择超级强化魔方，或者合成超级强化魔方所需材料数量不足")

            if not self.recognize_template("confirm_experience_synthesis", required=False).found:
                logging.info("经验合成：数量不足，结束经验合成")
                break

            logging.info("经验合成：第%d次经验合成", round_idx)
            self.click_template("confirm_experience_synthesis")
            time.sleep(3.6) # 经验合成动画时间，后续考虑识别经验合成的特殊加载ui
            self.click_template("reward_claim")
            round_idx += 1

        self.tap_position("exit_mid_down") # 点击两次底部从经验合成回到仓库界面
        self.tap_position("exit_mid_down")

    def run_backpack_space_flow(self) -> None:
        logging.info("========== 背包空间处理开始 ==========")
        self.enter_warehouse()
        self.equipment_synthesis_and_split()
        self.resource_sale()
        self.experience_synthesis()
        self.back_to_home()
        logging.info("========== 背包空间处理结束 ==========")

    def run_resource_sale_only_flow(self) -> None:
        if not self.enable_resource_sale:
            logging.info("========== 第二次背包空间处理：未启用资源出售，跳过 ==========")
            return
        logging.info("========== 第二次背包空间处理：资源出售开始 ==========")
        self.enter_warehouse()
        self.resource_sale()
        self.back_to_home()
        logging.info("========== 第二次背包空间处理：资源出售结束 ==========")

    def run_equipment_synthesis_and_split_flow(self) -> None:
        logging.info("========== 第三次背包空间处理：装备合成与拆分开始 ==========")
        self.enter_warehouse()
        self.equipment_synthesis_and_split()
        self.back_to_home()
        logging.info("========== 第三次背包空间处理：装备合成与拆分结束 ==========")

    # ==================== 夺宝领取 ====================

    def run_treasure_hunt_flow(self) -> None:
        logging.info("========== 夺宝领取开始 ==========")
        logging.info("进入夺宝界面")
        self.click_template("home_treasure_hunt")

        logging.info("观看广告领取免费装备宝箱")
        round_idx = 1
        while True:
            if not self.click_template("treasure_hunt_free_chest", required=False).found:
                logging.info("免费装备宝箱已领取完毕")
                break
            context = f"领取免费装备宝箱第{round_idx}次"
            logging.info("%s：执行广告领取", context)
            self.close_ad_after_wait(context)
            self.tap_position("open_chest")
            time.sleep(3.6) # 装备宝箱开启动画时间
            self.click_template("reward_claim")
            logging.info("第%d次免费装备宝箱领取奖励完成", round_idx)
            round_idx += 1

        logging.info("进入夺宝-转盘界面")
        self.click_template("treasure_hunt_wheel")
        if self.click_template("wheel_first_free", required=False, tap_delay=5.0).found: # 转盘点击后等待时间设置稍长一些，确保转盘动画播放完成。
            self.click_template("reward_claim")
        logging.info("转盘免费奖励已领取")

        logging.info("进入夺宝-兑换界面")
        self.click_template("treasure_hunt_redeem")
        if self.click_template("claim_star", required=False, settle_seconds=1.2).found: # 星辉出现动画占用settle_seconds时间
            self.click_template("reward_claim")
        self.back_to_home()
        logging.info("========== 夺宝领取结束 ==========")

    # ==================== 活动关卡 ====================

    def wait_and_continue_event_stage(
        self,
        check_interval: float = 10.0, # 每10秒检测一次结算页
    ) -> None:
        time.sleep(60) # 固定等待60秒
        round_idx = 1
        while True:
            if self.revive_by_ad_if_needed("活动关卡"):
                continue
            if self.click_template("continue", required=False, tap_delay=2.4, settle_seconds=-1.0).found:
                logging.info("活动关卡：检测到继续按钮并已点击")
                return
            logging.info("活动关卡：尚未进入结算页，等待%.1f秒后继续检测，当前第%d次检测", check_interval, round_idx)
            time.sleep(check_interval)
            round_idx += 1

    def run_event_stage_flow(self) -> None:
        logging.info("========== 活动关卡流程开始 ==========")
        self.click_template("home_challenge_mode")
        self.click_template("challenge_event_stage")
        self.click_template("event_stage_meteor_blitz")
        self.click_template("blitz_popup")
        self.wait_and_continue_event_stage()
        self.back_to_home()
        logging.info("========== 活动关卡流程结束 ==========")

    # ==================== 关卡扫荡 ====================

    def claim_starry_ladder_rewards(self) -> None:
        logging.info("进入逐星长阶")
        self.click_template("challenge_starry_ladder") # 识别到有逐星信标x5时，应当先领取5次逐星补给，再领取逐星信标x5
        if self.recognize_template("starry_ladder_beacon", required=False).found:
            logging.info("进入逐星补给")
            self.click_template("starry_ladder_supply")
            logging.info("领取5次逐星补给")
            self.click_template("starry_ladder_supply_claim_5")
            self.click_template("reward_claim")
            self.tap_position("exit_mid_down")
            logging.info("领取逐星信标x5")
            self.click_template("starry_ladder_beacon")
            self.click_template("reward_claim")
        logging.info("返回闯关模式界面")
        self.click_template("back")

    def reopen_quick_sweep(self, difficulty: str) -> None:
        logging.info("重新打开快速扫荡，恢复%s难度", difficulty)
        self.click_template("challenge_quick_sweep")
        if difficulty == "hero":
            self.click_template("quick_sweep_hero_tab")

    def should_double_quick_sweep_reward(
        self,
        difficulty: str,
        level: int,
        sweep_index: int,
        double_reward_count: int,
    ) -> bool:
        if sweep_index > double_reward_count:
            return False

        used_count = self.level_sweep_double_reward_counts.get(difficulty, 0)
        if used_count >= 5:
            logging.warning(
                "快速扫荡%s难度：广告双倍奖励已使用%d次，跳过第%d关第%d次双倍",
                difficulty,
                used_count,
                level,
                sweep_index,
            )
            return False

        return True

    def get_quick_sweep_button_roi(self, level_result: MatchResult) -> tuple[int, int, int, int]:
        y1 = int(level_result.y + 35)
        y2 = int(level_result.y + 125)
        return (470, y1, 670, y2)

    def quick_sweep_level_once(
        self,
        difficulty: str,
        level: int,
        sweep_index: int,
        use_double_reward: bool,
    ) -> None:
        template_name = f"quick_sweep_{difficulty}_{level}"
        context = f"快速扫荡{difficulty}难度第{level}关第{sweep_index}次"

        for scan_index in range(1, 4):
            level_result = self.recognize_template(template_name, required=False)

            if level_result.found:
                button_roi = self.get_quick_sweep_button_roi(level_result)
                if self.click_template("quick_sweep_sweep_button", required=False, roi=button_roi).found:
                    logging.info("%s：关卡与扫荡按钮均可见", context)
                    self.level_sweep_swept_count += 1
                    if use_double_reward:
                        logging.info("%s：领取双倍奖励", context)
                        self.click_template("quick_sweep_double_reward")
                        self.close_ad_after_wait(context)
                        self.level_sweep_double_reward_counts[difficulty] += 1
                    self.tap_position("exit_mid_down")
                    return

                logging.info("%s：关卡标题可见，但同一行未识别到可用扫荡按钮，scan=%d", context, scan_index)
            else:
                logging.info("%s：当前可见区域未识别到关卡，scan=%d", context, scan_index)

            if scan_index < 3:
                logging.info("%s：第%d次扫描未找到可点击按钮，向下滚动列表", context, scan_index)
                self.ctrl.swipe(
                    360,
                    1030,
                    360,
                    520,
                )

        raise RuntimeError(f"{context}，下滑寻找超出限制仍未找到可点击的扫荡按钮")

    def level_sweep(
        self,
        difficulty: str,
    ) -> None:
        level_plan = LEVEL_SWEEP_PLAN[difficulty]
        if not level_plan:
            logging.info("快速扫荡%s难度：未配置目标关卡，跳过", difficulty)
            return

        logging.info("快速扫荡%s难度：目标关卡计划=%s", difficulty, level_plan)
        for plan in level_plan:
            level = int(plan["level"])
            sweep_count = int(plan.get("sweeps", 0))
            double_reward_count = int(plan.get("double_rewards", 0))
            if sweep_count <= 0:
                logging.warning("快速扫荡%s难度第%d关：扫荡次数为%d，跳过", difficulty, level, sweep_count)
                continue
            if double_reward_count > sweep_count:
                logging.warning(
                    "快速扫荡%s难度第%d关：双倍次数%d超过扫荡次数%d，按扫荡次数处理",
                    difficulty,
                    level,
                    double_reward_count,
                    sweep_count,
                )
                double_reward_count = sweep_count

            for sweep_index in range(1, sweep_count + 1):
                use_double_reward = self.should_double_quick_sweep_reward(difficulty, level, sweep_index, double_reward_count)

                self.quick_sweep_level_once(difficulty, level, sweep_index, use_double_reward)

                if self.recognize_template("join_now", required=False, settle_seconds=1.5).found:
                    logging.info("无尽限时小组赛/无尽争霸赛事件已出现，立即参加后返回闯关模式继续关卡扫荡")
                    self.click_template("endless_mode_known", required=False, settle_seconds=4.8) # 可能会出现本周超频装备信息界面，出现在 立即参加 界面之上，需要先点击 知道了 按钮
                    if self.recognize_template("endless_limited_time_group_match", required=False).found:
                        logging.info("立即参加无尽限时小组赛")
                        self.click_template("join_now")
                        self.click_template("limited_time_group_match_close") # 无尽限时小组赛关闭按钮
                    elif self.recognize_template("endless_championship", required=False).found:
                        logging.info("立即参加无尽争霸赛")
                        self.click_template("join_now")
                        self.click_template("back", settle_seconds=4.8) # 无尽争霸赛返回按钮
                    self.reopen_quick_sweep(difficulty)

                if self.level_sweep_swept_count >= 5 and not self.level_sweep_periodic_reward_claimed:
                    self.tap_position("exit_mid_down") # 固定点击动作，退出快速扫荡界面
                    logging.info("扫荡累计达到5个关卡，领取体力100奖励")
                    self.claim_home_rewards()
                    self.level_sweep_periodic_reward_claimed = True
                    self.reopen_quick_sweep(difficulty)

    def run_level_sweep_flow(self) -> None:
        logging.info("========== 关卡扫荡流程开始 ==========")
        logging.info("从首页进入闯关模式")
        self.click_template("home_challenge_mode")

        self.claim_starry_ladder_rewards()

        logging.info("打开快速扫荡")
        self.click_template("challenge_quick_sweep")
        self.level_sweep_swept_count = 0
        self.level_sweep_periodic_reward_claimed = False
        self.level_sweep_double_reward_counts = {"normal": 0, "hero": 0}

        self.level_sweep("normal")

        logging.info("切换到英雄难度")
        self.click_template("quick_sweep_hero_tab")
        self.level_sweep("hero")

        logging.info("关闭快速扫荡")
        self.tap_position("exit_mid_down")
        self.back_to_home()
        logging.info("========== 关卡扫荡流程结束 ==========")

    # ==================== BOSS模式 ====================

    def select_today_boss_mode_boards(self) -> list[str]:
        day = datetime.now().day
        if day % 2 == 0:
            logging.info("BOSS模式：今天是%d日，偶数日期挑战天龙座空间站（装甲）、白鸟座空间站（副武器）", day)
            return ["draco", "cygnus"]

        logging.info("BOSS模式：今天是%d日，奇数日期挑战天马座空间站（战机）、仙女座空间站（僚机）", day)
        return ["pegasus", "andromeda"]

    def ensure_boss_mode_extreme_difficulty(self) -> None:
        round_idx = 1
        while True:
            if self.recognize_template("boss_mode_enemy_power_extreme", required=False).found:
                logging.info("BOSS模式：已选择极难难度")
                return

            logging.info("BOSS模式：当前不是极难难度，点击左侧切换按钮")
            self.tap_position("boss_mode_difficulty_prev")
            round_idx += 1

    def wait_and_continue_boss_mode(self, check_interval: float = 10.0) -> None:
        time.sleep(30) # 固定等待30秒
        round_idx = 1
        while True:
            if self.revive_by_ad_if_needed("BOSS模式"):
                continue
            if self.click_template("continue", required=False, settle_seconds=-1.0).found:
                logging.info("BOSS模式：检测到继续按钮并已点击")
                return
            logging.info("BOSS模式：尚未进入结算页，等待%.1f秒后继续检测，当前第%d次检测", check_interval, round_idx)
            time.sleep(check_interval)
            round_idx += 1

    def wait_and_drag_to_bottom(self, check_interval: float = 0.6) -> None:
        round_idx = 1
        while True:
            if self.revive_by_ad_if_needed("BOSS模式天马座"):
                continue
            if self.recognize_template("high_energy_bomb", required=False, settle_seconds=-1.0).found:
                logging.info("BOSS模式天马座：检测到高能爆弹按钮，确认已进入战斗，开始下滑战机")
                time.sleep(3)
                self.ctrl.swipe(
                    360,
                    880,
                    360,
                    1190,
                )
                logging.info("BOSS模式天马座：战机下滑到底端完成")
                return
            logging.info("BOSS模式天马座：尚未进入战斗，等待%.1f秒后继续检测，当前第%d次检测", check_interval, round_idx)
            time.sleep(check_interval)
            round_idx += 1

    def run_boss_mode_board(self, board: str) -> None:
        board_dict: dict[str, str] = {"draco": "天龙座", "cygnus": "白鸟座", "pegasus": "天马座", "andromeda": "仙女座"}
        logging.info("BOSS模式：开始挑战%s空间站", board_dict[board])
        self.click_template(f"boss_mode_board_{board}")
        self.ensure_boss_mode_extreme_difficulty()
        self.click_template("blitz")
        self.click_template("blitz_popup")
        self.click_template("confirm") # BOSS模式闪击二次确认：确认按钮

        if board == "pegasus": # 暗黑突击特殊逻辑
            self.wait_and_drag_to_bottom()

        self.wait_and_continue_boss_mode()
        self.click_template("back")
        logging.info("BOSS模式：%s空间站挑战完成并返回板块选择页", board_dict[board])

    def run_boss_mode_flow(self) -> None:
        logging.info("========== BOSS模式流程开始 ==========")
        self.click_template("home_challenge_mode")
        self.click_template("challenge_boss_mode")

        for board in self.select_today_boss_mode_boards():
            self.run_boss_mode_board(board)

        self.back_to_home()
        logging.info("========== BOSS模式流程结束 ==========")

    # ==================== 普通星域巡航 / 深空巡航 ====================

    def _recover_to_home(self, context: str, max_steps: int = 6) -> bool:
        """仅在识别到安全导航按钮时逐层返回首页。"""
        for _ in range(max_steps):
            shot = self.wait_until_not_loading(settle_seconds=0.2)
            if self.match("home_challenge_mode", shot).found:
                logging.info("%s：已回到首页", context)
                return True
            nav_home = self.match("nav_home", shot)
            if nav_home.found:
                self.ctrl.tap(nav_home.x, nav_home.y, delay=2.0)
                continue
            back = self.match("back", shot)
            if back.found:
                self.ctrl.tap(back.x, back.y, delay=1.5)
                continue
            logging.error("%s：当前页面没有可确认的安全返回按钮，停止点击", context)
            return False
        logging.error("%s：超过%d层仍未回到首页", context, max_steps)
        return False

    def _finish_mode_flow(
        self,
        context: str,
        primary_error: Optional[BaseException],
    ) -> None:
        """结束模式流程并确认回到首页；保留主流程异常，不让恢复异常覆盖它。"""
        try:
            recovered = self._recover_to_home(context)
        except Exception as recovery_error:
            if primary_error is not None:
                logging.error(
                    "%s：异常恢复失败，保留原始异常：%s",
                    context,
                    recovery_error,
                )
                return
            raise RuntimeError(f"{context}：恢复首页时发生异常") from recovery_error

        if recovered:
            return
        if primary_error is not None:
            logging.error("%s：异常后未能确认回到首页，保留原始异常", context)
            return
        raise RuntimeError(f"{context}：流程结束但未能确认回到首页")

    @staticmethod
    def _require_template_files(names: tuple[str, ...]) -> None:
        """在开始点击前检查模式所需模板存在且可解码，避免流程中途才中断。"""
        missing: list[str] = []
        for name in names:
            spec = TEMPLATE_SPECS.get(name)
            if spec is None:
                missing.append(f"{name}（未配置）")
                continue
            template_path = TEMPLATE_DIR / str(spec["file"])
            if not template_path.is_file():
                missing.append(f"{name}（{template_path.name}）")
                continue
            try:
                image = TemplateMatcher._read_image(template_path, grayscale=False)
            except Exception as exc:
                logging.debug("模板预检读取失败 %s: %s", template_path, exc)
                missing.append(f"{name}（{template_path.name}无法解码）")
                continue
            if image.size == 0:
                missing.append(f"{name}（{template_path.name}为空）")
        if missing:
            raise RuntimeError("缺少或无效的模式模板，已在点击前停止：" + "、".join(missing))

    @staticmethod
    def _validate_battle_wait_config(config: dict, context: str) -> None:
        initial_wait = float(config["initial_wait_seconds"])
        poll_interval = float(config["poll_interval_seconds"])
        timeout = float(config["battle_timeout_seconds"])
        if initial_wait < 0 or poll_interval <= 0 or timeout <= 0 or initial_wait >= timeout:
            raise ValueError(
                f"{context}战斗等待参数必须满足 "
                "0 <= initial_wait < timeout 且 poll_interval > 0"
            )

    def _click_first_available_cruise_enemy(self) -> bool:
        shot = self.wait_until_not_loading(settle_seconds=0.3)
        candidates: list[MatchResult] = []
        for name in (
            "expedition_available_enemy",
            "expedition_available_enemy_right",
        ):
            result = self.match(name, shot)
            if result.found:
                candidates.append(result)

        if not candidates:
            logging.info("普通星域巡航：当前地图没有识别到可挑战敌人")
            return False

        target = max(candidates, key=lambda item: item.score)
        logging.info(
            "普通星域巡航：选择可挑战敌人 at (%.1f, %.1f), score=%.3f",
            target.x,
            target.y,
            target.score,
        )
        self.ctrl.tap(target.x, target.y, delay=1.8)
        # 敌机与推荐战力是动态内容；通用挑战按钮才是可靠的详情页标志。
        return self.recognize_template(
            "expedition_challenge",
            required=False,
            settle_seconds=0.3,
        ).found

    @staticmethod
    def _sleep_with_deadline(seconds: float, deadline: float) -> bool:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return False
        time.sleep(min(seconds, remaining))
        return time.monotonic() < deadline

    def _classify_battle_result(
        self,
        shot: Path,
        *,
        victory_template: Optional[str],
        defeat_template: Optional[str],
    ) -> BattleResult:
        if defeat_template and self.match(defeat_template, shot).found:
            return BattleResult.DEFEAT
        if victory_template and self.match(victory_template, shot).found:
            return BattleResult.VICTORY
        return BattleResult.COMPLETE

    def _wait_for_mode_battle_result(
        self,
        *,
        context: str,
        result_template: str,
        revive_template: str,
        revive_close_template: str,
        initial_wait: float,
        poll_interval: float,
        timeout: float,
        revive_by_ad: bool,
        victory_template: Optional[str] = None,
        defeat_template: Optional[str] = None,
    ) -> BattleResult:
        if initial_wait < 0 or poll_interval <= 0 or timeout <= 0 or initial_wait >= timeout:
            raise ValueError(
                "战斗等待参数必须满足 0 <= initial_wait < timeout 且 poll_interval > 0"
            )

        logging.info("%s：等待战斗结束", context)
        deadline = time.monotonic() + timeout
        if initial_wait and not self._sleep_with_deadline(initial_wait, deadline):
            self.screenshot(f"{context}_timeout")
            raise RuntimeError(f"{context}：{timeout:.0f}秒内未进入结算页")
        revive_attempts = 0

        while time.monotonic() < deadline:
            shot = self.screenshot(f"{context}_battle_poll")
            result = self.match(result_template, shot)
            if result.found:
                battle_result = self._classify_battle_result(
                    shot,
                    victory_template=victory_template,
                    defeat_template=defeat_template,
                )
                logging.info("%s：检测到结算继续按钮，结果=%s", context, battle_result.value)
                self.ctrl.tap(result.x, result.y, delay=2.4)
                return battle_result

            revive = self.match(revive_template, shot)
            if revive.found:
                if revive_by_ad and revive_attempts < 4:
                    revive_attempts += 1
                    logging.info("%s：第%d次使用广告复活", context, revive_attempts)
                    self.ctrl.tap(revive.x, revive.y, delay=2.0)
                    if not self._sleep_with_deadline(42.0, deadline):
                        break
                    post_ad = self.screenshot(f"{context}_post_ad")
                    post_ad_result = self.match(result_template, post_ad)
                    if post_ad_result.found:
                        battle_result = self._classify_battle_result(
                            post_ad,
                            victory_template=victory_template,
                            defeat_template=defeat_template,
                        )
                        logging.info(
                            "%s：广告等待期间战斗已结束，结果=%s",
                            context,
                            battle_result.value,
                        )
                        self.ctrl.tap(post_ad_result.x, post_ad_result.y, delay=2.4)
                        return battle_result
                    # 复活弹窗后方仍能匹配 HUD，模态弹窗必须先于背景状态判断。
                    if self.match(revive_template, post_ad).found:
                        logging.warning("%s：广告复活未生效，停止重复观看并关闭复活弹窗", context)
                        close_result = self.match(revive_close_template, post_ad)
                        if not close_result.found:
                            raise RuntimeError(f"{context}：广告复活未生效且未识别到关闭按钮")
                        self.ctrl.tap(close_result.x, close_result.y, delay=3.0)
                        revive_attempts = 4
                        continue
                    if self.match("high_energy_bomb", post_ad).found:
                        logging.info("%s：广告复活后已返回战斗", context)
                        continue

                    raise RuntimeError(
                        f"{context}：广告结束后的页面无法确认，停止点击以避免误触未知控件"
                    )

                close_result = self.match(revive_close_template, shot)
                if not close_result.found:
                    raise RuntimeError(f"{context}：检测到复活弹窗但未识别到关闭按钮")
                logging.info("%s：关闭复活弹窗；不点击钻石复活", context)
                self.ctrl.tap(close_result.x, close_result.y, delay=3.0)
                continue

            logging.info("%s：战斗尚未结束，%.1f秒后继续检测", context, poll_interval)
            if not self._sleep_with_deadline(poll_interval, deadline):
                break

        self.screenshot(f"{context}_timeout")
        raise RuntimeError(f"{context}：{timeout:.0f}秒内未进入结算页")

    def _choose_cruise_equation_if_needed(self) -> bool:
        equation_page = self.recognize_template(
            "expedition_equation_page",
            required=False,
            settle_seconds=0.8,
        )
        if not equation_page.found:
            return False

        logging.info("普通星域巡航：选择中间增益方程")
        # 三张方程卡的内容和立绘会随战斗变化，固定点击中间卡片比模板匹配稳定。
        self.ctrl.tap(360, 650, delay=0.8)
        self.ctrl.tap(360, 977, delay=2.0)
        if self.recognize_template(
            "expedition_equation_page",
            required=False,
            settle_seconds=0.2,
        ).found:
            raise RuntimeError("普通星域巡航：选择增益方程后页面未关闭")
        return True

    def _start_expedition_endless_battle(self, run_index: int) -> bool:
        sortie = self.click_template(
            "deep_space_cruise_sortie",
            required=False,
            tap_delay=3.0,
        )
        if not sortie.found:
            logging.info("深空巡航：当前没有可用的出击按钮，停止后续出击")
            return False
        battle_result = self._wait_for_mode_battle_result(
            context=f"深空巡航第{run_index}次出击",
            result_template="cruise_result_continue",
            revive_template="cruise_ad_revive",
            revive_close_template="cruise_revive_close",
            initial_wait=float(DEEP_SPACE_CRUISE_CONFIG["initial_wait_seconds"]),
            poll_interval=float(DEEP_SPACE_CRUISE_CONFIG["poll_interval_seconds"]),
            timeout=float(DEEP_SPACE_CRUISE_CONFIG["battle_timeout_seconds"]),
            revive_by_ad=bool(DEEP_SPACE_CRUISE_CONFIG["revive_by_ad"]),
            victory_template="cruise_result_victory",
            defeat_template="cruise_result_defeat",
        )
        logging.info("深空巡航第%d次出击：结算结果=%s", run_index, battle_result.value)
        if battle_result is not BattleResult.VICTORY:
            logging.warning(
                "深空巡航第%d次出击：未确认胜利，停止后续出击",
                run_index,
            )
            return False
        self.recognize_template("deep_space_cruise_page")
        return True

    def run_deep_space_cruise_flow(self) -> None:
        logging.info("========== 深空巡航流程开始 ==========")
        self._validate_battle_wait_config(DEEP_SPACE_CRUISE_CONFIG, "深空巡航")
        max_runs = int(DEEP_SPACE_CRUISE_CONFIG["max_runs"])
        if max_runs < 1:
            raise ValueError("DEEP_SPACE_CRUISE_CONFIG.max_runs 必须大于 0")
        self._require_template_files(
            (
                "loading",
                "home_challenge_mode",
                "challenge_deep_space_cruise",
                "expedition_page",
                "deep_space_cruise_entry",
                "deep_space_cruise_page",
                "deep_space_cruise_sortie",
                "deep_space_cruise_info_close",
                "cruise_result_continue",
                "cruise_result_victory",
                "cruise_result_defeat",
                "cruise_ad_revive",
                "cruise_revive_close",
                "high_energy_bomb",
                "nav_home",
                "back",
            )
        )
        primary_error: Optional[BaseException] = None
        try:
            self.click_template("home_challenge_mode")
            self.click_template("challenge_deep_space_cruise")
            self.recognize_template("expedition_page")

            # Button-ExpeditionEndless 只在本期普通星域巡航全部完成后出现。
            entry = self.click_template(
                "deep_space_cruise_entry",
                required=False,
                tap_delay=2.5,
            )
            if not entry.found:
                logging.warning("深空巡航：本期普通星域巡航尚未完成，入口未解锁，安全跳过")
            else:
                # 账号首次进入时会自动弹出规则页；只关闭已识别到的弹窗。
                self.click_template(
                    "deep_space_cruise_info_close",
                    required=False,
                    tap_delay=1.5,
                    settle_seconds=0.5,
                )
                self.recognize_template("deep_space_cruise_page")

                for run_index in range(1, max_runs + 1):
                    if not self._start_expedition_endless_battle(run_index):
                        break
        except BaseException as exc:
            primary_error = exc
            raise
        finally:
            self._finish_mode_flow("深空巡航", primary_error)
        logging.info("========== 深空巡航流程结束 ==========")

    # ==================== 超限模式 ====================

    @staticmethod
    def _overlimit_board_name(board: str) -> str:
        names = {
            "draco": "天龙座",
            "cygnus": "白鸟座",
            "pegasus": "天马座",
            "andromeda": "仙女座",
        }
        if board not in names:
            raise ValueError(f"未知超限模式空间站: {board}")
        return names[board]

    def _wait_for_overlimit_battle_start(
        self,
        *,
        context: str,
        allow_crystal_popup: bool,
        allow_force_confirm: bool = False,
        timeout: float = 15.0,
    ) -> bool:
        """点击挑战后只等待已确认的弹窗或战斗 HUD，禁止未知页面盲点。"""
        if timeout <= 0:
            raise ValueError("超限模式战斗启动等待时间必须大于 0")
        deadline = time.monotonic() + timeout
        force_confirm_clicked = False
        partial_crystal_logged = False
        while time.monotonic() < deadline:
            shot = self.screenshot(f"{context}_start_poll")
            if self.match("overlimit_mode_challenge_ended", shot).found:
                logging.warning("%s：检测到挑战已截止", context)
                return False

            if allow_crystal_popup:
                crystal_invalid = self.match("overlimit_mode_crystal_invalid", shot)
                continue_battle = self.match("overlimit_mode_continue_battle", shot)
                if crystal_invalid.found and continue_battle.found:
                    logging.info("%s：预设包含失效原晶，按当前预设继续", context)
                    # 同一截图同时确认标题和按钮后才允许点击，避开下方付费试用区。
                    self.ctrl.tap(continue_battle.x, continue_battle.y, delay=3.0)
                    return True
                if (crystal_invalid.found or continue_battle.found) and not partial_crystal_logged:
                    logging.warning("%s：原晶弹窗尚未完整渲染，继续等待", context)
                    partial_crystal_logged = True
                    if not self._sleep_with_deadline(0.4, deadline):
                        break
                    continue

            # 低战力确认弹窗是模态层；即使其背景仍能匹配战斗 HUD，也必须先处理弹窗。
            if allow_force_confirm:
                force_confirm = self.match("expedition_force_challenge_confirm", shot)
                if force_confirm.found:
                    if not force_confirm_clicked:
                        logging.info("%s：检测到低战力确认，点击无资源消耗的确认按钮", context)
                        self.ctrl.tap(force_confirm.x, force_confirm.y, delay=2.0)
                        force_confirm_clicked = True
                    else:
                        logging.info("%s：低战力确认弹窗仍在显示，继续等待其关闭", context)
                    if not self._sleep_with_deadline(0.2, deadline):
                        break
                    continue

            if self.match("high_energy_bomb", shot).found:
                logging.info("%s：检测到战斗 HUD", context)
                return True

            if not self._sleep_with_deadline(0.5, deadline):
                break

        return False

    def _run_overlimit_battle(self, *, board: str, challenge: str) -> bool:
        board_name = self._overlimit_board_name(board)
        challenge_name = "普通挑战" if challenge == "normal" else "超限挑战"
        if challenge not in {"normal", "overlimit"}:
            raise ValueError(f"未知超限模式挑战类型: {challenge}")
        context = f"超限模式{board_name}{challenge_name}"
        logging.info("%s：开始", context)

        self.click_template(f"overlimit_mode_{challenge}_challenge", tap_delay=1.5)
        if challenge == "normal":
            if not self._wait_for_overlimit_battle_start(
                context=context,
                allow_crystal_popup=False,
                allow_force_confirm=True,
            ):
                logging.warning("%s：点击后未进入战斗，停止等待结算", context)
                return False
        else:
            self.recognize_template("overlimit_mode_overlimit_dialog")
            # 只点击主挑战按钮；不触碰下方需消耗资源的 MAX 装备试用。
            self.click_template("overlimit_mode_start_challenge", tap_delay=2.0)
            if not self._wait_for_overlimit_battle_start(
                context=context,
                allow_crystal_popup=True,
            ):
                raise RuntimeError(f"{context}：点击挑战后未进入战斗或原晶提示")

        battle_result = self._wait_for_mode_battle_result(
            context=context,
            result_template="overlimit_mode_result_continue",
            revive_template="overlimit_mode_ad_revive",
            revive_close_template="overlimit_mode_revive_close",
            initial_wait=float(OVERLIMIT_MODE_CONFIG["initial_wait_seconds"]),
            poll_interval=float(OVERLIMIT_MODE_CONFIG["poll_interval_seconds"]),
            timeout=float(OVERLIMIT_MODE_CONFIG["battle_timeout_seconds"]),
            revive_by_ad=bool(OVERLIMIT_MODE_CONFIG["revive_by_ad"]),
            defeat_template="cruise_result_defeat",
        )
        logging.info("%s：结算结果=%s", context, battle_result.value)
        if battle_result is BattleResult.DEFEAT:
            logging.warning("%s：确认失败，不进入下一轮", context)
            return False
        if battle_result is BattleResult.COMPLETE:
            logging.warning(
                "%s：未识别胜负，后续仅允许由稳定完成槽位增长确认进度",
                context,
            )
        self.recognize_template("overlimit_mode_stage_page")
        logging.info("%s：完成", context)
        return True

    @staticmethod
    def _overlimit_board_count_roi(board: str) -> tuple[int, int, int, int]:
        rois = {
            "draco": (120, 535, 285, 590),
            "cygnus": (450, 685, 620, 740),
            "pegasus": (115, 945, 285, 1000),
            "andromeda": (435, 1080, 610, 1135),
        }
        if board not in rois:
            raise ValueError(f"未知超限模式空间站: {board}")
        return rois[board]

    @staticmethod
    @lru_cache(maxsize=1)
    def _get_ocr_engine():
        """延迟初始化 OCR，避免每个空间站重复加载 ONNX 模型。"""
        try:
            from rapidocr_onnxruntime import RapidOCR
        except ImportError:
            return None
        return RapidOCR()

    @classmethod
    def _read_challenge_count_from_image(
        cls,
        screenshot_path: Path,
        roi: tuple[int, int, int, int],
    ) -> Optional[int]:
        """从“完成挑战：n/12”区域读取计数；OCR 不可用或结果冲突时返回 None。"""
        engine = cls._get_ocr_engine()
        if engine is None:
            return None

        image = TemplateMatcher._read_image(screenshot_path, grayscale=False)
        x1, y1, x2, y2 = roi
        height, width = image.shape[:2]
        if not (0 <= x1 < x2 <= width and 0 <= y1 < y2 <= height):
            return None
        crop = image[y1:y2, x1:x2]
        result, _ = engine(crop)
        texts: list[str] = []
        candidates: list[tuple[int, float]] = []
        for item in result or []:
            if len(item) < 2:
                continue
            text = str(item[1])
            texts.append(text)
            try:
                confidence = float(item[2]) if len(item) > 2 else 0.0
            except (TypeError, ValueError):
                continue
            if confidence < 0.80:
                continue
            for match in re.finditer(r"(?<!\d)(\d{1,2})\s*/\s*(\d{1,2})(?!\d)", text):
                count = int(match.group(1))
                total = int(match.group(2))
                if 0 <= count <= total <= 12:
                    candidates.append((count, confidence))

        # 标题和计数有时会落在相邻文本框中；只有所有相关文本置信度足够时才拼接。
        if not candidates and texts and (result or []):
            confidences = []
            for item in result or []:
                if len(item) < 3:
                    continue
                try:
                    confidences.append(float(item[2]))
                except (TypeError, ValueError):
                    pass
            if confidences and min(confidences) >= 0.80:
                joined = " ".join(texts)
                for match in re.finditer(
                    r"(?<!\d)(\d{1,2})\s*/\s*(\d{1,2})(?!\d)",
                    joined,
                ):
                    count = int(match.group(1))
                    total = int(match.group(2))
                    if 0 <= count <= total <= 12:
                        candidates.append((count, min(confidences)))

        if not candidates:
            return None
        best_confidence = max(confidence for _, confidence in candidates)
        best_counts = {
            count
            for count, confidence in candidates
            if confidence >= best_confidence - 0.05
        }
        if len(best_counts) != 1:
            return None
        return next(iter(best_counts))

    def _get_overlimit_board_count(
        self,
        board: str,
        shot: Optional[Path] = None,
        confirm: bool = True,
    ) -> Optional[int]:
        """读取并确认空间站完成槽位计数，避免单帧 OCR 误触发挑战。"""
        first_shot = shot or self.screenshot(f"overlimit_{board}_count")
        roi = self._overlimit_board_count_roi(board)
        first_count = self._read_challenge_count_from_image(first_shot, roi)
        if confirm and first_count is not None:
            time.sleep(0.15)
            second_shot = self.screenshot(f"overlimit_{board}_count_confirm")
            second_count = self._read_challenge_count_from_image(second_shot, roi)
            if second_count != first_count:
                logging.warning(
                    "超限模式%s：连续两帧完成挑战次数不一致，安全跳过",
                    self._overlimit_board_name(board),
                )
                return None
        count = first_count
        if count is None:
            logging.warning("超限模式%s：无法读取完成挑战次数", self._overlimit_board_name(board))
        else:
            logging.info("超限模式%s：当前完成挑战%d（聚合完成槽位）", self._overlimit_board_name(board), count)
        return count

    def _return_to_overlimit_board_page(self) -> bool:
        """从空间站详情返回选择页；没有明确页面标志时不点击。"""
        if self.recognize_template(
            "overlimit_mode_page",
            required=False,
            settle_seconds=0.2,
        ).found:
            return True
        if not self.recognize_template(
            "overlimit_mode_stage_page",
            required=False,
            settle_seconds=0.2,
        ).found:
            return False
        if not self.click_template("back", required=False, tap_delay=1.5).found:
            return False
        return self.recognize_template(
            "overlimit_mode_page",
            required=False,
            settle_seconds=0.2,
        ).found

    def run_overlimit_mode_board(
        self,
        board: str,
        count_before: Optional[int] = None,
    ) -> Optional[int]:
        """按聚合完成槽位计数逐轮处理一个空间站，未增长时立即停止。"""
        board_name = self._overlimit_board_name(board)
        target_runs = int(OVERLIMIT_MODE_CONFIG["target_runs_per_board"])
        if target_runs < 0 or target_runs > 12:
            raise ValueError("OVERLIMIT_MODE_CONFIG.target_runs_per_board 必须在 0..12")
        logging.info("超限模式：进入%s空间站", board_name)

        if count_before is None:
            count_before = self._get_overlimit_board_count(board)
        if count_before is None:
            logging.warning("超限模式：无法确认%s挑战次数，安全跳过", board_name)
            return None
        if count_before >= target_runs:
            logging.info(
                "超限模式%s：当前完成挑战%d，已达到目标%d",
                board_name,
                count_before,
                target_runs,
            )
            return count_before

        current_count = count_before
        stage_open = False
        primary_error: Optional[BaseException] = None
        try:
            while current_count < target_runs:
                if not stage_open:
                    entry = self.click_template(
                        f"overlimit_mode_board_{board}",
                        required=False,
                        tap_delay=2.0,
                    )
                    if not entry.found:
                        logging.info("超限模式：未识别到%s空间站，跳过", board_name)
                        return current_count
                    if not self.recognize_template("overlimit_mode_stage_page").found:
                        return current_count
                    stage_open = True

                normal_cleared = self.recognize_template(
                    "overlimit_mode_normal_cleared",
                    required=False,
                    settle_seconds=0.2,
                ).found
                if normal_cleared:
                    logging.info("超限模式%s空间站：普通挑战已通关", board_name)
                    challenge = "overlimit"
                    if not bool(OVERLIMIT_MODE_CONFIG["run_overlimit_challenge"]):
                        logging.info("超限模式%s：已关闭超限挑战，停止", board_name)
                        return current_count
                else:
                    challenge = "normal"
                    if not bool(OVERLIMIT_MODE_CONFIG["run_normal_challenge"]):
                        logging.warning(
                            "超限模式%s空间站：普通挑战未通关且已关闭普通挑战，停止",
                            board_name,
                        )
                        return current_count

                if not self._run_overlimit_battle(board=board, challenge=challenge):
                    logging.warning("超限模式%s：%s未能启动，停止本站后续挑战", board_name, challenge)
                    return current_count

                if not self._return_to_overlimit_board_page():
                    raise RuntimeError(
                        f"超限模式{board_name}：战斗后未能确认回到空间站选择页"
                    )
                stage_open = False
                count_after = self._get_overlimit_board_count(board)
                if count_after is None:
                    logging.warning("超限模式%s：战斗后无法确认完成槽位变化，停止", board_name)
                    return current_count
                if count_after < current_count:
                    raise RuntimeError(f"超限模式{board_name}：挑战次数异常回退")
                if count_after == current_count:
                    logging.warning("超限模式%s：本轮完成槽位未增加，停止避免重复消耗", board_name)
                    return current_count
                current_count = count_after

            return current_count
        except BaseException as exc:
            primary_error = exc
            raise
        finally:
            if stage_open:
                try:
                    returned = self._return_to_overlimit_board_page()
                except Exception as recovery_error:
                    if primary_error is None:
                        raise RuntimeError(
                            f"超限模式{board_name}：退出空间站详情时发生异常"
                        ) from recovery_error
                    logging.error(
                        "超限模式%s：异常恢复失败，保留原始异常：%s",
                        board_name,
                        recovery_error,
                    )
                else:
                    if not returned:
                        if primary_error is None:
                            raise RuntimeError(f"超限模式{board_name}：退出空间站详情失败")
                        logging.error(
                            "超限模式%s：异常后未能退出空间站详情，保留原始异常",
                            board_name,
                        )

    def run_overlimit_mode_flow(self) -> None:
        logging.info("========== 超限模式流程开始 ==========")
        self._validate_battle_wait_config(OVERLIMIT_MODE_CONFIG, "超限模式")
        target_runs = int(OVERLIMIT_MODE_CONFIG["target_runs_per_board"])
        if target_runs < 0 or target_runs > 12:
            raise ValueError("OVERLIMIT_MODE_CONFIG.target_runs_per_board 必须在 0..12")
        if target_runs == 0:
            logging.info("超限模式：目标完成槽位为0，跳过全部挑战")
            return
        boards = tuple(str(board) for board in OVERLIMIT_MODE_CONFIG["boards"])
        for board in boards:
            self._overlimit_board_name(board)
        template_names = [
            "loading",
            "home_challenge_mode",
            "challenge_boss_mode",
            "boss_mode_overlimit_entry",
            "overlimit_mode_page",
            "overlimit_mode_stage_page",
            "overlimit_mode_normal_cleared",
            "overlimit_mode_challenge_ended",
            "overlimit_mode_result_continue",
            "cruise_result_defeat",
            "overlimit_mode_ad_revive",
            "overlimit_mode_revive_close",
            "high_energy_bomb",
            "nav_home",
            "back",
        ]
        template_names.extend(
            f"overlimit_mode_board_{str(board)}"
            for board in OVERLIMIT_MODE_CONFIG["boards"]
        )
        if bool(OVERLIMIT_MODE_CONFIG["run_normal_challenge"]):
            template_names.extend(
                (
                    "overlimit_mode_normal_challenge",
                    "expedition_force_challenge_confirm",
                )
            )
        if bool(OVERLIMIT_MODE_CONFIG["run_overlimit_challenge"]):
            template_names.extend(
                (
                    "overlimit_mode_overlimit_challenge",
                    "overlimit_mode_overlimit_dialog",
                    "overlimit_mode_start_challenge",
                    "overlimit_mode_crystal_invalid",
                    "overlimit_mode_continue_battle",
                )
            )
        self._require_template_files(tuple(template_names))
        primary_error: Optional[BaseException] = None
        try:
            self.click_template("home_challenge_mode")
            self.click_template("challenge_boss_mode")
            entry = self.click_template("boss_mode_overlimit_entry", required=False, tap_delay=2.0)
            if not entry.found:
                logging.info("超限模式：当前活动入口不存在，结束流程")
            else:
                self.recognize_template("overlimit_mode_page")

                for board in boards:
                    count = self._get_overlimit_board_count(board)
                    # 计数不可读时安全跳过，避免重复消耗挑战次数和广告。
                    if count is None:
                        continue
                    if count >= target_runs:
                        logging.info(
                            "超限模式%s：已达到目标%d个完成槽位，本次跳过",
                            self._overlimit_board_name(board),
                            target_runs,
                        )
                        continue
                    self.run_overlimit_mode_board(board, count_before=count)
        except BaseException as exc:
            primary_error = exc
            raise
        finally:
            self._finish_mode_flow("超限模式", primary_error)
        logging.info("========== 超限模式流程结束 ==========")

    # ==================== 无尽模式 ====================

    def wait_and_claim_endless_reward(
        self,
        check_interval: int = 20, # 每20秒检测一次战斗/结算状态
        # timeout: float = 480.0, # 最多等待8分钟进入奖励领取页
    ) -> None:
        # deadline = time.monotonic() + timeout
        logging.info("等待无尽模式战斗中......")
        time.sleep(150) # 固定等待150秒

        crash_triggered = False
        round_idx = 1
        while True:
            if self.click_template("reward_claim", required=False, settle_seconds=-1.0).found:
                logging.info("无尽模式：检测到结算奖励页并完成领取")
                self.click_template("continue")
                self.click_template("back")
                break

            if not crash_triggered and \
                (self.recognize_template("endless_chest_4", required=False, settle_seconds=-1.0).found or \
                 self.recognize_template("endless_chest_5", required=False, settle_seconds=-1.0).found or \
                 self.recognize_template("endless_chest_6", required=False, settle_seconds=-1.0).found):
                logging.info("无尽模式：检测到宝箱数量达到4、5或6，执行上划等待坠机")
                self.ctrl.swipe(
                    360,
                    975, # 初始位置
                    360,
                    330,
                )
                crash_triggered = True

            logging.info("无尽模式：尚未进入奖励领取页，等待%d秒后继续检测，当前第%d次检测", check_interval, round_idx)
            time.sleep(check_interval)
            round_idx += 1

        # raise RuntimeError(f"无尽模式：{timeout:.0f} 秒内未进入奖励领取页")

    def run_endless_world_competition_once(self, round_index: int) -> None:
        logging.info("无尽模式：开始第%d次世界竞赛钻石赛场", round_index)
        self.click_template("endless_entry_diamond_20")
        self.click_template("endless_sortie")

        if round_index == 1:
            logging.info("无尽模式：购买战前准“烈火x1”")
            self.click_template("endless_fire_buy_200")

        self.click_template("blitz")
        self.click_template("blitz_popup")
        self.click_template("confirm") # 无尽模式闪击部分战斗道具不足：确认

        self.wait_and_claim_endless_reward()
        logging.info("无尽模式：第%d次世界竞赛完成并返回竞赛页", round_index)

    def run_endless_mode_flow(self, runs: int = 2) -> None: # 默认执行两轮无尽世界竞赛
        logging.info("========== 无尽模式流程开始 ==========")
        self.click_template("home_endless_mode")
        self.click_template("endless_mode_known", required=False, settle_seconds=4.8) # 可能会出现本周超频装备信息界面，需要先点击 知道了 按钮
        self.click_template("endless_world_competition")

        for round_index in range(1, runs + 1):
            self.run_endless_world_competition_once(round_index)

        self.back_to_home()
        logging.info("========== 无尽模式流程结束 ==========")

    # ==================== 消息、活跃度、奖励领取 ====================

    def claim_information_rewards(self) -> None:
        logging.info("领取首页消息奖励")
        self.click_template("home_information")
        logging.info("切换助战页面")
        self.click_template("home_information_assist_battle")
        self.click_template("home_information_claim_all")
        self.click_template("reward_claim", required=False)
        logging.info("切换系统页面")
        self.click_template("home_information_system")
        self.click_template("home_information_claim_all")
        self.click_template("reward_claim", required=False)
        logging.info("点击底部回到首页")
        self.tap_position("exit_mid_down")
        self.deal_endless_mode_event_when_back_to_home()

    def claim_activity_rewards(self) -> None:
        logging.info("领取首页活跃度奖励")
        self.click_template("home_activity")
        if self.click_template("activity_claim_all", required=False).found:
            self.click_template("reward_claim")
        else:
            logging.info("活跃任务页未识别到一键领取按钮，可能已领取")
        self.click_template("back")
        self.deal_endless_mode_event_when_back_to_home()


    def claim_home_rewards(self) -> None:
        logging.info("领取首页奖励页第一个奖励")
        self.click_template("home_reward")
        if self.click_template("home_reward_claim", required=False).found:
            self.click_template("reward_claim")
        else:
            logging.info("奖励页未识别到第一个领取按钮，可能已领取")
        self.tap_position("exit_mid_down")
        self.deal_endless_mode_event_when_back_to_home()

    def run_daily_rewards_flow(self) -> None:
        logging.info("========== 消息、活跃度、奖励领取流程开始 ==========")
        # self.claim_information_rewards() # 在游戏圈中已经执行过了
        self.claim_activity_rewards()
        self.claim_home_rewards()
        logging.info("========== 消息、活跃度、奖励领取流程结束 ==========")

    # ==================== 总流程 ====================

    def run(self) -> None:
        logging.info("========== 日活基本流程开始 ==========")
        execution_plan = (
            ("redemption_code", self.run_redemption_code_flow),
            ("game_circle", self.run_game_circle_flow),
            ("decade_reunion", self.run_decade_reunion_flow),
            ("shop", self.run_shop_gift_flow),
            ("interstellar", self.run_interstellar_flow),
            ("stamina", self.run_stamina_flow),
            ("team", self.run_team_expedition_and_donation_flow),
            ("backpack", self.run_backpack_space_flow),
            ("treasure_hunt", self.run_treasure_hunt_flow),
            ("event_stage", self.run_event_stage_flow),
            ("level_sweep", self.run_level_sweep_flow),
            ("backpack", self.run_resource_sale_only_flow),
            ("deep_space_cruise", self.run_deep_space_cruise_flow),
            ("boss_mode", self.run_boss_mode_flow),
            ("overlimit_mode", self.run_overlimit_mode_flow),
            ("endless_mode", self.run_endless_mode_flow),
            ("backpack", self.run_equipment_synthesis_and_split_flow),
            ("daily_rewards", self.run_daily_rewards_flow),
        )
        selected_sections = set(self.sections)
        known_sections = {section for section, _ in execution_plan}
        unknown_sections = selected_sections - known_sections
        if unknown_sections:
            raise ValueError(f"未知流程模块: {sorted(unknown_sections)}")

        for section, flow in execution_plan:
            if section in selected_sections:
                flow()
        logging.info("========== 日活基本流程结束 ==========")


def setup_logging(save_logs: bool = DEFAULT_SAVE_LOGS) -> Optional[Path]:
    log_file: Optional[Path] = None
    handlers: list[logging.Handler] = [logging.StreamHandler()]
    if save_logs:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        log_file = LOG_DIR / f"daily_run_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        handlers.insert(0, logging.FileHandler(log_file, encoding="utf-8"))
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=handlers,
        force=True,
    )
    return log_file


def parse_sections(value: str) -> list[str]:
    allowed = {
        "redemption_code",
        "game_circle",
        "decade_reunion",
        "shop",
        "interstellar",
        "stamina",
        "team",
        "backpack",
        "treasure_hunt",
        "event_stage",
        "level_sweep",
        "deep_space_cruise",
        "boss_mode",
        "overlimit_mode",
        "endless_mode",
        "daily_rewards",
    }
    sections = [item.strip() for item in value.split(",") if item.strip()]
    unknown = [item for item in sections if item not in allowed]
    if unknown:
        raise argparse.ArgumentTypeError(f"未知流程模块: {unknown}，可选: {sorted(allowed)}")
    if not sections:
        raise argparse.ArgumentTypeError("--sections 不能为空")
    return sections


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="雷霆战机：集结 - 电脑端微信窗口日活基本流程自动执行")
    parser.add_argument(
        "--capture-method",
        choices=["printwindow", "mss"],
        default=DEFAULT_CAPTURE_METHOD,
        help="截图方式：printwindow 可尝试遮挡截图；mss 需要窗口可见且不被遮挡",
    )
    parser.add_argument(
        "--click-method",
        choices=["message", "foreground"],
        default=DEFAULT_CLICK_METHOD,
        help="点击方式：message 后台消息点击；foreground 激活窗口后真实点击",
    )
    parser.add_argument(
        "--no-force-client-size",
        dest="force_client_size",
        action="store_false",
        default=DEFAULT_FORCE_CLIENT_SIZE,
        help="关闭客户区尺寸自动调整；初始尺寸不匹配时只记录警告",
    )
    parser.add_argument(
        "--client-width",
        type=int,
        default=TARGET_CLIENT_WIDTH,
        help="游戏窗口目标客户区宽度，默认720",
    )
    parser.add_argument(
        "--client-height",
        type=int,
        default=TARGET_CLIENT_HEIGHT,
        help="游戏窗口目标客户区高度，默认1280",
    )
    parser.add_argument(
        "--toolbox-client-width",
        type=int,
        default=TOOLBOX_CLIENT_WIDTH,
        help="Yang昜工具箱目标客户区宽度，默认414",
    )
    parser.add_argument(
        "--toolbox-client-height",
        type=int,
        default=TOOLBOX_CLIENT_HEIGHT,
        help="Yang昜工具箱目标客户区高度，默认780",
    )
    parser.add_argument(
        "--save-screenshots",
        dest="save_screenshots",
        action="store_true",
        default=DEFAULT_SAVE_SCREENSHOTS,
        help="保存运行过程中的历史截图；不加时仅覆盖 .runtime/current_screenshot.png 供识别使用",
    )
    parser.add_argument(
        "--save-logs",
        dest="save_logs",
        action="store_true",
        default=DEFAULT_SAVE_LOGS,
        help="保存 logs/daily_run_*.log 日志文件；不加时只输出到终端或 GUI 日志窗口",
    )
    parser.add_argument(
        "--enable-resource-sale",
        action="store_true",
        default=DEFAULT_ENABLE_RESOURCE_SALE,
        help="在背包空间处理流程中启用资源残骸出售；默认关闭",
    )
    parser.add_argument(
        "--sections",
        type=parse_sections,
        default=parse_sections("redemption_code,game_circle,decade_reunion,shop,interstellar,stamina,team,backpack,treasure_hunt,event_stage,level_sweep,boss_mode,endless_mode,daily_rewards"),
        help="选择执行模块，用逗号分隔；执行顺序由总流程固定。可选：redemption_code,game_circle,decade_reunion,shop,interstellar,stamina,team,backpack,treasure_hunt,event_stage,level_sweep,deep_space_cruise,boss_mode,overlimit_mode,endless_mode,daily_rewards。深空巡航和超限模式默认不执行，需显式选择",
    )
    parser.add_argument("--list-windows", action="store_true", help="精确列出配置中的游戏窗口后退出")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    log_file = setup_logging(save_logs=args.save_logs)
    try:
        if args.list_windows:
            items = WindowsController.list_windows(DEFAULT_WINDOW_TITLE)
            items = [item for item in items if item.title == DEFAULT_WINDOW_TITLE]
            for item in items:
                l, t, r, b = item.client_rect_screen
                logging.info(
                    "窗口 hwnd=%s title=%r class=%s client_rect=%s size=%dx%d",
                    item.hwnd, item.title, item.class_name, item.client_rect_screen, r-l, b-t,
                )
            return

        game_controller = WindowsController(
            window_title=DEFAULT_WINDOW_TITLE,
            capture_method=args.capture_method,
            click_method=args.click_method,
            client_width=args.client_width,
            client_height=args.client_height,
            force_client_size=args.force_client_size,
        )
        toolbox_controller: Optional[WindowsController] = None
        if "redemption_code" in args.sections:
            toolbox_controller = WindowsController(
                window_title=DEFAULT_TOOLBOX_WINDOW_TITLE,
                capture_method=args.capture_method,
                click_method=args.click_method,
                client_width=args.toolbox_client_width,
                client_height=args.toolbox_client_height,
                force_client_size=args.force_client_size,
            )
        runner = DailyFlowRunner(
            game_controller=game_controller,
            toolbox_controller=toolbox_controller,
            sections=args.sections,
            save_screenshots=args.save_screenshots,
            enable_resource_sale=args.enable_resource_sale,
        )
        runner.run()
        if log_file is not None:
            logging.info("日志文件：%s", log_file)
        else:
            logging.info("日志文件：未保存")
    except Exception as exc:
        logging.exception("流程执行失败：%s", exc)
        raise


if __name__ == "__main__":
    main()
