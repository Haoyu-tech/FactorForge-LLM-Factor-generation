"""Walk-forward expanding-window models for independent factor backtests."""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from qlib.data.dataset.handler import DataHandlerLP


class ExpandingQlibModel:
    """Tune on train/validation, then refit using only data known at each block."""

    def __init__(self, model_type: str = "lightgbm", retrain_months: int = 12,
                 min_train_years: int = 10, random_state: int = 42):
        if model_type not in {"lightgbm", "pls5", "lasso"}:
            raise ValueError(f"Unsupported expanding model: {model_type}")
        self.model_type = model_type
        self.retrain_months = max(1, int(retrain_months))
        self.min_train_years = max(1, int(min_train_years))
        self.random_state = random_state
        self.feature_columns: list[Any] = []
        self.tuning: dict[str, Any] = {}
        self.details: dict[str, Any] = {
            "model": model_type,
            "expanding_window": True,
            "retrain_months": self.retrain_months,
            "min_train_years": self.min_train_years,
        }
        self._dataset = None

    @staticmethod
    def _split(frame: pd.DataFrame, include_label: bool):
        if not isinstance(frame, pd.DataFrame):
            frame = frame.to_frame()
        if isinstance(frame.columns, pd.MultiIndex):
            features = frame["feature"].copy()
            labels = frame["label"].copy() if include_label else None
        elif include_label:
            label_columns = [c for c in frame.columns if str(c).upper().startswith("LABEL")]
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
    def _dates(index: pd.Index) -> pd.DatetimeIndex:
        if isinstance(index, pd.MultiIndex):
            names = list(index.names)
            level = names.index("datetime") if "datetime" in names else 0
            return pd.DatetimeIndex(pd.to_datetime(index.get_level_values(level)))
        return pd.DatetimeIndex(pd.to_datetime(index))

    @staticmethod
    def _clean(features: pd.DataFrame, fill_values: pd.Series | None = None):
        cleaned = features.apply(pd.to_numeric, errors="coerce").replace([np.inf, -np.inf], np.nan)
        if fill_values is None:
            fill_values = cleaned.median(axis=0).fillna(0.0)
        # Fill each feature from the same date's stock cross-section. This is
        # observable at prediction time and avoids mixing future dates into an
        # imputation value. Fall back to the fitted-history median only when a
        # whole date/feature cross-section is missing.
        if isinstance(cleaned.index, pd.MultiIndex):
            names = list(cleaned.index.names)
            date_level = names.index("datetime") if "datetime" in names else 0
            cross_section_median = cleaned.groupby(level=date_level).transform("median")
            cleaned = cleaned.fillna(cross_section_median)
        return cleaned.fillna(fill_values).fillna(0.0).astype("float32"), fill_values

    @staticmethod
    def _valid_xy(features: pd.DataFrame, labels: pd.Series):
        labels = pd.to_numeric(labels, errors="coerce")
        mask = labels.notna()
        return features.loc[mask], labels.loc[mask].astype("float32")

    def fit(self, dataset) -> None:
        from lightgbm import LGBMRegressor, early_stopping
        from sklearn.cross_decomposition import PLSRegression
        from sklearn.linear_model import Lasso
        from sklearn.metrics import mean_squared_error
        from sklearn.pipeline import make_pipeline
        from sklearn.preprocessing import StandardScaler

        self._dataset = dataset
        train_x, train_y = self._prepare(dataset, "train", True)
        valid_x, valid_y = self._prepare(dataset, "valid", True)
        self.feature_columns = list(train_x.columns)
        valid_x = valid_x.reindex(columns=self.feature_columns)
        train_x, fill = self._clean(train_x)
        valid_x, _ = self._clean(valid_x, fill)
        train_x, train_y = self._valid_xy(train_x, train_y)
        valid_x, valid_y = self._valid_xy(valid_x, valid_y)
        if train_x.empty or valid_x.empty:
            raise ValueError("Training or validation segment has no usable observations")

        if self.model_type == "lightgbm":
            candidate = LGBMRegressor(
                objective="regression", n_estimators=600, learning_rate=.035,
                num_leaves=31, min_child_samples=100, subsample=.85,
                colsample_bytree=.80, reg_alpha=.1, reg_lambda=1.0,
                random_state=self.random_state, n_jobs=2, verbosity=-1,
            )
            candidate.fit(
                train_x, train_y, eval_set=[(valid_x, valid_y)], eval_metric="l2",
                callbacks=[early_stopping(40, verbose=False)],
            )
            self.tuning["best_iterations"] = int(candidate.best_iteration_ or 180)
        elif self.model_type == "lasso":
            best_alpha, best_loss = 1e-3, float("inf")
            for alpha in (1e-5, 3e-5, 1e-4, 3e-4, 1e-3, 3e-3, 1e-2):
                candidate = make_pipeline(
                    StandardScaler(),
                    Lasso(alpha=alpha, max_iter=5000, tol=1e-4, selection="cyclic"),
                )
                candidate.fit(train_x, train_y)
                loss = float(mean_squared_error(valid_y, candidate.predict(valid_x)))
                if loss < best_loss:
                    best_alpha, best_loss = alpha, loss
            self.tuning.update(best_alpha=float(best_alpha), validation_mse=best_loss)
        else:
            maximum = max(1, min(5, train_x.shape[1], train_x.shape[0] - 1))
            best_components, best_loss = 1, float("inf")
            for components in range(1, maximum + 1):
                candidate = PLSRegression(n_components=components, scale=True, max_iter=500)
                candidate.fit(train_x, train_y)
                loss = float(mean_squared_error(
                    valid_y, np.asarray(candidate.predict(valid_x)).reshape(-1)
                ))
                if loss < best_loss:
                    best_components, best_loss = components, loss
            self.tuning.update(n_components=int(best_components), validation_mse=best_loss)
        self.details.update(self.tuning)

    def _new_model(self):
        if self.model_type == "lightgbm":
            from lightgbm import LGBMRegressor
            return LGBMRegressor(
                objective="regression",
                n_estimators=int(self.tuning["best_iterations"]),
                learning_rate=.035, num_leaves=31, min_child_samples=100,
                subsample=.85, colsample_bytree=.80, reg_alpha=.1, reg_lambda=1.0,
                random_state=self.random_state, n_jobs=2, verbosity=-1,
            )
        if self.model_type == "lasso":
            from sklearn.linear_model import Lasso
            from sklearn.pipeline import make_pipeline
            from sklearn.preprocessing import StandardScaler
            return make_pipeline(
                StandardScaler(),
                Lasso(alpha=float(self.tuning["best_alpha"]), max_iter=5000,
                      tol=1e-4, selection="cyclic"),
            )
        from sklearn.cross_decomposition import PLSRegression
        return PLSRegression(
            n_components=int(self.tuning["n_components"]), scale=True, max_iter=500
        )

    def predict(self, dataset=None, segment: str = "test") -> pd.Series:
        dataset = dataset or self._dataset
        if dataset is None or not self.feature_columns:
            raise RuntimeError("Model must be fitted before prediction")
        if segment != "test":
            raise ValueError("ExpandingQlibModel only emits held-out test predictions")

        historical = []
        for name in ("train", "valid", "test"):
            x, y = self._prepare(dataset, name, True)
            x = x.reindex(columns=self.feature_columns)
            historical.append((x, pd.to_numeric(y, errors="coerce")))
        all_x = pd.concat([item[0] for item in historical]).sort_index()
        all_y = pd.concat([item[1] for item in historical]).reindex(all_x.index)
        test_x, _ = historical[-1]
        test_dates = self._dates(test_x.index)
        months = pd.Index(test_dates.to_period("M").unique()).sort_values()
        outputs: list[pd.Series] = []
        refit_count = 0

        for offset in range(0, len(months), self.retrain_months):
            block_months = months[offset: offset + self.retrain_months]
            predict_mask = test_dates.to_period("M").isin(block_months)
            block_x = test_x.loc[predict_mask]
            if block_x.empty:
                continue
            refit_date = self._dates(block_x.index).min()
            all_dates = self._dates(all_x.index)
            known_dates = pd.DatetimeIndex(sorted(pd.unique(all_dates[all_dates < refit_date])))
            # The configured daily label contains forward prices. Leave two
            # complete trading dates between fitted labels and predictions.
            if len(known_dates) < 3:
                continue
            label_cutoff = known_dates[-3]
            train_mask = (all_dates <= label_cutoff) & all_y.notna().to_numpy()
            history_start = all_dates[train_mask].min() if train_mask.any() else None
            if history_start is None or refit_date < history_start + pd.DateOffset(years=self.min_train_years):
                continue
            fit_x = all_x.loc[train_mask]
            fit_y = all_y.loc[train_mask].astype("float32")
            fit_x, fill = self._clean(fit_x)
            predict_x, _ = self._clean(block_x, fill)
            model = self._new_model()
            model.fit(fit_x, fit_y)
            prediction = np.asarray(model.predict(predict_x)).reshape(-1)
            outputs.append(pd.Series(prediction, index=block_x.index, name="score"))
            refit_count += 1

        if not outputs:
            raise ValueError("Expanding window produced no out-of-sample predictions")
        result = pd.concat(outputs).sort_index()
        self.details.update({
            "refit_count": refit_count,
            "prediction_start": str(self._dates(result.index).min().date()),
            "prediction_end": str(self._dates(result.index).max().date()),
        })
        return result
