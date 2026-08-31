from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import pytest

from vision import TemplateMatcher
from windows_controller import WindowsController


def _controller() -> WindowsController:
    controller = object.__new__(WindowsController)
    controller.client_width = 720
    controller.client_height = 1280
    controller.force_client_size = False
    controller.click_method = "message"
    controller._ensure_client_size_before_interaction = lambda: None
    return controller


@pytest.mark.parametrize(
    "point",
    [(-1, 10), (720, 10), (10, -1), (10, 1280), (float("nan"), 10), (10, float("inf"))],
)
def test_controller_rejects_invalid_tap_coordinates(point: tuple[float, float]) -> None:
    controller = _controller()

    with pytest.raises(ValueError, match="坐标"):
        controller.tap(*point, delay=0)


@pytest.mark.parametrize(
    "points",
    [((-1, 10), (20, 20)), ((10, 10), (720, 20)), ((10, 1280), (20, 20))],
)
def test_controller_rejects_invalid_swipe_coordinates(
    points: tuple[tuple[float, float], tuple[float, float]],
) -> None:
    controller = _controller()

    with pytest.raises(ValueError, match="坐标"):
        controller.swipe(*points[0], *points[1], delay=0)


def test_make_lparam_does_not_wrap_negative_coordinates() -> None:
    with pytest.raises(ValueError, match="坐标"):
        WindowsController._make_lparam(-1, 10)

    assert WindowsController._make_lparam(12, 34) == (34 << 16) | 12


def test_template_matcher_rejects_out_of_bounds_roi(tmp_path: Path) -> None:
    image = np.zeros((20, 20, 3), dtype=np.uint8)
    image_path = tmp_path / "截图.png"
    template_path = tmp_path / "模板.png"
    cv2.imencode(".png", image)[1].tofile(image_path)
    cv2.imencode(".png", image[:5, :5])[1].tofile(template_path)

    with pytest.raises(ValueError, match="ROI"):
        TemplateMatcher(grayscale=False).match(
            image_path,
            template_path,
            threshold=0.9,
            roi=(-1, 0, 10, 10),
            grayscale=False,
        )

    with pytest.raises(ValueError, match="ROI"):
        TemplateMatcher(grayscale=False).match(
            image_path,
            template_path,
            threshold=0.9,
            roi=(0, 0, 21, 10),
            grayscale=False,
        )
