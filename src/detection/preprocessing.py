from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

import cv2
import numpy as np


@dataclass
class LetterBoxResult:
    image: np.ndarray
    ratio: float
    padding: Tuple[int, int]


def letterbox(
    image: np.ndarray,
    new_shape: Tuple[int, int] = (640, 640),
    color: Tuple[int, int, int] = (114, 114, 114),
    auto: bool = False,
    scale_fill: bool = False,
) -> LetterBoxResult:
    """
    Resize image to model input size with unchanged aspect ratio using padding.
    """

    shape = image.shape[:2]  # current shape [height, width]
    ratio = min(new_shape[0] / shape[0], new_shape[1] / shape[1])

    if not scale_fill:
        new_unpad = (int(round(shape[1] * ratio)), int(round(shape[0] * ratio)))
        dw = new_shape[1] - new_unpad[0]
        dh = new_shape[0] - new_unpad[1]
        if auto:
            dw %= 32
            dh %= 32
        dw /= 2
        dh /= 2
        resized = cv2.resize(image, new_unpad, interpolation=cv2.INTER_LINEAR)
        top, bottom = int(round(dh - 0.1)), int(round(dh + 0.1))
        left, right = int(round(dw - 0.1)), int(round(dw + 0.1))
        padded = cv2.copyMakeBorder(
            resized, top, bottom, left, right, cv2.BORDER_CONSTANT, value=color
        )
    else:
        padded = cv2.resize(image, new_shape, interpolation=cv2.INTER_LINEAR)
        ratio = new_shape[1] / shape[1]
        left = right = top = bottom = 0

    return LetterBoxResult(
        image=padded,
        ratio=ratio,
        padding=(left, top),
    )

