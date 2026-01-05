import numpy as np

from src.detection.preprocessing import letterbox


def test_letterbox_preserves_aspect_ratio():
    img = np.zeros((480, 640, 3), dtype=np.uint8)
    result = letterbox(img, new_shape=(640, 640))

    assert result.image.shape[:2] == (640, 640)
    # Expect padding applied because original aspect ratio differs
    assert result.padding[0] >= 0 and result.padding[1] >= 0
    assert 0 < result.ratio <= 1

