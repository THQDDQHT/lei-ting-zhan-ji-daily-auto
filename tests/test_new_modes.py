from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import pytest

import runner as runner_module
from config import (
    BATTLE_ASSIST_CONFIG,
    CRUISE_FIGHTER_CONFIG,
    OVERLIMIT_MODE_CONFIG,
    TEMPLATE_DIR,
    TEMPLATE_SPECS,
)
from runner import BattleAssistState, BattleResult, DailyFlowRunner, parse_sections
from vision import MatchResult, TemplateMatcher


DEEP_SPACE_TEMPLATE_NAMES = (
    "deep_space_cruise_entry",
    "deep_space_cruise_page",
    "deep_space_cruise_sortie",
    "deep_space_cruise_info_close",
)


def result(
    found: bool,
    *,
    x: float = 360,
    y: float = 640,
    score: float | None = None,
) -> MatchResult:
    return MatchResult(
        found=found,
        score=(1.0 if found else 0.0) if score is None else score,
        x=x,
        y=y,
        top_left=(0, 0),
        bottom_right=(1, 1),
        template_size=(1, 1),
    )


class FakeController:
    def __init__(self) -> None:
        self.taps: list[tuple[float, float, float]] = []
        self.swipes: list[tuple[float, float, float, float, float]] = []
        self.events: list[tuple[str, tuple[float, ...]]] = []

    def tap(self, x: float, y: float, delay: float = 0.8) -> None:
        self.taps.append((x, y, delay))
        self.events.append(("tap", (x, y, delay)))

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
        self.swipes.append((x1, y1, x2, y2, duration))
        self.events.append(
            (
                "swipe",
                (x1, y1, x2, y2, duration, press_delay, release_delay, delay),
            )
        )

    def screenshot(self, path: str | Path) -> Path:
        return Path(path)


@pytest.fixture
def flow() -> DailyFlowRunner:
    return DailyFlowRunner(FakeController(), None, sections=["deep_space_cruise"])


def test_new_sections_are_allowed() -> None:
    assert parse_sections("deep_space_cruise,overlimit_mode") == [
        "deep_space_cruise",
        "overlimit_mode",
    ]


def test_battle_assist_defaults_match_authorized_spending_and_overlimit_goal() -> None:
    assert BATTLE_ASSIST_CONFIG["enabled"] is True
    assert BATTLE_ASSIST_CONFIG["allowed_diamond_revive_costs"] == (40,)
    assert BATTLE_ASSIST_CONFIG["max_paid_revives_per_battle"] == 1
    assert BATTLE_ASSIST_CONFIG["max_bombs_per_life"] == 1
    assert OVERLIMIT_MODE_CONFIG["boards"] == (
        "draco",
        "cygnus",
        "pegasus",
        "andromeda",
    )
    assert OVERLIMIT_MODE_CONFIG["target_runs_per_board"] == 9
    assert OVERLIMIT_MODE_CONFIG["use_max_equipment_trial"] is True
    assert OVERLIMIT_MODE_CONFIG["max_equipment_trial_expected_cost"] == 200
    assert OVERLIMIT_MODE_CONFIG["max_equipment_trial_purchase_attempt_limit"] == 16
    assert TEMPLATE_SPECS["overlimit_mode_start_challenge"]["grayscale"] is True


