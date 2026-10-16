"""Scikit-learn model adapters for Qlib DatasetH backtests."""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from qlib.data.dataset.handler import DataHandlerLP


class SklearnQlibModel:
    """PLS/Lasso adapter exposing Qlib's fit/predict model contract."""

    def __init__(self, model_type: str, random_state: int = 42):
        if model_type not in {"pls5", "lasso"}:
            raise ValueError(f"Unsupported sklearn Qlib model: {model_type}")
        self.model_type = model_type
        self.random_state = random_state
        self.model: Any = None
        self.feature_columns: list[str] = []
        self.fill_values = pd.Series(dtype=float)
        self.details: dict[str, Any] = {"model": model_type}

    @staticmethod
    def _split(frame: pd.DataFrame, include_label: bool):
        if not isinstance(frame, pd.DataFrame):
            frame = frame.to_frame()
        if isinstance(frame.columns, pd.MultiIndex):
            features = frame["feature"].copy()
            labels = frame["label"].copy() if include_label else None
        elif include_label:
            label_columns = [column for column in frame.columns if str(column).upper().startswith("LABEL")]
            if not label_columns:
                raise ValueError("Dataset contains no label column")
            labels = frame[label_columns].copy()
            features = frame.drop(columns=label_columns)
        else:
            features, labels = frame.copy(), None
        if labels is not None and isinstance(labels, pd.DataFrame):
            labels = labels.iloc[:, 0]
        return features, labels

    @classmethod
    def _prepare(cls, dataset, segment: str, include_label: bool):
        col_set = ["feature", "label"] if include_label else "feature"
        data_key = DataHandlerLP.DK_L if include_label else DataHandlerLP.DK_I
        frame = dataset.prepare(segment, col_set=col_set, data_key=data_key)
        return cls._split(frame, include_label)

    @staticmethod
    def _clean(features: pd.DataFrame, fill_values: pd.Series | None = None):
        cleaned = features.apply(pd.to_numeric, errors="coerce").replace([np.inf, -np.inf], np.nan)
        if fill_values is None:
            fill_values = cleaned.median(axis=0).fillna(0.0)
        cleaned = cleaned.fillna(fill_values).fillna(0.0).astype("float32")
        return cleaned, fill_values

    def fit(self, dataset) -> None:
        from sklearn.cross_decomposition import PLSRegression
        from sklearn.linear_model import Lasso
        from sklearn.metrics import mean_squared_error
        from sklearn.pipeline import make_pipeline
        from sklearn.preprocessing import StandardScaler

        train_x, train_y = self._prepare(dataset, "train", True)
        valid_x, valid_y = self._prepare(dataset, "valid", True)
        self.feature_columns = [str(column) for column in train_x.columns]
        valid_x = valid_x.reindex(columns=train_x.columns)
        train_x, train_fill = self._clean(train_x)
        valid_x, _ = self._clean(valid_x, train_fill)
        train_y = pd.to_numeric(train_y, errors="coerce")
        valid_y = pd.to_numeric(valid_y, errors="coerce")
        train_mask, valid_mask = train_y.notna(), valid_y.notna()
        train_x, train_y = train_x.loc[train_mask], train_y.loc[train_mask]
        valid_x, valid_y = valid_x.loc[valid_mask], valid_y.loc[valid_mask]
        if train_x.empty or valid_x.empty:
            raise ValueError("Training or validation segment has no usable observations")

        if self.model_type == "lasso":
            candidates = (1e-5, 3e-5, 1e-4, 3e-4, 1e-3, 3e-3, 1e-2)
            best_alpha, best_loss = None, float("inf")
            for alpha in candidates:
                candidate = make_pipeline(
                    StandardScaler(),
                    Lasso(alpha=alpha, max_iter=5000, tol=1e-4, selection="cyclic"),
                )
                candidate.fit(train_x, train_y)
                loss = float(mean_squared_error(valid_y, candidate.predict(valid_x)))
                if loss < best_loss:
                    best_alpha, best_loss = alpha, loss
            combined_x = pd.concat([train_x, valid_x])
            combined_y = pd.concat([train_y, valid_y])
            self.model = make_pipeline(
                StandardScaler(),
                Lasso(alpha=float(best_alpha), max_iter=5000, tol=1e-4, selection="cyclic"),
            )
            self.model.fit(combined_x, combined_y)
            self.details.update({"alpha": float(best_alpha), "validation_mse": best_loss})
        else:
            maximum = max(1, min(5, train_x.shape[1], train_x.shape[0] - 1))
            best_components, best_loss = 1, float("inf")
            for components in range(1, maximum + 1):
                candidate = PLSRegression(n_components=components, scale=True, max_iter=500)
                candidate.fit(train_x, train_y)
                prediction = np.asarray(candidate.predict(valid_x)).reshape(-1)
                loss = float(mean_squared_error(valid_y, prediction))
                if loss < best_loss:
                    best_components, best_loss = components, loss
            combined_x = pd.concat([train_x, valid_x])
            combined_y = pd.concat([train_y, valid_y])
            self.model = PLSRegression(n_components=best_components, scale=True, max_iter=500)
            self.model.fit(combined_x, combined_y)
            self.details.update({"components": best_components, "validation_mse": best_loss})

        combined_raw = pd.concat([
            self._prepare(dataset, "train", True)[0],
            self._prepare(dataset, "valid", True)[0],
        ]).reindex(columns=self.feature_columns)
        _, self.fill_values = self._clean(combined_raw)

    def predict(self, dataset, segment: str = "test") -> pd.Series:
        if self.model is None:
            raise RuntimeError("Model must be fitted before prediction")
        features, _ = self._prepare(dataset, segment, False)
        features = features.reindex(columns=self.feature_columns)
        features, _ = self._clean(features, self.fill_values)
        prediction = np.asarray(self.model.predict(features)).reshape(-1)
        return pd.Series(prediction, index=features.index, name="score")
