from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import pytest

import runner as runner_module
from config import TEMPLATE_DIR, TEMPLATE_SPECS
from runner import BattleResult, DailyFlowRunner, parse_sections
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

    def tap(self, x: float, y: float, delay: float = 0.8) -> None:
        self.taps.append((x, y, delay))

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
        and name not in DEEP_SPACE_TEMPLATE_NAMES
        and not (TEMPLATE_DIR / spec["file"]).is_file()
    ]
    assert missing == []


def test_deep_space_template_specs_are_declared() -> None:
    assert set(DEEP_SPACE_TEMPLATE_NAMES).issubset(TEMPLATE_SPECS)
    for name in DEEP_SPACE_TEMPLATE_NAMES:
        assert TEMPLATE_SPECS[name]["file"] == f"{name}.png"


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
    monkeypatch.setattr(flow, "_recover_to_home", lambda _context: True)

    flow.run_deep_space_cruise_flow()

    assert clicked == [
        "home_challenge_mode",
        "challenge_deep_space_cruise",
        "deep_space_cruise_entry",
    ]
    assert runs == []


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
    monkeypatch.setattr(
        flow,
        "recognize_template",
        lambda name, **_kwargs: result(name != "overlimit_mode_normal_cleared"),
    )
    monkeypatch.setattr(
        flow,
        "_run_overlimit_battle",
        lambda *, board, challenge: challenges.append(challenge),
    )

    flow.run_overlimit_mode_board("draco")

    assert challenges == ["normal"]


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
    monkeypatch.setattr(
        flow,
        "_wait_for_mode_battle_result",
        lambda **_kwargs: BattleResult.DEFEAT,
    )

    assert not flow._run_overlimit_battle(board="draco", challenge="overlimit")
    assert "overlimit_mode_stage_page" not in recognized


def test_overlimit_battle_never_taps_paid_trial(
    flow: DailyFlowRunner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clicked: list[str] = []
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
        "wait_until_not_loading",
        lambda **_kwargs: Path("popup.png"),
    )
    monkeypatch.setattr(
        flow,
        "match",
        lambda name, _shot: result(
            name in {
                "overlimit_mode_crystal_invalid",
                "overlimit_mode_continue_battle",
            },
            x=510,
            y=820,
        ),
    )
    monkeypatch.setattr(
        flow,
        "_wait_for_mode_battle_result",
        lambda **_kwargs: BattleResult.COMPLETE,
    )

    flow._run_overlimit_battle(board="draco", challenge="overlimit")

    assert clicked == [
        "overlimit_mode_overlimit_challenge",
        "overlimit_mode_start_challenge",
    ]
    assert flow.ctrl.taps == [(510, 820, 3.0)]
    assert all("trial" not in name and "max" not in name for name in clicked)


def test_overlimit_flow_skips_board_at_target(
    flow: DailyFlowRunner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    visited: list[str] = []
    monkeypatch.setattr(flow, "_require_template_files", lambda _names: None)
    monkeypatch.setattr(flow, "click_template", lambda *_args, **_kwargs: result(True))
    monkeypatch.setattr(
        flow,
        "recognize_template",
        lambda *_args, **_kwargs: result(True),
    )
    monkeypatch.setattr(flow, "_get_overlimit_board_count", lambda _board: 2)
    monkeypatch.setattr(
        flow,
        "run_overlimit_mode_board",
        lambda board, **_kwargs: visited.append(board),
    )
    monkeypatch.setattr(flow, "_recover_to_home", lambda _context: True)

    flow.run_overlimit_mode_flow()

    assert visited == []


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


def test_overlimit_board_recovery_failure_stops_flow(
    flow: DailyFlowRunner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(flow, "_get_overlimit_board_count", lambda _board: 0)
    monkeypatch.setattr(flow, "click_template", lambda *_args, **_kwargs: result(True))
    monkeypatch.setattr(flow, "recognize_template", lambda *_args, **_kwargs: result(True))
    monkeypatch.setattr(flow, "_run_overlimit_battle", lambda **_kwargs: True)
    monkeypatch.setattr(flow, "_return_to_overlimit_board_page", lambda: False)

    with pytest.raises(RuntimeError, match="未能确认回到空间站选择页"):
        flow.run_overlimit_mode_board("draco")
