from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

import cv2
import numpy as np

ROI = Tuple[int, int, int, int]


@dataclass
class MatchResult:
    found: bool
    score: float
    x: float
    y: float
    top_left: tuple[int, int]
    bottom_right: tuple[int, int]
    template_size: tuple[int, int]


class TemplateMatcher:
    def __init__(self, grayscale: bool = True):
        """OpenCV模板匹配器。

        grayscale 是默认模式。实际匹配时可以通过 match(..., grayscale=False)
        针对某些模板单独启用彩色匹配。比如蓝色/灰色按钮状态差异主要
        来自颜色时，必须保留彩色信息，否则灰度化后会非常相似。
        """
        self.grayscale = grayscale
        self._template_cache: dict[tuple[Path, bool], np.ndarray] = {}

    @staticmethod
    def _read_image(path: str | Path, grayscale: bool) -> np.ndarray:
        path = Path(path)
        try:
            data = np.fromfile(path, dtype=np.uint8)
        except OSError as exc:
            raise FileNotFoundError(f"图片读取失败: {path}") from exc
        img = cv2.imdecode(data, cv2.IMREAD_COLOR)
        if img is None:
            raise FileNotFoundError(f"图片读取失败: {path}")
        if grayscale:
            img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        return img

    def _read_template(self, path: str | Path, grayscale: bool) -> np.ndarray:
        path = Path(path)
        key = (path, grayscale)
        cached = self._template_cache.get(key)
        if cached is not None:
            return cached
        templ = self._read_image(path, grayscale)
        self._template_cache[key] = templ
        return templ

    @staticmethod
    def _crop_by_roi(img: np.ndarray, roi: Optional[ROI]) -> tuple[np.ndarray, int, int]:
        if roi is None:
            return img, 0, 0
        x1, y1, x2, y2 = roi
        h, w = img.shape[:2]
        if not (0 <= x1 < x2 <= w and 0 <= y1 < y2 <= h):
            raise ValueError(
                f"ROI 越界或为空: {roi}，图像尺寸为 {w}x{h}"
            )
        return img[y1:y2, x1:x2], x1, y1

    def match(
        self,
        screenshot_path: str | Path,
        template_path: str | Path,
        threshold: float = 0.86,
        roi: Optional[ROI] = None,
        grayscale: Optional[bool] = None,
    ) -> MatchResult:
        """执行一次模板匹配。

        grayscale:
        - None：使用对象默认模式；
        - True：灰度匹配；
        - False：彩色匹配。
        """
        use_grayscale = self.grayscale if grayscale is None else grayscale
        screen = self._read_image(screenshot_path, use_grayscale)
        templ = self._read_template(template_path, use_grayscale)
        region, ox, oy = self._crop_by_roi(screen, roi)

        th, tw = templ.shape[:2]
        rh, rw = region.shape[:2]
        if th > rh or tw > rw:
            return MatchResult(False, -1.0, 0.0, 0.0, (0, 0), (0, 0), (tw, th))

        result = cv2.matchTemplate(region, templ, cv2.TM_CCOEFF_NORMED)
        # 最高匹配分数max_val，和最高匹配分数对应的位置max_loc，也就是模板左上角在 ROI 中的位置（相对坐标）
        _, max_val, _, max_loc = cv2.minMaxLoc(result)
        x1 = ox + max_loc[0]
        y1 = oy + max_loc[1]
        x2 = x1 + tw
        y2 = y1 + th
        cx = x1 + tw / 2
        cy = y1 + th / 2
        return MatchResult(
            found=max_val >= threshold,
            score=float(max_val),
            x=cx,
            y=cy,
            top_left=(x1, y1),
            bottom_right=(x2, y2),
            template_size=(tw, th),
        )
