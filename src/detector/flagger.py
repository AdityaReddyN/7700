"""M4: the rule-based flagger (fallback, D-030).

The original detector design, kept as a transparent fallback selected by
``method: rules`` in ``config/detector.yaml``. It scores a window by the largest
robust z-score of any feature against the baseline, so a single feature far from
normal traffic raises the alert. It shares the baseline and feature set with the
Isolation Forest, so the rest of the pipeline is unchanged when it is selected.
"""

from __future__ import annotations

import numpy as np

from detector.baseline import Baseline
from detector.features import robust_z


class RuleFlagger:
    method = "rules"

    def __init__(self, cfg: dict) -> None:
        self._z_flag = float(cfg.get("z_flag", 4.0))
        self._median: np.ndarray | None = None
        self._mad: np.ndarray | None = None

    @property
    def z_flag(self) -> float:
        return self._z_flag

    def fit(self, baseline: Baseline) -> RuleFlagger:
        self._median = baseline.median
        self._mad = baseline.mad
        return self

    def score(self, vec: np.ndarray) -> float:
        """Anomaly score = max |robust z| over features; higher is more anomalous."""
        if self._median is None or self._mad is None:
            raise RuntimeError("flagger not fitted")
        zs = [
            abs(robust_z(float(vec[j]), float(self._median[j]), float(self._mad[j])))
            for j in range(vec.size)
        ]
        return float(max(zs)) if zs else 0.0

    def score_many(self, matrix: np.ndarray) -> np.ndarray:
        return np.array([self.score(matrix[i]) for i in range(matrix.shape[0])], dtype="float64")
