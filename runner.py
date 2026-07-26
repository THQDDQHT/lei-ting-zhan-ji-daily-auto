from __future__ import annotations

import argparse
import logging
import re
import time
from datetime import datetime
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
    DEFAULT_NO_FORCE_CLIENT_SIZE,
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

    def wait_until_not_loading( # 后续新增其他的加载动画，也可以等待（做法：新增传参）。或者新增函数def wait_until()，函数功能会类似旧click_template，多次尝试识别一个模版
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
            # time.sleep(3.6) # 进入十年集结动画时间
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
        logging.info("步骤1：从首页进入星际探索")
        self.click_template("home_interstellar")

    def claim_interstellar_income(self) -> None:
        logging.info("步骤2：星际探索页面领取累计收益，若在冷却中则跳过领取")
        if self.click_template("star_claim", required=False).found:
            self.click_template("reward_claim")

    def run_quick_exploration(self) -> None:
        """开始4次快速探索。"""
        logging.info("步骤3：执行快速探索")

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

    # def exit_interstellar_to_home(self) -> None:
    #     logging.info("步骤4：点击底部退出星际探索回到首页")
    #     self.tap_position("exit_mid_down")
    #     self.tap_position("exit_mid_down") # 再次点击底部，应对无法进入广告的情况，确保回到首页。

    def run_interstellar_flow(self) -> None:
        logging.info("========== 星际探索领取开始 ==========")
        self.enter_interstellar()
        self.claim_interstellar_income()
        self.run_quick_exploration()
        # self.exit_interstellar_to_home()
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
                time.sleep(140.0)
                self.click_template("team_expedition_confirm")
                round_idx += 1
            if self.click_template("team_expedition_claim", required=False).found:
                logging.info("已领取今日伤害奖励")
                self.click_template("reward_claim")
            logging.info("返回战队界面")
            self.click_template("back")
        else:
            logging.info("战队征讨——公示中，不进行征讨")
        logging.info("战队征讨结束")
    
    # TEAM_DONATION_ROUNDS = 3 #之后要改掉，不要固定循环次数，这样可以避免中途处bug退出，但是又无法重新执行，识别3/3

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

        # for idx in range(1, self.TEAM_DONATION_ROUNDS + 1):
        #     logging.info("战队金币捐献：第%d/%d次", idx, self.TEAM_DONATION_ROUNDS)
        #     self.click_template("team_coin_donate")
        #     self.click_template("reward_claim")

        # for idx in range(1, self.TEAM_DONATION_ROUNDS + 1):
        #     logging.info("战队钻石捐献：第%d/%d次", idx, self.TEAM_DONATION_ROUNDS)
        #     self.click_template("team_diamond_donate")
        #     self.click_template("team_diamond_donate_confirm")
        #     self.click_template("reward_claim")

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
            
            # self.recognize_template("select_split_equipment", required=False) # 可能识别到：1.loading 2.拆分动画 3.select_split_equipment，因此做一个保障，防止self.click_template("enter_synthesis")的时候刚好在动画播放过程
            # time.sleep(2.4) # 拆分动画占空时间，现在可以用settle_seconds解决
            # idx = 1
            # while True:
            #     time.sleep(1.0)
            #     if self.recognize_template("select_split_equipment", required=False).found:
            #         # 检测到select_split_equipment重新出现，说明拆分动画完成。
            #         break
            #     idx += 1
            #     if idx > 10:  # 防止无限循环
            #         logging.error("装备拆分循环异常，强制跳出循环")
            #         break

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
        time.sleep(1.2) # 星辉出现动画时间
        if self.click_template("claim_star", required=False).found:
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

                #
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
                        self.click_template("back", settle_seconds=4.8) # 无尽争霸赛返回按钮，返回之后会退回到首页，吗？？TODO 实测好像不是这样
                        # self.click_template("home_challenge_mode")
                    self.reopen_quick_sweep(difficulty)
                #

                # if self.click_template("join_now", required=False, tap_delay=5.4).found: # 此处在每周开始还会出现超频装备
                #     logging.info("无尽限时小组赛/无尽争霸赛事件已出现，立即参加后返回闯关模式继续关卡扫荡")
                #     self.click_template("limited_time_group_match_close", tap_delay=3.6, required=False) # 无尽限时小组赛关闭按钮
                #     if self.click_template("back", tap_delay=3.6, required=False).found: # 无尽争霸赛返回按钮，返回之后会退回到首页
                #         self.click_template("home_challenge_mode")
                #     self.reopen_quick_sweep(difficulty)

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
            ("boss_mode", self.run_boss_mode_flow),
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
        "boss_mode",
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
        action="store_true",
        default=DEFAULT_NO_FORCE_CLIENT_SIZE,
        help="不自动调整游戏和Yang昜工具箱客户区尺寸，但仍严格校验",
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
        help="选择执行模块，用逗号分隔；执行顺序由总流程固定。可选：redemption_code,game_circle,decade_reunion,shop,interstellar,stamina,team,backpack,treasure_hunt,event_stage,level_sweep,boss_mode,endless_mode,daily_rewards。默认全部执行",
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
            no_force_client_size=args.no_force_client_size,
        )
        toolbox_controller: Optional[WindowsController] = None
        if "redemption_code" in args.sections:
            toolbox_controller = WindowsController(
                window_title=DEFAULT_TOOLBOX_WINDOW_TITLE,
                capture_method=args.capture_method,
                click_method=args.click_method,
                client_width=args.toolbox_client_width,
                client_height=args.toolbox_client_height,
                no_force_client_size=args.no_force_client_size,
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