def test_battle_actions_prioritize_shield_over_bomb(
    flow: DailyFlowRunner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = dict(BATTLE_ASSIST_CONFIG)
    config.update(
        {
            "shield_retry_seconds": 10.0,
            "shield_protection_seconds": 5.0,
            "bomb_initial_delay_seconds": 12.0,
            "bomb_min_interval_seconds": 30.0,
            "move_enabled": False,
        }
    )
    monkeypatch.setattr(
        flow,
        "match",
        lambda name, _shot: result(name == "high_energy_bomb", x=81, y=1096),
    )
    state = BattleAssistState(life_started_at=0.0, battle_confirmed=True)

    flow._perform_battle_actions(Path("battle.png"), state, now=20.0, config=config)

    assert flow.ctrl.taps == [(*config["shield_position"], 0.1)]
    assert state.bombs_used_this_life == 0

    flow._perform_battle_actions(Path("battle.png"), state, now=26.0, config=config)

    assert flow.ctrl.taps[-1] == (81, 1096, 0.1)
    assert state.bombs_used_this_life == 1


def test_battle_actions_rate_limit_bomb_and_alternate_movement(
    flow: DailyFlowRunner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = dict(BATTLE_ASSIST_CONFIG)
    config.update(
        {
            "shield_enabled": False,
            "bomb_enabled": False,
            "move_enabled": True,
            "move_initial_delay_seconds": 2.0,
            "move_interval_seconds": 5.0,
            "move_positions": ((360, 980), (170, 980), (550, 980)),
        }
    )
    monkeypatch.setattr(
        flow,
        "match",
        lambda name, _shot: result(name == "high_energy_bomb", x=81, y=1096),
    )
    state = BattleAssistState(life_started_at=0.0, battle_confirmed=True)

    flow._perform_battle_actions(Path("battle.png"), state, now=2.0, config=config)
    flow._perform_battle_actions(Path("battle.png"), state, now=4.0, config=config)
    flow._perform_battle_actions(Path("battle.png"), state, now=7.0, config=config)

    assert flow.ctrl.swipes == [
        (360, 980, 170, 980, config["move_duration_seconds"]),
        (170, 980, 550, 980, config["move_duration_seconds"]),
    ]


def test_battle_actions_do_nothing_without_confirmed_hud(
    flow: DailyFlowRunner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(flow, "match", lambda *_args, **_kwargs: result(False))
    state = BattleAssistState(life_started_at=0.0)

    action = flow._perform_battle_actions(
        Path("loading.png"),
        state,
        now=60.0,
        config=BATTLE_ASSIST_CONFIG,
    )

    assert action is None
    assert flow.ctrl.events == []


def test_battle_actions_start_life_timer_when_hud_is_first_confirmed(
    flow: DailyFlowRunner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = dict(BATTLE_ASSIST_CONFIG)
    config.update(
        {
            "shield_enabled": False,
            "bomb_enabled": False,
            "move_initial_delay_seconds": 3.0,
        }
    )
    monkeypatch.setattr(
        flow,
        "match",
        lambda name, _shot: result(name == "high_energy_bomb", x=81, y=1096),
    )
    state = BattleAssistState(life_started_at=0.0)

    action = flow._perform_battle_actions(
        Path("battle.png"),
        state,
        now=60.0,
        config=config,
    )

    assert action is None
    assert state.battle_confirmed is True
    assert state.life_started_at == 60.0
    assert flow.ctrl.events == []


def test_battle_actions_use_due_bomb_before_movement(
    flow: DailyFlowRunner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = dict(BATTLE_ASSIST_CONFIG)
    config.update(
        {
            "shield_enabled": False,
            "bomb_enabled": True,
            "bomb_initial_delay_seconds": 2.0,
            "move_enabled": True,
            "move_initial_delay_seconds": 2.0,
        }
    )
    monkeypatch.setattr(
        flow,
        "match",
        lambda name, _shot: result(name == "high_energy_bomb", x=81, y=1096),
    )
    state = BattleAssistState(life_started_at=0.0, battle_confirmed=True)

    action = flow._perform_battle_actions(
        Path("battle.png"),
        state,
        now=2.0,
        config=config,
    )

    assert action == "bomb"
    assert flow.ctrl.taps == [(81, 1096, 0.1)]
    assert flow.ctrl.swipes == []


def test_battle_actions_move_when_due_bomb_is_not_currently_visible(
    flow: DailyFlowRunner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = dict(BATTLE_ASSIST_CONFIG)
    config.update(
        {
            "shield_enabled": False,
            "bomb_enabled": True,
            "bomb_initial_delay_seconds": 2.0,
            "move_enabled": True,
            "move_initial_delay_seconds": 2.0,
        }
    )
    monkeypatch.setattr(flow, "match", lambda *_args, **_kwargs: result(False))
    state = BattleAssistState(life_started_at=0.0, battle_confirmed=True)

    action = flow._perform_battle_actions(
        Path("battle.png"),
        state,
        now=2.0,
        config=config,
    )

    assert action == "move"
    assert flow.ctrl.taps == []
    assert flow.ctrl.swipes == [(360, 980, 170, 980, config["move_duration_seconds"])]


@pytest.mark.parametrize("cost, expected", [(40, True), (60, False), (None, False)])
def test_paid_revive_only_accepts_exactly_40_once(
    flow: DailyFlowRunner,
    monkeypatch: pytest.MonkeyPatch,
    cost: int | None,
    expected: bool,
) -> None:
    monkeypatch.setattr(flow, "_read_revive_diamond_cost", lambda _shot, _config: cost)
    monkeypatch.setattr(flow, "screenshot", lambda _tag: Path("revive_confirm.png"))
    monkeypatch.setattr(
        flow,
        "match",
        lambda name, shot: result(name == "close" and shot.name == "revive_confirm.png"),
    )
    state = BattleAssistState(life_started_at=0.0)

    used = flow._try_paid_revive(
        Path("revive.png"),
        state,
        now=10.0,
        config=BATTLE_ASSIST_CONFIG,
        revive_close_template="close",
    )

    assert used is expected
    if expected:
        assert flow.ctrl.taps == [(*BATTLE_ASSIST_CONFIG["diamond_revive_position"], 2.0)]
        assert state.paid_revives_used == 1
        assert not flow._try_paid_revive(
            Path("revive_again.png"),
            state,
            now=20.0,
            config=BATTLE_ASSIST_CONFIG,
            revive_close_template="close",
        )
        assert len(flow.ctrl.taps) == 1
    else:
        assert flow.ctrl.taps == []


def test_paid_revive_requires_two_matching_40_cost_frames(
    flow: DailyFlowRunner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    costs = iter([40, 60])
    monkeypatch.setattr(flow, "_read_revive_diamond_cost", lambda *_args: next(costs))
    monkeypatch.setattr(flow, "screenshot", lambda _tag: Path("revive_confirm.png"))
    monkeypatch.setattr(
        flow,
        "match",
        lambda name, shot: result(name == "close" and shot.name == "revive_confirm.png"),
    )

    assert not flow._try_paid_revive(
        Path("revive.png"),
        BattleAssistState(life_started_at=0.0),
        now=10.0,
        config=BATTLE_ASSIST_CONFIG,
        revive_close_template="close",
    )
    assert flow.ctrl.taps == []


def test_select_best_cruise_fighter_uses_highest_ocr_power(
    flow: DailyFlowRunner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(flow, "screenshot", lambda _tag: Path("fighters.png"))
    monkeypatch.setattr(
        flow,
        "_read_fighter_power_candidates",
        lambda _shot, _config: [(40047, 250.0, 850.0), (42907, 520.0, 850.0)],
    )
    monkeypatch.setattr(
        flow,
        "recognize_template",
        lambda name, **_kwargs: result(name == "expedition_challenge"),
    )

    assert flow._select_best_cruise_fighter(CRUISE_FIGHTER_CONFIG)
    assert flow.ctrl.taps == [
        (*CRUISE_FIGHTER_CONFIG["change_fighter_position"], 0.8),
        (520.0, 850.0, 0.5),
        (*CRUISE_FIGHTER_CONFIG["sortie_position"], 1.2),
    ]


def test_existing_new_mode_template_specs_reference_files() -> None:
    prefixes = (
        "challenge_deep_space_cruise",
        "expedition_",
        "cruise_",
        "boss_mode_overlimit_entry",
        "overlimit_mode_",
    )
    missing = [
        name
        for name, spec in TEMPLATE_SPECS.items()
        if name.startswith(prefixes)
        and not (TEMPLATE_DIR / spec["file"]).is_file()
    ]
    assert missing == []


def test_deep_space_template_specs_are_declared() -> None:
    assert set(DEEP_SPACE_TEMPLATE_NAMES).issubset(TEMPLATE_SPECS)
    for name in DEEP_SPACE_TEMPLATE_NAMES:
        assert TEMPLATE_SPECS[name]["file"] == f"{name}.png"
        assert (TEMPLATE_DIR / TEMPLATE_SPECS[name]["file"]).is_file()


@pytest.mark.parametrize(
    "missing_name",
    (
        "deep_space_cruise_entry",
        "deep_space_cruise_page",
        "deep_space_cruise_sortie",
        "deep_space_cruise_info_close",
    ),
)
def test_missing_deep_space_asset_fails_before_any_click(
    missing_name: str,
    flow: DailyFlowRunner,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    required = (
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
    placeholder = cv2.imencode(".png", np.zeros((1, 1, 3), dtype=np.uint8))[1].tobytes()
    for name in required:
        if name != missing_name:
            (tmp_path / TEMPLATE_SPECS[name]["file"]).write_bytes(placeholder)
    monkeypatch.setattr(runner_module, "TEMPLATE_DIR", tmp_path)

    clicked: list[str] = []
    monkeypatch.setattr(
        flow,
        "click_template",
        lambda name, **_kwargs: clicked.append(name) or result(True),
    )

    with pytest.raises(RuntimeError, match=missing_name):
        flow.run_deep_space_cruise_flow()

    assert clicked == []
    assert flow.ctrl.taps == []


def test_template_preflight_rejects_invalid_image(
    flow: DailyFlowRunner,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    invalid_path = tmp_path / TEMPLATE_SPECS["challenge_deep_space_cruise"]["file"]
    invalid_path.write_bytes(b"not-an-image")
    monkeypatch.setattr(runner_module, "TEMPLATE_DIR", tmp_path)

    with pytest.raises(RuntimeError, match="无法解码"):
        flow._require_template_files(("challenge_deep_space_cruise",))


def test_template_matcher_reads_unicode_path(tmp_path: Path) -> None:
    screen = np.zeros((30, 40, 3), dtype=np.uint8)
    template = np.zeros((10, 10, 3), dtype=np.uint8)
    template[1:9, 2:8] = (20, 120, 240)
    template[4:6, :] = (230, 40, 90)
    screen[8:18, 12:22] = template
    screen_path = tmp_path / "普通星域巡航截图.png"
    template_path = tmp_path / "挑战按钮模板.png"
    assert cv2.imencode(".png", screen)[1].tofile(screen_path) is None
    assert cv2.imencode(".png", template)[1].tofile(template_path) is None

    matched = TemplateMatcher(grayscale=False).match(
        screen_path,
        template_path,
        threshold=0.99,
        grayscale=False,
    )

    assert matched.found
    assert matched.top_left == (12, 8)


def test_click_first_available_cruise_enemy_uses_best_match(
    flow: DailyFlowRunner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(flow, "wait_until_not_loading", lambda **_: Path("shot.png"))
    matches = {
        "expedition_available_enemy": result(True, x=92, y=702, score=0.92),
        "expedition_available_enemy_right": result(
            True,
            x=613,
            y=885,
            score=0.97,
        ),
    }
    monkeypatch.setattr(flow, "match", lambda name, _shot: matches[name])
    monkeypatch.setattr(
        flow,
        "recognize_template",
        lambda *_args, **_kwargs: result(True),
    )

    assert flow._click_first_available_cruise_enemy()
    assert flow.ctrl.taps == [(613, 885, 1.8)]


def test_battle_result_classification_prefers_defeat(
    flow: DailyFlowRunner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        flow,
        "match",
        lambda name, _shot: result(name in {"victory", "defeat"}),
    )

    assert (
        flow._classify_battle_result(
            Path("result.png"),
            victory_template="victory",
            defeat_template="defeat",
        )
        is BattleResult.DEFEAT
    )


def test_wait_for_battle_closes_revive_when_ads_disabled(
    flow: DailyFlowRunner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    shots = iter([Path("revive.png"), Path("result.png")])
    monkeypatch.setattr(flow, "screenshot", lambda _tag: next(shots))
    monkeypatch.setattr(runner_module.time, "sleep", lambda _seconds: None)

    def match(name: str, shot: Path) -> MatchResult:
        if shot.name == "revive.png":
            if name == "revive":
                return result(True, x=490, y=680)
            if name == "close":
                return result(True, x=603, y=590)
        if shot.name == "result.png" and name == "result":
            return result(True, x=362, y=1122)
        return result(False)

    monkeypatch.setattr(flow, "match", match)
    battle_result = flow._wait_for_mode_battle_result(
        context="测试战斗",
        result_template="result",
        revive_template="revive",
        revive_close_template="close",
        initial_wait=0,
        poll_interval=0.01,
        timeout=10,
        revive_by_ad=False,
    )

    assert battle_result is BattleResult.COMPLETE
    assert flow.ctrl.taps == [(603, 590, 3.0), (362, 1122, 2.4)]


@pytest.mark.parametrize(
    ("cost", "expected_first_tap"),
    (
        (40, (*BATTLE_ASSIST_CONFIG["diamond_revive_position"], 2.0)),
        (20, (603, 590, 3.0)),
        (60, (603, 590, 3.0)),
        (None, (603, 590, 3.0)),
    ),
)
def test_wait_for_battle_only_uses_exact_40_paid_revive_when_ad_is_unavailable(
    flow: DailyFlowRunner,
    monkeypatch: pytest.MonkeyPatch,
    cost: int | None,
    expected_first_tap: tuple[float, float, float],
) -> None:
    shots = iter([Path("revive.png"), Path("result.png")])
    config = dict(BATTLE_ASSIST_CONFIG)
    config.update(
        {
            "shield_enabled": False,
            "bomb_enabled": False,
            "move_enabled": False,
        }
    )
    monkeypatch.setattr(
        flow,
        "screenshot",
        lambda tag: (
            Path("revive_confirm.png")
            if tag == "battle_assist_paid_revive_confirm"
            else next(shots)
        ),
    )
    monkeypatch.setattr(flow, "_read_revive_diamond_cost", lambda _shot, _config: cost)

    def match(name: str, shot: Path) -> MatchResult:
        if shot.name in {"revive.png", "revive_confirm.png"} and name == "close":
            return result(True, x=603, y=590)
        if shot.name == "result.png" and name == "result":
            return result(True, x=362, y=1122)
        return result(False)

    monkeypatch.setattr(flow, "match", match)
    battle_result = flow._wait_for_mode_battle_result(
        context="40钻复活测试",
        result_template="result",
        revive_template="revive",
        revive_close_template="close",
        initial_wait=0,
        poll_interval=0.01,
        timeout=10,
        revive_by_ad=True,
        battle_assist_config=config,
    )

    assert battle_result is BattleResult.COMPLETE
    assert flow.ctrl.taps == [
        expected_first_tap,
        (362, 1122, 2.4),
    ]


def test_revive_modal_wins_over_visible_background_hud(
    flow: DailyFlowRunner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    shots = iter([Path("revive.png"), Path("post_ad.png"), Path("final.png")])
    monkeypatch.setattr(flow, "screenshot", lambda _tag: next(shots))
    monkeypatch.setattr(runner_module.time, "sleep", lambda _seconds: None)

    def match(name: str, shot: Path) -> MatchResult:
        if shot.name in {"revive.png", "post_ad.png"}:
            if name == "revive":
                return result(True, x=490, y=680)
            if name == "high_energy_bomb":
                return result(True)
            if name == "close":
                return result(True, x=603, y=590)
        if shot.name == "final.png" and name == "result":
            return result(True, x=362, y=1122)
        return result(False)

    monkeypatch.setattr(flow, "match", match)
    flow._wait_for_mode_battle_result(
        context="复活优先级测试",
        result_template="result",
        revive_template="revive",
        revive_close_template="close",
        initial_wait=0,
        poll_interval=0.01,
        timeout=10,
        revive_by_ad=True,
    )

    assert flow.ctrl.taps == [
        (490, 680, 2.0),
        (603, 590, 3.0),
        (362, 1122, 2.4),
    ]


def test_ad_revive_requires_close_button_from_same_frame(
    flow: DailyFlowRunner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(flow, "screenshot", lambda _tag: Path("revive.png"))
    monkeypatch.setattr(
        flow,
        "match",
        lambda name, _shot: result(name == "revive", x=490, y=680),
    )

    with pytest.raises(RuntimeError, match="未识别到关闭按钮"):
        flow._wait_for_mode_battle_result(
            context="广告复活双模板测试",
            result_template="result",
            revive_template="revive",
            revive_close_template="close",
            initial_wait=0,
            poll_interval=0.01,
            timeout=10,
            revive_by_ad=True,
        )

    assert flow.ctrl.taps == []


def test_initial_wait_honors_timeout(
    flow: DailyFlowRunner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tags: list[str] = []
    monkeypatch.setattr(
        flow,
        "_sleep_with_deadline",
        lambda _seconds, _deadline: False,
    )
    monkeypatch.setattr(
        flow,
        "screenshot",
        lambda tag: tags.append(tag) or Path("timeout.png"),
    )

    with pytest.raises(RuntimeError, match="10秒内未进入结算页"):
        flow._wait_for_mode_battle_result(
            context="硬超时测试",
            result_template="result",
            revive_template="revive",
            revive_close_template="close",
            initial_wait=1,
            poll_interval=1,
            timeout=10,
            revive_by_ad=False,
        )

    assert tags == ["硬超时测试_timeout"]


def test_cruise_equation_handler_consumes_consecutive_pages(
    flow: DailyFlowRunner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    shots = iter([Path("equation_2.png"), Path("battle.png")])
    monkeypatch.setattr(flow, "screenshot", lambda _tag: next(shots))
    monkeypatch.setattr(
        flow,
        "match",
        lambda name, shot: result(
            name == "expedition_equation_page" and shot.name.startswith("equation")
        ),
    )
    monkeypatch.setattr(flow, "_select_equation_card_index", lambda *_args: 1)

    selected = flow._choose_cruise_equations_if_needed(
        context="连续方程测试",
        first_shot=Path("equation_1.png"),
        max_picks=3,
    )

    assert selected == 2
    assert flow.ctrl.taps == [
        (360, 650, 0.8),
        (360, 977, 1.5),
        (360, 650, 0.8),
        (360, 977, 1.5),
    ]


def test_wait_for_battle_handles_equation_before_result(
    flow: DailyFlowRunner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    shots = iter([Path("equation.png"), Path("battle.png"), Path("result.png")])
    monkeypatch.setattr(flow, "screenshot", lambda _tag: next(shots))

    def match(name: str, shot: Path) -> MatchResult:
        if name == "expedition_equation_page":
            return result(shot.name == "equation.png")
        if name == "result":
            return result(shot.name == "result.png", x=362, y=1122)
        return result(False)

    monkeypatch.setattr(flow, "match", match)
    monkeypatch.setattr(flow, "_select_equation_card_index", lambda *_args: 1)
    battle_result = flow._wait_for_mode_battle_result(
        context="深空方程测试",
        result_template="result",
        revive_template="revive",
        revive_close_template="close",
        initial_wait=0,
        poll_interval=0.01,
        timeout=10,
        revive_by_ad=False,
        handle_cruise_equations=True,
    )

    assert battle_result is BattleResult.COMPLETE
    assert flow.ctrl.taps == [
        (360, 650, 0.8),
        (360, 977, 1.5),
        (362, 1122, 2.4),
    ]


@pytest.mark.parametrize(
    ("bgr", "expected_rank"),
    (
        ((0, 190, 240), 5),
        ((190, 40, 180), 4),
        ((220, 120, 20), 3),
        ((70, 180, 70), 2),
    ),
)
def test_equation_quality_color_classifier(
    bgr: tuple[int, int, int],
    expected_rank: int,
) -> None:
    crop = np.full((60, 60, 3), bgr, dtype=np.uint8)
    assert DailyFlowRunner._equation_quality_rank_from_hsv(crop) == expected_rank


def test_equation_selector_prefers_quality_or_priority(
    flow: DailyFlowRunner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        flow,
        "_read_equation_cards",
        lambda _shot: [
            ("维修回路·III", 3),
            ("随机金色方程·V", 5),
            ("随机紫色方程·IV", 4),
        ],
    )

    assert flow._select_equation_card_index(Path("equation.png"), "highest_quality") == 1
    assert flow._select_equation_card_index(Path("equation.png"), "priority") == 0


def test_equation_selector_uses_middle_when_unreadable(
    flow: DailyFlowRunner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        flow,
        "_read_equation_cards",
        lambda _shot: [("", 0), ("", 0), ("", 0)],
    )

    assert flow._select_equation_card_index(Path("equation.png"), "priority") == 1


def test_normal_cruise_battle_handles_result_and_equation(
    flow: DailyFlowRunner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clicked: list[str] = []
    wait_kwargs: dict[str, object] = {}
    recognized: list[str] = []
    fighter_selections: list[dict] = []
    monkeypatch.setattr(flow, "_click_first_available_cruise_enemy", lambda: True)
    monkeypatch.setattr(
        flow,
        "_select_best_cruise_fighter",
        lambda config: fighter_selections.append(config) or True,
    )
    monkeypatch.setattr(
        flow,
        "click_template",
        lambda name, **_kwargs: clicked.append(name) or result(True),
    )
    monkeypatch.setattr(flow, "_wait_for_cruise_battle_start", lambda **_kwargs: True)

    def wait_for_result(**kwargs: object) -> BattleResult:
        wait_kwargs.update(kwargs)
        return BattleResult.VICTORY

    monkeypatch.setattr(flow, "_wait_for_mode_battle_result", wait_for_result)
    monkeypatch.setattr(
        flow,
        "wait_until_not_loading",
        lambda **_kwargs: Path("equation.png"),
    )
    monkeypatch.setattr(
        flow,
        "_choose_cruise_equations_if_needed",
        lambda **_kwargs: 1,
    )
    monkeypatch.setattr(
        flow,
        "recognize_template",
        lambda name, **_kwargs: recognized.append(name) or result(True),
    )

    assert flow._run_normal_cruise_battle(3)
    assert fighter_selections == [CRUISE_FIGHTER_CONFIG]
    assert clicked == ["expedition_challenge"]
    assert wait_kwargs["battle_assist_config"] == BATTLE_ASSIST_CONFIG
    assert wait_kwargs["handle_cruise_equations"] is True
    assert wait_kwargs["cruise_equation_strategy"] == "highest_quality"
    assert wait_kwargs["timeout"] == runner_module.DEEP_SPACE_CRUISE_CONFIG[
        "normal_battle_timeout_seconds"
    ]
    assert recognized == ["expedition_page"]


def test_complete_normal_cruise_runs_until_endless_entry(
    flow: DailyFlowRunner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    entry_states = iter([False, False, True])
    battles: list[int] = []
    monkeypatch.setattr(
        flow,
        "recognize_template",
        lambda name, **_kwargs: result(
            next(entry_states) if name == "deep_space_cruise_entry" else True
        ),
    )
    monkeypatch.setattr(
        flow,
        "_run_normal_cruise_battle",
        lambda index: battles.append(index) or True,
    )

    assert flow._complete_normal_cruise()
    assert battles == [1, 2]


def test_deep_space_unlocked_navigation_and_sortie(
    flow: DailyFlowRunner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clicked: list[str] = []
    recognized: list[str] = []
    runs: list[int] = []
    monkeypatch.setattr(flow, "_require_template_files", lambda _names: None)
    monkeypatch.setattr(
        flow,
        "click_template",
        lambda name, **_kwargs: clicked.append(name) or result(True),
    )
    monkeypatch.setattr(
        flow,
        "recognize_template",
        lambda name, **_kwargs: recognized.append(name) or result(True),
    )
    monkeypatch.setattr(
        flow,
        "_start_expedition_endless_battle",
        lambda index: runs.append(index),
    )
    monkeypatch.setattr(flow, "_recover_to_home", lambda _context: True)

    flow.run_deep_space_cruise_flow()

    assert clicked == [
        "home_challenge_mode",
        "challenge_deep_space_cruise",
        "deep_space_cruise_entry",
        "deep_space_cruise_info_close",
    ]
    assert recognized == ["expedition_page", "deep_space_cruise_page"]
    assert runs == [1]


def test_deep_space_locked_entry_skips_sortie(
    flow: DailyFlowRunner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clicked: list[str] = []
    runs: list[int] = []
    normal_attempts: list[bool] = []
    monkeypatch.setattr(flow, "_require_template_files", lambda _names: None)

    def click(name: str, **_kwargs) -> MatchResult:
        clicked.append(name)
        return result(name != "deep_space_cruise_entry")

    monkeypatch.setattr(flow, "click_template", click)
    monkeypatch.setattr(
        flow,
        "recognize_template",
        lambda *_args, **_kwargs: result(True),
    )
    monkeypatch.setattr(
        flow,
        "_start_expedition_endless_battle",
        lambda index: runs.append(index),
    )
    monkeypatch.setattr(
        flow,
        "_complete_normal_cruise",
        lambda: normal_attempts.append(True) or False,
    )
    monkeypatch.setattr(flow, "_recover_to_home", lambda _context: True)

    flow.run_deep_space_cruise_flow()

    assert clicked == [
        "home_challenge_mode",
        "challenge_deep_space_cruise",
        "deep_space_cruise_entry",
    ]
    assert normal_attempts == [True]
    assert runs == []


def test_deep_space_invalid_equation_strategy_stops_before_click(
    flow: DailyFlowRunner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clicked: list[str] = []
    monkeypatch.setitem(
        runner_module.DEEP_SPACE_CRUISE_CONFIG,
        "deep_equation_pick_strategy",
        "random",
    )
    monkeypatch.setattr(
        flow,
        "click_template",
        lambda name, **_kwargs: clicked.append(name) or result(True),
    )

    with pytest.raises(ValueError, match="未知方程选择策略"):
        flow.run_deep_space_cruise_flow()

    assert clicked == []


def test_deep_space_recovers_home_after_navigation_failure(
    flow: DailyFlowRunner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recovered: list[str] = []
    monkeypatch.setattr(flow, "_require_template_files", lambda _names: None)
    monkeypatch.setattr(
        flow,
        "click_template",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("导航失败")),
    )
    monkeypatch.setattr(
        flow,
        "_recover_to_home",
        lambda context: recovered.append(context) or True,
    )

    with pytest.raises(RuntimeError, match="导航失败"):
        flow.run_deep_space_cruise_flow()

    assert recovered == ["深空巡航"]


def test_overlimit_count_parser_handles_overlapping_ocr_boxes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    image_path = tmp_path / "超限次数.png"
    image = np.zeros((55, 170, 3), dtype=np.uint8)
    assert cv2.imencode(".png", image)[1].tofile(image_path) is None

    class FakeOcr:
        def __call__(self, _image):
            return [
                [[[0, 0], [100, 0], [100, 20], [0, 20]], "完成挑战：1", 0.99],
                [[[90, 0], [140, 0], [140, 20], [90, 20]], "1/12", 0.99],
            ], None

    monkeypatch.setattr(DailyFlowRunner, "_get_ocr_engine", lambda: FakeOcr())

    assert (
        DailyFlowRunner._read_challenge_count_from_image(
            image_path,
            (0, 0, 170, 55),
        )
        == 1
    )


def test_overlimit_normal_failure_does_not_start_overlimit(
    flow: DailyFlowRunner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    challenges: list[str] = []
    monkeypatch.setattr(flow, "_get_overlimit_board_count", lambda *_args: 0)
    monkeypatch.setattr(flow, "click_template", lambda *_args, **_kwargs: result(True))
    monkeypatch.setattr(flow, "_recognize_overlimit_stage_page", lambda **_kwargs: True)
    monkeypatch.setattr(flow, "_rewind_overlimit_stages", lambda: True)
    monkeypatch.setattr(flow, "_get_overlimit_stage_status", lambda *_args: "incomplete")
    monkeypatch.setattr(flow, "_return_to_overlimit_board_page", lambda: True)
    monkeypatch.setattr(flow, "wait_until_not_loading", lambda **_kwargs: Path("stage.png"))
    monkeypatch.setattr(
        flow,
        "_run_overlimit_battle",
        lambda *, board, challenge: challenges.append(challenge),
    )

    flow.run_overlimit_mode_board("draco")

    assert challenges == ["normal"]


@pytest.mark.parametrize(
    ("header", "expected"),
    (
        ("猎杀原型体未完成挑战", "incomplete"),
        ("猎杀原型体普通通关", "normal_cleared"),
        ("猎杀原型体超限通关", "overlimit_cleared"),
    ),
)
def test_overlimit_stage_status_uses_header_ocr(
    flow: DailyFlowRunner,
    monkeypatch: pytest.MonkeyPatch,
    header: str,
    expected: str,
) -> None:
    monkeypatch.setattr(flow, "_read_overlimit_stage_header", lambda _shot: header)
    monkeypatch.setattr(flow, "match", lambda *_args, **_kwargs: result(False))

    assert flow._get_overlimit_stage_status(Path("stage.png")) == expected


def test_overlimit_board_scans_all_boss_stages(
    flow: DailyFlowRunner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(runner_module.OVERLIMIT_MODE_CONFIG, "target_runs_per_board", 4)
    monkeypatch.setitem(runner_module.OVERLIMIT_MODE_CONFIG, "stages_per_board", 2)
    statuses = iter(
        [
            "incomplete",
            "normal_cleared",
            "normal_cleared",
            "overlimit_cleared",
            "incomplete",
            "normal_cleared",
            "normal_cleared",
            "overlimit_cleared",
        ]
    )
    challenges: list[str] = []
    advances: list[bool] = []
    monkeypatch.setattr(flow, "click_template", lambda *_args, **_kwargs: result(True))
    monkeypatch.setattr(flow, "_recognize_overlimit_stage_page", lambda **_kwargs: True)
    monkeypatch.setattr(flow, "_rewind_overlimit_stages", lambda: True)
    monkeypatch.setattr(flow, "wait_until_not_loading", lambda **_kwargs: Path("stage.png"))
    monkeypatch.setattr(flow, "_get_overlimit_stage_status", lambda *_args: next(statuses))
    monkeypatch.setattr(
        flow,
        "_run_overlimit_battle",
        lambda *, board, challenge: challenges.append(challenge) or True,
    )
    monkeypatch.setattr(
        flow,
        "_advance_overlimit_stage",
        lambda: advances.append(True) or True,
    )
    monkeypatch.setattr(flow, "_return_to_overlimit_board_page", lambda: True)
    monkeypatch.setattr(flow, "_get_overlimit_board_count", lambda _board: 4)

    assert flow.run_overlimit_mode_board("draco", count_before=0) == 4
    assert challenges == ["normal", "overlimit", "normal", "overlimit"]
    assert advances == [True]


def test_overlimit_crystal_popup_requires_both_templates(
    flow: DailyFlowRunner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(flow, "click_template", lambda *_args, **_kwargs: result(True))
    monkeypatch.setattr(
        flow,
        "screenshot",
        lambda _tag: Path("popup.png"),
    )
    monkeypatch.setattr(
        flow,
        "match",
        lambda name, _shot: result(name == "overlimit_mode_crystal_invalid"),
    )
    monkeypatch.setattr(
        flow,
        "_sleep_with_deadline",
        lambda _seconds, _deadline: False,
    )

    assert not flow._wait_for_overlimit_battle_start(
        context="原晶状态测试",
        allow_crystal_popup=True,
        timeout=1.0,
    )
    assert flow.ctrl.taps == []


def test_overlimit_crystal_continue_waits_for_battle_hud(
    flow: DailyFlowRunner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    shots = iter([Path("crystal.png"), Path("battle.png")])
    monkeypatch.setattr(flow, "screenshot", lambda _tag: next(shots))
    monkeypatch.setattr(flow, "_sleep_with_deadline", lambda *_args: True)

    def match(name: str, shot: Path) -> MatchResult:
        if name == "overlimit_mode_challenge_ended":
            return result(False)
        if name in {
            "overlimit_mode_crystal_invalid",
            "overlimit_mode_continue_battle",
        }:
            return result(shot.name == "crystal.png", x=510, y=820)
        if name == "high_energy_bomb":
            return result(shot.name == "battle.png")
        return result(False)

    monkeypatch.setattr(flow, "match", match)

    assert flow._wait_for_overlimit_battle_start(
        context="原晶继续后HUD测试",
        allow_crystal_popup=True,
        timeout=1.0,
    )
    assert flow.ctrl.taps == [(510, 820, 3.0)]


def test_force_confirm_modal_wins_over_background_hud(
    flow: DailyFlowRunner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    shots = iter([Path("force_confirm.png"), Path("battle.png")])
    monkeypatch.setattr(flow, "screenshot", lambda _tag: next(shots))
    monkeypatch.setattr(runner_module.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(flow, "_sleep_with_deadline", lambda _seconds, _deadline: True)

    def match(name: str, shot: Path) -> MatchResult:
        if name == "overlimit_mode_challenge_ended":
            return result(False)
        if name == "expedition_force_challenge_confirm":
            return result(shot.name == "force_confirm.png", x=470, y=700)
        if name == "high_energy_bomb":
            return result(True)
        return result(False)

    monkeypatch.setattr(flow, "match", match)

    assert flow._wait_for_overlimit_battle_start(
        context="低战力弹窗优先级测试",
        allow_crystal_popup=False,
        allow_force_confirm=True,
        timeout=1.0,
    )
    assert flow.ctrl.taps == [(470, 700, 2.0)]


def test_overlimit_defeat_stops_before_stage_progression(
    flow: DailyFlowRunner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recognized: list[str] = []
    monkeypatch.setattr(flow, "click_template", lambda *_args, **_kwargs: result(True))
    monkeypatch.setattr(
        flow,
        "recognize_template",
        lambda name, **_kwargs: recognized.append(name) or result(True),
    )
    monkeypatch.setattr(
        flow,
        "_wait_for_overlimit_battle_start",
        lambda **_kwargs: True,
    )
    monkeypatch.setattr(flow, "_activate_overlimit_max_trial", lambda **_kwargs: True)
    monkeypatch.setattr(
        flow,
        "_wait_for_mode_battle_result",
        lambda **_kwargs: BattleResult.DEFEAT,
    )

    assert not flow._run_overlimit_battle(board="draco", challenge="overlimit")
    assert "overlimit_mode_stage_page" not in recognized


def test_overlimit_battle_activates_max_before_starting_challenge(
    flow: DailyFlowRunner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clicked: list[str] = []
    max_contexts: list[str] = []
    wait_kwargs: dict[str, object] = {}
    monkeypatch.setattr(
        flow,
        "click_template",
        lambda name, **_kwargs: clicked.append(name) or result(True),
    )
    monkeypatch.setattr(
        flow,
        "recognize_template",
        lambda *_args, **_kwargs: result(True),
    )
    monkeypatch.setattr(
        flow,
        "_activate_overlimit_max_trial",
        lambda *, context: max_contexts.append(context) or True,
    )
    monkeypatch.setattr(flow, "_wait_for_overlimit_battle_start", lambda **_kwargs: True)
    def wait_for_result(**kwargs: object) -> BattleResult:
        wait_kwargs.update(kwargs)
        return BattleResult.COMPLETE

    monkeypatch.setattr(flow, "_wait_for_mode_battle_result", wait_for_result)
    monkeypatch.setattr(flow, "_recognize_overlimit_stage_page", lambda **_kwargs: True)

    flow._run_overlimit_battle(board="draco", challenge="overlimit")

    assert clicked == [
        "overlimit_mode_overlimit_challenge",
        "overlimit_mode_start_challenge",
    ]
    assert max_contexts == ["超限模式天龙座超限挑战"]
    assert wait_kwargs["battle_assist_config"] == BATTLE_ASSIST_CONFIG


def test_overlimit_battle_stops_when_max_activation_is_unconfirmed(
    flow: DailyFlowRunner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clicked: list[str] = []
    result_waited: list[bool] = []
    monkeypatch.setattr(
        flow,
        "click_template",
        lambda name, **_kwargs: clicked.append(name) or result(True),
    )
    monkeypatch.setattr(flow, "recognize_template", lambda *_args, **_kwargs: result(True))
    monkeypatch.setattr(flow, "_activate_overlimit_max_trial", lambda **_kwargs: False)
    monkeypatch.setattr(
        flow,
        "_wait_for_mode_battle_result",
        lambda **_kwargs: result_waited.append(True) or BattleResult.COMPLETE,
    )

    assert not flow._run_overlimit_battle(board="draco", challenge="overlimit")
    assert clicked == ["overlimit_mode_overlimit_challenge"]
    assert result_waited == []


def test_normal_overlimit_challenge_never_activates_max(
    flow: DailyFlowRunner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(flow, "click_template", lambda *_args, **_kwargs: result(True))
    monkeypatch.setattr(flow, "_wait_for_overlimit_battle_start", lambda **_kwargs: True)
    monkeypatch.setattr(
        flow,
        "_activate_overlimit_max_trial",
        lambda **_kwargs: pytest.fail("普通挑战不应购买 MAX"),
    )
    monkeypatch.setattr(
        flow,
        "_wait_for_mode_battle_result",
        lambda **_kwargs: BattleResult.DEFEAT,
    )

    assert not flow._run_overlimit_battle(board="draco", challenge="normal")


def test_max_trial_state_requires_dialog_challenge_label_and_exact_200(
    flow: DailyFlowRunner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        flow,
        "_read_ocr_tokens",
        lambda *_args: [
            ("试用[MAX]装备", 0.99, 260.0, 972.0),
            ("（试用不进入排行榜单）", 0.99, 360.0, 990.0),
            ("200", 0.99, 596.0, 972.0),
        ],
    )
    monkeypatch.setattr(
        flow,
        "match",
        lambda name, _shot: result(
            name in {
                "overlimit_mode_overlimit_dialog",
                "overlimit_mode_start_challenge",
            },
            x=596,
            y=972,
        ),
    )

    state, point = flow._read_overlimit_max_trial_state(Path("max.png"))

    assert state == "available"
    assert point == (596, 972)


def test_max_trial_state_recognizes_already_activated_prompt(
    flow: DailyFlowRunner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def read_tokens(
        _shot: Path,
        roi: tuple[int, int, int, int],
    ) -> list[tuple[str, float, float, float]]:
        if roi == tuple(OVERLIMIT_MODE_CONFIG["max_equipment_trial_prompt_roi"]):
            return [
                ("将以所拥有的超限挑战装备进行战斗，", 0.99, 350.0, 550.0),
                ("是否开始挑战？", 0.99, 350.0, 570.0),
            ]
        return []

    monkeypatch.setattr(flow, "_read_ocr_tokens", read_tokens)
    monkeypatch.setattr(
        flow,
        "match",
        lambda name, _shot: result(
            name in {
                "overlimit_mode_overlimit_dialog",
                "overlimit_mode_start_challenge",
            }
        ),
    )

    assert flow._read_overlimit_max_trial_state(Path("active.png")) == (
        "activated",
        None,
    )


def test_max_trial_state_rejects_active_prompt_while_any_price_is_visible(
    flow: DailyFlowRunner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def read_tokens(
        _shot: Path,
        roi: tuple[int, int, int, int],
    ) -> list[tuple[str, float, float, float]]:
        if roi == tuple(OVERLIMIT_MODE_CONFIG["max_equipment_trial_prompt_roi"]):
            return [
                ("将以所拥有的超限挑战装备进行战斗，", 0.99, 350.0, 510.0),
                ("是否开始挑战？", 0.99, 350.0, 550.0),
            ]
        if roi == tuple(OVERLIMIT_MODE_CONFIG["max_equipment_trial_cost_roi"]):
            return [("200", 0.89, 596.0, 972.0)]
        return []

    monkeypatch.setattr(flow, "_read_ocr_tokens", read_tokens)
    monkeypatch.setattr(flow, "match", lambda *_args: result(True))

    assert flow._read_overlimit_max_trial_state(Path("ambiguous-active.png")) == (
        None,
        None,
    )


@pytest.mark.parametrize(
    "tokens",
    (
        [
            ("试用[MAX]装备", 0.99, 260.0, 972.0),
            ("（试用不进入排行榜单）", 0.99, 360.0, 990.0),
            ("2000", 0.99, 596.0, 972.0),
        ],
        [
            ("试用[MAX]装备", 0.99, 260.0, 972.0),
            ("（试用不进入排行榜单）", 0.99, 360.0, 990.0),
            ("200", 0.70, 596.0, 972.0),
        ],
        [("试用[MAX]装备", 0.99, 260.0, 972.0), ("200", 0.99, 596.0, 972.0)],
        [
            ("试用[MAX]装备", 0.99, 260.0, 972.0),
            ("（试用不进入排行榜单）", 0.99, 360.0, 990.0),
            ("200", 0.99, 596.0, 972.0),
            ("40", 0.99, 620.0, 972.0),
        ],
        [("200", 0.99, 596.0, 972.0)],
    ),
)
def test_max_trial_state_rejects_ambiguous_or_untrusted_price(
    flow: DailyFlowRunner,
    monkeypatch: pytest.MonkeyPatch,
    tokens: list[tuple[str, float, float, float]],
) -> None:
    monkeypatch.setattr(flow, "_read_ocr_tokens", lambda *_args: tokens)
    monkeypatch.setattr(
        flow,
        "match",
        lambda name, _shot: result(
            name in {
                "overlimit_mode_overlimit_dialog",
                "overlimit_mode_start_challenge",
            },
            x=596,
            y=972,
        ),
    )

    assert flow._read_overlimit_max_trial_state(Path("max.png")) == (None, None)


def test_max_trial_activation_buys_once_after_two_matching_frames(
    flow: DailyFlowRunner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    states = iter(
        [
            ("available", (596.0, 972.0)),
            ("available", (598.0, 971.0)),
            ("activated", None),
            ("activated", None),
        ]
    )
    monkeypatch.setattr(flow, "wait_until_not_loading", lambda **_kwargs: Path("max1.png"))
    monkeypatch.setattr(flow, "screenshot", lambda _tag: Path("max_next.png"))
    monkeypatch.setattr(
        flow,
        "_read_overlimit_max_trial_state",
        lambda _shot: next(states),
    )
    monkeypatch.setattr(flow, "_sleep_with_deadline", lambda *_args: True)

    assert flow._activate_overlimit_max_trial(context="MAX测试")
    assert flow.ctrl.taps == [(598.0, 971.0, 1.5)]


def test_max_trial_activation_does_not_rebuy_when_already_active(
    flow: DailyFlowRunner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    states = iter([("activated", None), ("activated", None)])
    monkeypatch.setattr(flow, "wait_until_not_loading", lambda **_kwargs: Path("active1.png"))
    monkeypatch.setattr(flow, "screenshot", lambda _tag: Path("active2.png"))
    monkeypatch.setattr(
        flow,
        "_read_overlimit_max_trial_state",
        lambda _shot: next(states),
    )

    assert flow._activate_overlimit_max_trial(context="MAX已启用测试")
    assert flow.ctrl.taps == []


def test_max_trial_activation_refuses_two_frame_price_mismatch(
    flow: DailyFlowRunner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    states = iter([("available", (596.0, 972.0)), (None, None)])
    monkeypatch.setattr(flow, "wait_until_not_loading", lambda **_kwargs: Path("max1.png"))
    monkeypatch.setattr(flow, "screenshot", lambda _tag: Path("max2.png"))
    monkeypatch.setattr(
        flow,
        "_read_overlimit_max_trial_state",
        lambda _shot: next(states),
    )

    assert not flow._activate_overlimit_max_trial(context="MAX价格变化测试")
    assert flow.ctrl.taps == []


def test_max_trial_activation_never_retries_after_paid_state_is_unknown(
    flow: DailyFlowRunner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    states = iter(
        [
            ("available", (596.0, 972.0)),
            ("available", (598.0, 971.0)),
            (None, None),
        ]
    )
    sleeps = iter([True, False])
    monkeypatch.setattr(flow, "wait_until_not_loading", lambda **_kwargs: Path("max1.png"))
    monkeypatch.setattr(flow, "screenshot", lambda _tag: Path("max_next.png"))
    monkeypatch.setattr(
        flow,
        "_read_overlimit_max_trial_state",
        lambda _shot: next(states),
    )
    monkeypatch.setattr(
        flow,
        "_sleep_with_deadline",
        lambda *_args: next(sleeps),
    )

    with pytest.raises(RuntimeError, match="拒绝再次扣费"):
        flow._activate_overlimit_max_trial(context="MAX购买后状态测试")

    assert flow.ctrl.taps == [(598.0, 971.0, 1.5)]
    assert flow.overlimit_max_trial_purchase_attempts == 1


def test_max_trial_activation_honors_flow_purchase_attempt_limit(
    flow: DailyFlowRunner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    states = iter(
        [
            ("available", (596.0, 972.0)),
            ("available", (598.0, 971.0)),
        ]
    )
    flow.overlimit_max_trial_purchase_attempts = int(
        OVERLIMIT_MODE_CONFIG["max_equipment_trial_purchase_attempt_limit"]
    )
    monkeypatch.setattr(flow, "wait_until_not_loading", lambda **_kwargs: Path("max1.png"))
    monkeypatch.setattr(flow, "screenshot", lambda _tag: Path("max2.png"))
    monkeypatch.setattr(
        flow,
        "_read_overlimit_max_trial_state",
        lambda _shot: next(states),
    )
    monkeypatch.setattr(flow, "_sleep_with_deadline", lambda *_args: True)

    assert not flow._activate_overlimit_max_trial(context="MAX上限测试")
    assert flow.ctrl.taps == []


def test_overlimit_flow_skips_board_at_target(
    flow: DailyFlowRunner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    visited: list[str] = []
    checked: list[str] = []
    monkeypatch.setattr(flow, "_require_template_files", lambda _names: None)
    monkeypatch.setattr(flow, "click_template", lambda *_args, **_kwargs: result(True))
    monkeypatch.setattr(
        flow,
        "recognize_template",
        lambda *_args, **_kwargs: result(True),
    )
    monkeypatch.setattr(
        flow,
        "_get_overlimit_board_count",
        lambda board: checked.append(board) or 9,
    )
    monkeypatch.setattr(
        flow,
        "run_overlimit_mode_board",
        lambda board, **_kwargs: visited.append(board),
    )
    monkeypatch.setattr(flow, "_recover_to_home", lambda _context: True)

    flow.run_overlimit_mode_flow()

    assert checked == ["draco", "cygnus", "pegasus", "andromeda"]
    assert visited == []


def test_overlimit_flow_processes_all_four_boards_below_target_in_order(
    flow: DailyFlowRunner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    counts = {"draco": 9, "cygnus": 8, "pegasus": 9, "andromeda": 0}
    checked: list[str] = []
    visited: list[tuple[str, int]] = []
    monkeypatch.setattr(flow, "_require_template_files", lambda _names: None)
    monkeypatch.setattr(flow, "click_template", lambda *_args, **_kwargs: result(True))
    monkeypatch.setattr(flow, "recognize_template", lambda *_args, **_kwargs: result(True))
    monkeypatch.setattr(
        flow,
        "_get_overlimit_board_count",
        lambda board: checked.append(board) or counts[board],
    )
    monkeypatch.setattr(
        flow,
        "run_overlimit_mode_board",
        lambda board, *, count_before: visited.append((board, count_before)),
    )
    monkeypatch.setattr(flow, "_recover_to_home", lambda _context: True)

    flow.run_overlimit_mode_flow()

    assert checked == ["draco", "cygnus", "pegasus", "andromeda"]
    assert visited == [("cygnus", 8), ("andromeda", 0)]


def test_overlimit_flow_processes_every_board_when_all_are_below_target(
    flow: DailyFlowRunner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    visited: list[tuple[str, int]] = []
    monkeypatch.setattr(flow, "_require_template_files", lambda _names: None)
    monkeypatch.setattr(flow, "click_template", lambda *_args, **_kwargs: result(True))
    monkeypatch.setattr(flow, "recognize_template", lambda *_args, **_kwargs: result(True))
    monkeypatch.setattr(flow, "_get_overlimit_board_count", lambda _board: 8)
    monkeypatch.setattr(
        flow,
        "run_overlimit_mode_board",
        lambda board, *, count_before: visited.append((board, count_before)),
    )
    monkeypatch.setattr(flow, "_recover_to_home", lambda _context: True)

    flow.run_overlimit_mode_flow()

    assert visited == [
        ("draco", 8),
        ("cygnus", 8),
        ("pegasus", 8),
        ("andromeda", 8),
    ]


@pytest.mark.parametrize("board", ("draco", "cygnus", "pegasus", "andromeda"))
def test_overlimit_board_stops_at_default_nine_without_opening_stage(
    flow: DailyFlowRunner,
    monkeypatch: pytest.MonkeyPatch,
    board: str,
) -> None:
    opened: list[str] = []
    monkeypatch.setattr(
        flow,
        "click_template",
        lambda name, **_kwargs: opened.append(name) or result(True),
    )

    assert flow.run_overlimit_mode_board(board, count_before=9) == 9
    assert opened == []


def test_overlimit_board_stops_immediately_after_reaching_nine(
    flow: DailyFlowRunner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    statuses = iter(["incomplete", "normal_cleared"])
    challenges: list[str] = []
    advances: list[bool] = []
    monkeypatch.setattr(flow, "click_template", lambda *_args, **_kwargs: result(True))
    monkeypatch.setattr(flow, "_recognize_overlimit_stage_page", lambda **_kwargs: True)
    monkeypatch.setattr(flow, "_rewind_overlimit_stages", lambda: True)
    monkeypatch.setattr(flow, "wait_until_not_loading", lambda **_kwargs: Path("stage.png"))
    monkeypatch.setattr(flow, "_get_overlimit_stage_status", lambda *_args: next(statuses))
    monkeypatch.setattr(
        flow,
        "_run_overlimit_battle",
        lambda *, board, challenge: challenges.append(challenge) or True,
    )
    monkeypatch.setattr(
        flow,
        "_advance_overlimit_stage",
        lambda: advances.append(True) or True,
    )
    monkeypatch.setattr(flow, "_return_to_overlimit_board_page", lambda: True)
    monkeypatch.setattr(flow, "_get_overlimit_board_count", lambda _board: 9)

    assert flow.run_overlimit_mode_board("draco", count_before=8) == 9
    assert challenges == ["normal"]
    assert advances == []


def test_deep_space_flow_fails_when_home_recovery_is_unconfirmed(
    flow: DailyFlowRunner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(flow, "_require_template_files", lambda _names: None)
    monkeypatch.setattr(flow, "click_template", lambda *_args, **_kwargs: result(True))
    monkeypatch.setattr(flow, "recognize_template", lambda *_args, **_kwargs: result(True))
    monkeypatch.setattr(flow, "_start_expedition_endless_battle", lambda _index: False)
    monkeypatch.setattr(flow, "_recover_to_home", lambda _context: False)

    with pytest.raises(RuntimeError, match="流程结束但未能确认回到首页"):
        flow.run_deep_space_cruise_flow()


def test_mode_recovery_does_not_mask_primary_error(
    flow: DailyFlowRunner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(flow, "_recover_to_home", lambda _context: False)

    with pytest.raises(ValueError, match="主流程失败"):
        try:
            raise ValueError("主流程失败")
        except ValueError as exc:
            flow._finish_mode_flow("测试模式", exc)
            raise


def test_deep_space_sortie_wires_result_classification(
    flow: DailyFlowRunner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    wait_kwargs: dict[str, object] = {}
    monkeypatch.setattr(flow, "click_template", lambda *_args, **_kwargs: result(True))
    monkeypatch.setattr(flow, "recognize_template", lambda *_args, **_kwargs: result(True))

    def wait_for_result(**kwargs: object) -> BattleResult:
        wait_kwargs.update(kwargs)
        return BattleResult.VICTORY

    monkeypatch.setattr(flow, "_wait_for_mode_battle_result", wait_for_result)

    assert flow._start_expedition_endless_battle(1)
    assert wait_kwargs["victory_template"] == "cruise_result_victory"
    assert wait_kwargs["defeat_template"] == "cruise_result_defeat"
    assert wait_kwargs["cruise_equation_strategy"] == "priority"
    assert wait_kwargs["battle_assist_config"] == BATTLE_ASSIST_CONFIG
    assert wait_kwargs["timeout"] == runner_module.DEEP_SPACE_CRUISE_CONFIG[
        "battle_timeout_seconds"
    ]


def test_deep_space_defeat_stops_follow_up_sortie(
    flow: DailyFlowRunner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recognized: list[str] = []
    monkeypatch.setattr(flow, "click_template", lambda *_args, **_kwargs: result(True))
    monkeypatch.setattr(
        flow,
        "_wait_for_mode_battle_result",
        lambda **_kwargs: BattleResult.DEFEAT,
    )
    monkeypatch.setattr(
        flow,
        "recognize_template",
        lambda name, **_kwargs: recognized.append(name) or result(True),
    )

    assert not flow._start_expedition_endless_battle(1)
    assert recognized == []


def test_overlimit_preflight_checks_force_confirm_before_click(
    flow: DailyFlowRunner,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    required = (
        "loading",
        "home_challenge_mode",
        "challenge_boss_mode",
        "boss_mode_overlimit_entry",
        "overlimit_mode_page",
        "overlimit_mode_stage_page",
        "overlimit_mode_stage_prev",
        "overlimit_mode_stage_next",
        "overlimit_mode_normal_cleared",
        "overlimit_mode_challenge_ended",
        "overlimit_mode_result_continue",
        "cruise_result_defeat",
        "overlimit_mode_ad_revive",
        "overlimit_mode_revive_close",
        "high_energy_bomb",
        "nav_home",
        "back",
        "overlimit_mode_board_draco",
        "overlimit_mode_board_cygnus",
        "overlimit_mode_board_pegasus",
        "overlimit_mode_board_andromeda",
        "overlimit_mode_normal_challenge",
        "overlimit_mode_overlimit_challenge",
        "overlimit_mode_overlimit_dialog",
        "overlimit_mode_start_challenge",
        "overlimit_mode_crystal_invalid",
        "overlimit_mode_continue_battle",
    )
    placeholder = cv2.imencode(".png", np.zeros((1, 1, 3), dtype=np.uint8))[1].tobytes()
    for name in required:
        (tmp_path / TEMPLATE_SPECS[name]["file"]).write_bytes(placeholder)
    monkeypatch.setattr(runner_module, "TEMPLATE_DIR", tmp_path)

    clicked: list[str] = []
    monkeypatch.setattr(
        flow,
        "click_template",
        lambda name, **_kwargs: clicked.append(name) or result(True),
    )

    with pytest.raises(RuntimeError, match="expedition_force_challenge_confirm"):
        flow.run_overlimit_mode_flow()

    assert clicked == []


def test_overlimit_target_zero_skips_navigation(
    flow: DailyFlowRunner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(runner_module.OVERLIMIT_MODE_CONFIG, "target_runs_per_board", 0)
    clicked: list[str] = []
    monkeypatch.setattr(
        flow,
        "click_template",
        lambda name, **_kwargs: clicked.append(name) or result(True),
    )

    flow.run_overlimit_mode_flow()

    assert clicked == []


def test_overlimit_rejects_non_200_max_config_before_navigation(
    flow: DailyFlowRunner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(
        runner_module.OVERLIMIT_MODE_CONFIG,
        "max_equipment_trial_expected_cost",
        199,
    )
    clicked: list[str] = []
    monkeypatch.setattr(
        flow,
        "click_template",
        lambda name, **_kwargs: clicked.append(name) or result(True),
    )

    with pytest.raises(ValueError, match="精确价格 200"):
        flow.run_overlimit_mode_flow()

    assert clicked == []


def test_overlimit_rejects_purchase_attempt_limit_above_four_board_bound(
    flow: DailyFlowRunner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(
        runner_module.OVERLIMIT_MODE_CONFIG,
        "max_equipment_trial_purchase_attempt_limit",
        17,
    )
    clicked: list[str] = []
    monkeypatch.setattr(
        flow,
        "click_template",
        lambda name, **_kwargs: clicked.append(name) or result(True),
    )

    with pytest.raises(ValueError, match=r"1\.\.16"):
        flow.run_overlimit_mode_flow()

    assert clicked == []


def test_overlimit_board_recovery_failure_stops_flow(
    flow: DailyFlowRunner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(flow, "_get_overlimit_board_count", lambda _board: 0)
    monkeypatch.setattr(flow, "click_template", lambda *_args, **_kwargs: result(True))
    monkeypatch.setattr(flow, "recognize_template", lambda *_args, **_kwargs: result(True))
    monkeypatch.setattr(flow, "_run_overlimit_battle", lambda **_kwargs: True)
    monkeypatch.setattr(flow, "_recognize_overlimit_stage_page", lambda **_kwargs: True)
    monkeypatch.setattr(flow, "_rewind_overlimit_stages", lambda: True)
    monkeypatch.setattr(flow, "wait_until_not_loading", lambda **_kwargs: Path("stage.png"))
    monkeypatch.setattr(flow, "_get_overlimit_stage_status", lambda *_args: "overlimit_cleared")
    monkeypatch.setattr(flow, "_advance_overlimit_stage", lambda: True)
    monkeypatch.setattr(flow, "_return_to_overlimit_board_page", lambda: False)

    with pytest.raises(RuntimeError, match="未能确认回到空间站选择页"):
        flow.run_overlimit_mode_board("draco")
