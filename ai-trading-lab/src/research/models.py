"""Monthly rolling fits (00:00 UTC on the 1st, 365-day window, mature labels only) and prequential OOS predictions."""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge


def fit_times(first_fit: pd.Timestamp, split_start: pd.Timestamp, split_end: pd.Timestamp) -> list[pd.Timestamp]:
    s = max(first_fit, split_start)
    return list(pd.date_range(s, split_end, freq="MS", inclusive="left", tz="UTC"))


def model_id_for(T: pd.DatetimeIndex, fits: list[pd.Timestamp]) -> np.ndarray:
    """Index of the latest fit <= T (or -1)."""
    f = pd.DatetimeIndex(fits)
    return np.searchsorted(f.asi8, T.asi8, side="right") - 1


def train_mask(T: pd.DatetimeIndex, F: pd.Timestamp, window_days: int, delay_min: int, hold_min: int,
               crosses: np.ndarray) -> np.ndarray:
    """Rows whose decision lies in [F - window, F) and whose label is complete by F (exit open <= F)."""
    exit_t = T + pd.Timedelta(minutes=delay_min + hold_min)
    return (T >= F - pd.Timedelta(days=window_days)) & (T < F) & (exit_t <= F) & ~crosses


class RidgeFit:
    def __init__(self, alpha: float):
        self.alpha = alpha

    def fit(self, X: pd.DataFrame, y: np.ndarray):
        mu = X.mean(axis=0)
        sd = X.std(axis=0, ddof=0)
        self.dropped = [c for c in X.columns if not np.isfinite(sd[c]) or sd[c] == 0]
        self.cols = [c for c in X.columns if c not in self.dropped]
        self.mu, self.sd = mu[self.cols], sd[self.cols]
        Z = ((X[self.cols] - self.mu) / self.sd).to_numpy()
        self.m = Ridge(alpha=self.alpha, fit_intercept=True).fit(Z, y)
        self.n = len(y)
        return self

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        Z = ((X[self.cols] - self.mu) / self.sd).to_numpy()
        return self.m.predict(Z)

    def coef_record(self) -> dict:
        return {"intercept": float(self.m.intercept_), "n_train": int(self.n), "dropped_zero_var": self.dropped,
                **{f"coef_std::{c}": float(v) for c, v in zip(self.cols, self.m.coef_)}}


def calib_edges(pred_train: np.ndarray, n_bins: int = 10) -> np.ndarray:
    q = np.quantile(pred_train, np.linspace(0, 1, n_bins + 1)[1:-1])
    return np.unique(q)
