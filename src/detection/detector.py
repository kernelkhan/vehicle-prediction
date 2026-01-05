from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

import cv2
import numpy as np
import onnxruntime as ort

from src.utils.logger import get_logger

from .preprocessing import letterbox


@dataclass
class Detection:
    bbox: np.ndarray  # [x1, y1, x2, y2]
    confidence: float
    class_id: int
    class_name: str


class YoloV8Detector:
    """
    YOLOv8 ONNX detector optimized for Raspberry Pi inference via ONNX Runtime.
    """

    def __init__(
        self,
        model_path: Path,
        class_names: List[str],
        conf_threshold: float = 0.4,
        iou_threshold: float = 0.5,
        providers: Optional[list[str]] = None,
        log_dir: Optional[Path] = None,
    ) -> None:
        self.model_path = model_path
        self.class_names = class_names
        self.conf_threshold = conf_threshold
        self.iou_threshold = iou_threshold
        self.providers = providers or self._default_providers()

        self.logger = get_logger("YoloV8Detector", log_dir)
        self.session = self._create_session()
        self.input_name = self.session.get_inputs()[0].name
        self.input_shape = self.session.get_inputs()[0].shape
        self.output_name = self.session.get_outputs()[0].name

    def _default_providers(self) -> list[str]:
        providers = ["CPUExecutionProvider"]
        try:
            import pkgutil

            if pkgutil.find_loader("onnxruntime_extensions"):
                providers.insert(0, "ARMNNExecutionProvider")
        except Exception:  # pragma: no cover - optional acceleration
            pass
        return providers

    def _create_session(self) -> ort.InferenceSession:
        if not self.model_path.exists():
            raise FileNotFoundError(f"Model not found at {self.model_path}")

        session_options = ort.SessionOptions()
        session_options.graph_optimization_level = (
            ort.GraphOptimizationLevel.ORT_ENABLE_EXTENDED
        )

        self.logger.info(
            "Loading YOLOv8 ONNX model from %s with providers %s",
            self.model_path,
            self.providers,
        )
        return ort.InferenceSession(
            str(self.model_path), providers=self.providers, sess_options=session_options
        )

    def infer(self, frame: np.ndarray) -> List[Detection]:
        start = time.time()
        letterbox_result = letterbox(frame, (self.input_shape[2], self.input_shape[3]))
        resized = letterbox_result.image
        ratio = letterbox_result.ratio
        pad_x, pad_y = letterbox_result.padding

        image = resized[:, :, ::-1].transpose(2, 0, 1)  # BGR to RGB, HWC to CHW
        image = np.ascontiguousarray(image, dtype=np.float32) / 255.0
        image = np.expand_dims(image, axis=0)

        outputs = self.session.run([self.output_name], {self.input_name: image})[0]
        detections = self._post_process(outputs, ratio, pad_x, pad_y, frame.shape[:2])

        elapsed = (time.time() - start) * 1000
        self.logger.debug("Inference completed in %.2f ms", elapsed)
        return detections

    def _post_process(
        self,
        predictions: np.ndarray,
        ratio: float,
        pad_x: int,
        pad_y: int,
        original_shape: tuple[int, int],
    ) -> List[Detection]:
        """
        Convert raw model outputs into a list of Detection objects.
        """

        if predictions.ndim == 3:
            predictions = np.squeeze(predictions, axis=0)

        boxes = predictions[:, :4]
        scores = predictions[:, 4:]

        class_ids = np.argmax(scores, axis=1)
        confidences = scores[np.arange(scores.shape[0]), class_ids]

        mask = confidences > self.conf_threshold
        boxes = boxes[mask]
        confidences = confidences[mask]
        class_ids = class_ids[mask]

        if boxes.size == 0:
            return []

        boxes = self._xywh2xyxy(boxes)
        boxes -= np.array([pad_x, pad_y, pad_x, pad_y])
        boxes /= ratio
        boxes[:, [0, 2]] = np.clip(boxes[:, [0, 2]], 0, original_shape[1])
        boxes[:, [1, 3]] = np.clip(boxes[:, [1, 3]], 0, original_shape[0])

        indices = self._nms(boxes, confidences, self.iou_threshold)

        detections: List[Detection] = []
        for idx in indices:
            class_id = int(class_ids[idx])
            class_name = (
                self.class_names[class_id]
                if 0 <= class_id < len(self.class_names)
                else str(class_id)
            )
            detections.append(
                Detection(
                    bbox=boxes[idx],
                    confidence=float(confidences[idx]),
                    class_id=class_id,
                    class_name=class_name,
                )
            )
        return detections

    @staticmethod
    def _xywh2xyxy(x: np.ndarray) -> np.ndarray:
        y = np.zeros_like(x)
        y[:, 0] = x[:, 0] - x[:, 2] / 2
        y[:, 1] = x[:, 1] - x[:, 3] / 2
        y[:, 2] = x[:, 0] + x[:, 2] / 2
        y[:, 3] = x[:, 1] + x[:, 3] / 2
        return y

    @staticmethod
    def _nms(boxes: np.ndarray, scores: np.ndarray, iou_threshold: float) -> List[int]:
        indices = cv2.dnn.NMSBoxes(
            boxes.tolist(),
            scores.tolist(),
            score_threshold=0.0,
            nms_threshold=iou_threshold,
        )
        if len(indices) == 0:
            return []
        if isinstance(indices, np.ndarray):
            indices = indices.flatten().tolist()
        return [int(i) for i in indices]

