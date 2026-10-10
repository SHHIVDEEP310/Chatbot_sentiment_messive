"""
Wraps the pre-trained sentiment model. Loaded exactly once (at app
startup, see main.py) and reused across requests.

Nothing about the label set, num_labels, or preprocessing is assumed
here: everything is read from the checkpoint's own config.json /
tokenizer_config.json via `from_pretrained`.
"""
import logging
import os
import re
from typing import Dict, List

from app.config import get_settings

settings = get_settings()

logger = logging.getLogger("sentiment_service")

# NOTE: torch / transformers are imported lazily inside load(), not at
# module import time. They're large, optional-at-import-time dependencies
# (e.g. test suites that stub out SentimentService entirely, or app
# startup paths that only check health) shouldn't be forced to pay their
# import cost or require them installed.


_GENERIC_LABEL = re.compile(r"^LABEL_(\d+)$", re.IGNORECASE)


def _parse_label_map(raw: str) -> Dict[int, str]:
    out: Dict[int, str] = {}
    for part in (raw or "").split(","):
        if ":" in part:
            idx, name = part.split(":", 1)
            if idx.strip().isdigit() and name.strip():
                out[int(idx.strip())] = name.strip().lower()
    return out


def friendly_label(label: str) -> str:
    """LABEL_2 -> positive (via LABEL_MAP). Real names pass through untouched."""
    m = _GENERIC_LABEL.match(label or "")
    if not m:
        return label
    return _parse_label_map(settings.LABEL_MAP).get(int(m.group(1)), label)


def friendly_scores(scores: Dict[str, float]) -> Dict[str, float]:
    return {friendly_label(k): v for k, v in scores.items()}


class ModelNotLoadedError(RuntimeError):
    pass


class InferenceError(RuntimeError):
    pass


class SentimentService:
    """
    Loads a HuggingFace sequence-classification checkpoint and exposes
    single/batch predict methods. Instantiate once; share the instance
    across the app (see app.state.ml_service in main.py).
    """

    def __init__(self, model_path: str):
        self.model_path = model_path
        self.tokenizer = None
        self.model = None
        self.device = None
        self.id2label: Dict[int, str] = {}

    def load(self) -> None:
        # Check the cheap thing (does the directory even exist) before
        # paying the cost of importing torch/transformers, and before
        # either of those being missing/broken can raise a confusing
        # ImportError instead of our own clear error.
        if not os.path.isdir(self.model_path):
            raise ModelNotLoadedError(
                f"Model path '{self.model_path}' does not exist. Set MODEL_PATH "
                "to the directory containing config.json / model.safetensors / "
                "tokenizer files."
            )

        try:
            import torch
            from transformers import AutoModelForSequenceClassification, AutoTokenizer
        except ImportError as exc:
            raise ModelNotLoadedError(
                f"Required ML libraries are not installed: {exc}. "
                "Run `pip install -r requirements.txt`."
            ) from exc

        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        logger.info("Loading tokenizer and model from %s", self.model_path)
        self.tokenizer = AutoTokenizer.from_pretrained(self.model_path)
        self.model = AutoModelForSequenceClassification.from_pretrained(self.model_path)
        self.model.to(self.device)
        self.model.eval()

        # Respect whatever id2label the checkpoint itself declares.
        raw_id2label = getattr(self.model.config, "id2label", None)
        if not raw_id2label:
            raise ModelNotLoadedError(
                "Loaded model config has no id2label mapping; cannot determine "
                "the label set."
            )
        self.id2label = {int(k): v for k, v in raw_id2label.items()}
        logger.info("Model loaded. Labels: %s", self.id2label)
        if any(_GENERIC_LABEL.match(v) for v in self.id2label.values()):
            logger.warning(
                "Checkpoint uses generic labels %s; displaying them via LABEL_MAP=%r. "
                "Verify this matches your training label order.",
                self.id2label, settings.LABEL_MAP,
            )

    def is_ready(self) -> bool:
        return self.model is not None and self.tokenizer is not None

    def _ensure_ready(self) -> None:
        if not self.is_ready():
            raise ModelNotLoadedError("Sentiment model is not loaded.")

    def predict_batch(self, texts: List[str]) -> List[Dict[str, float]]:
        """
        Returns one dict per input text: {"scores": {label: prob, ...}}
        Order matches the input order; no merging or averaging across items.
        """
        self._ensure_ready()
        import torch
        import torch.nn.functional as F

        try:
            with torch.no_grad():
                encoded = self.tokenizer(
                    texts,
                    padding=True,
                    truncation=True,
                    return_tensors="pt",
                ).to(self.device)
                logits = self.model(**encoded).logits
                probs = F.softmax(logits, dim=-1).cpu().tolist()
        except Exception as exc:  # noqa: BLE001 - surface as a clean 5xx upstream
            logger.exception("Inference failed")
            raise InferenceError(str(exc)) from exc

        results = []
        for row in probs:
            scores = {
                self.id2label[i]: round(float(p), 6) for i, p in enumerate(row)
            }
            results.append(friendly_scores(scores))
        return results

    def predict_single(self, text: str) -> Dict[str, float]:
        return self.predict_batch([text])[0]


def top_label(scores: Dict[str, float]) -> str:
    return max(scores, key=scores.get)


def build_insight(label: str, scores: Dict[str, float]) -> str:
    """
    Short, rule-based, contextual suggestion. Deliberately simple and
    deterministic — no extra model call, just a mapping over the
    predicted label and its confidence.
    """
    confidence = scores.get(label, 0.0)
    label_lower = label.lower()
    strength = "strongly" if confidence >= 0.75 else "somewhat"

    if "pos" in label_lower:
        return (
            f"This reads as {strength} positive ({confidence:.0%} confidence). "
            "Good moment to capture what's working — consider highlighting or "
            "amplifying this feedback."
        )
    if "neg" in label_lower:
        return (
            f"This reads as {strength} negative ({confidence:.0%} confidence). "
            "Worth a closer look — consider following up to understand and "
            "address the underlying concern."
        )
    return (
        f"This reads as neutral ({confidence:.0%} confidence). "
        "No strong signal either way — useful as a baseline data point."
    )
