"""M4: the Isolation Forest detector (primary, D-030).

Fits scikit-learn's IsolationForest on the normal-traffic baseline and scores a
feature vector so that a higher score means more anomalous. Features are
log1p-compressed (all are non-negative and heavy-tailed) and standardised before
the forest sees them. random_state is fixed for determinism (ARCHITECTURE §9).
"""

from __future__ import annotations

import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

from detector.baseline import Baseline


def _transform(matrix: np.ndarray) -> np.ndarray:
    return np.log1p(np.clip(matrix, 0.0, None))


class IsolationForestDetector:
    method = "isolation_forest"

    def __init__(self, cfg: dict) -> None:
        contamination = cfg.get("contamination", "auto")
        self._scaler = StandardScaler()
        self._forest = IsolationForest(
            n_estimators=int(cfg.get("n_estimators", 200)),
            contamination=contamination,
            max_samples=cfg.get("max_samples", "auto"),
            random_state=int(cfg.get("random_state", 42)),
        )
        self._fitted = False

    def fit(self, baseline: Baseline) -> IsolationForestDetector:
        x = self._scaler.fit_transform(_transform(baseline.matrix))
        self._forest.fit(x)
        self._fitted = True
        return self

    def score(self, vec: np.ndarray) -> float:
        """Anomaly score; higher is more anomalous."""
        if not self._fitted:
            raise RuntimeError("detector not fitted")
        x = self._scaler.transform(_transform(vec.reshape(1, -1)))
        return float(-self._forest.decision_function(x)[0])

    def score_many(self, matrix: np.ndarray) -> np.ndarray:
        if not self._fitted:
            raise RuntimeError("detector not fitted")
        if matrix.shape[0] == 0:
            return np.empty(0, dtype="float64")
        x = self._scaler.transform(_transform(matrix))
        return -self._forest.decision_function(x)
