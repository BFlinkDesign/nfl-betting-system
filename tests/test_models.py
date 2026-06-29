"""Tests for src/models package."""

import numpy as np
import pandas as pd
import pytest

from src.models.base import NFLModel
from src.models.calibration import ModelCalibrator
from src.models.ensemble import EnsembleModel
from src.models.lightgbm_model import LightGBMModel
from src.models.xgboost_model import XGBoostNFLModel


@pytest.fixture
def synthetic_data():
    """Generate small synthetic dataset for model tests."""
    rng = np.random.default_rng(42)
    n = 200
    X = pd.DataFrame(
        {
            "elo_diff": rng.normal(0, 50, n),
            "rest_days_home": rng.integers(4, 14, n).astype(float),
            "rest_days_away": rng.integers(4, 14, n).astype(float),
            "form_home": rng.uniform(-0.5, 0.5, n),
            "form_away": rng.uniform(-0.5, 0.5, n),
        }
    )
    prob = 1.0 / (1.0 + np.exp(-0.01 * X["elo_diff"]))
    y = pd.Series((rng.random(n) < prob).astype(int))
    return X, y


class TestXGBoostNFLModel:
    def test_init_default(self):
        model = XGBoostNFLModel()
        assert model.model is not None

    def test_init_with_config(self):
        config = {"params": {"n_estimators": 50, "max_depth": 3}}
        model = XGBoostNFLModel(config)
        assert model.model.n_estimators == 50

    def test_train_and_predict(self, synthetic_data):
        X, y = synthetic_data
        X_train, X_test = X[:150], X[150:]
        y_train, y_test = y[:150], y[150:]

        model = XGBoostNFLModel({"params": {"n_estimators": 20, "max_depth": 3}})
        model.train(X_train, y_train, X_test, y_test)

        proba = model.predict_proba(X_test)
        assert proba.shape == (50, 2)
        assert np.allclose(proba.sum(axis=1), 1.0)

    def test_evaluate(self, synthetic_data):
        X, y = synthetic_data
        model = XGBoostNFLModel({"params": {"n_estimators": 20}})
        model.train(X[:150], y[:150])

        metrics = model.evaluate(X[150:], y[150:])
        assert "accuracy" in metrics
        assert "brier_score" in metrics
        assert "log_loss" in metrics
        assert "roc_auc" in metrics
        assert 0 <= metrics["accuracy"] <= 1

    def test_feature_importance(self, synthetic_data):
        X, y = synthetic_data
        model = XGBoostNFLModel({"params": {"n_estimators": 20}})
        model.train(X, y)

        importance = model.get_feature_importance()
        assert isinstance(importance, dict)
        assert len(importance) == 5
        assert all(v >= 0 for v in importance.values())

    def test_save_and_load(self, synthetic_data, tmp_path):
        X, y = synthetic_data
        model = XGBoostNFLModel({"params": {"n_estimators": 20}})
        model.train(X, y)

        path = str(tmp_path / "test_model.json")
        model.save(path)

        loaded = XGBoostNFLModel.load(path)
        orig = model.predict_proba(X[:5])
        reloaded = loaded.predict_proba(X[:5])
        np.testing.assert_array_almost_equal(orig, reloaded, decimal=5)

    def test_is_nfl_model(self):
        assert issubclass(XGBoostNFLModel, NFLModel)


class TestLightGBMModel:
    def test_init(self):
        model = LightGBMModel()
        assert model.model is not None

    def test_fit_and_predict(self, synthetic_data):
        X, y = synthetic_data
        model = LightGBMModel({"params": {"n_estimators": 20}})
        model.fit(X[:150], y[:150])

        proba = model.predict_proba(X[150:])
        assert proba.shape == (50, 2)

    def test_train_delegates_to_fit(self, synthetic_data):
        X, y = synthetic_data
        model = LightGBMModel({"params": {"n_estimators": 20}})
        model.train(X[:150], y[:150])
        assert len(model.feature_names) == 5

    def test_evaluate(self, synthetic_data):
        X, y = synthetic_data
        model = LightGBMModel({"params": {"n_estimators": 20}})
        model.fit(X[:150], y[:150])
        metrics = model.evaluate(X[150:], y[150:])
        assert 0 <= metrics["accuracy"] <= 1


class TestEnsembleModel:
    def test_weighted_average(self, synthetic_data):
        X, y = synthetic_data
        X_train, X_test = X[:150], X[150:]
        y_train, y_test = y[:150], y[150:]

        xgb = XGBoostNFLModel({"params": {"n_estimators": 20}})
        xgb.train(X_train, y_train)

        lgb = LightGBMModel({"params": {"n_estimators": 20}})
        lgb.fit(X_train, y_train)

        ensemble = EnsembleModel(
            models=[xgb, lgb], weights=[0.6, 0.4], method="weighted_average"
        )
        ensemble.fit(X_train, y_train)

        proba = ensemble.predict_proba(X_test)
        assert proba.shape == (50, 2)

    def test_evaluate(self, synthetic_data):
        X, y = synthetic_data
        xgb = XGBoostNFLModel({"params": {"n_estimators": 20}})
        xgb.train(X[:150], y[:150])

        ensemble = EnsembleModel(models=[xgb], weights=[1.0])
        metrics = ensemble.evaluate(X[150:], y[150:])
        assert "accuracy" in metrics

    def test_feature_importance_combined(self, synthetic_data):
        X, y = synthetic_data
        xgb = XGBoostNFLModel({"params": {"n_estimators": 20}})
        xgb.train(X, y)
        lgb = LightGBMModel({"params": {"n_estimators": 20}})
        lgb.fit(X, y)

        ensemble = EnsembleModel(models=[xgb, lgb], weights=[0.5, 0.5])
        importance = ensemble.get_feature_importance()
        assert len(importance) > 0


class TestModelCalibrator:
    def test_calibrate_and_evaluate(self, synthetic_data):
        X, y = synthetic_data
        X_train, X_val, X_test = X[:120], X[120:160], X[160:]
        y_train, y_val, y_test = y[:120], y[120:160], y[160:]

        model = XGBoostNFLModel({"params": {"n_estimators": 30}})
        model.train(X_train, y_train)

        calibrator = ModelCalibrator(model, method="sigmoid", cv="prefit")
        calibrator.calibrate(X_val, y_val)

        cal_metrics = calibrator.evaluate_calibration(X_test, y_test)
        assert "brier_uncalibrated" in cal_metrics
        assert "brier_calibrated" in cal_metrics
        assert "improvement_pct" in cal_metrics

    def test_predict_proba_calibrated(self, synthetic_data):
        X, y = synthetic_data
        model = XGBoostNFLModel({"params": {"n_estimators": 20}})
        model.train(X[:150], y[:150])

        calibrator = ModelCalibrator(model)
        calibrator.calibrate(X[150:180], y[150:180])

        proba = calibrator.predict_proba(X[180:])
        assert proba.shape[0] == 20
        assert proba.shape[1] == 2

    def test_plot_calibration_curve(self, synthetic_data, tmp_path):
        X, y = synthetic_data
        model = XGBoostNFLModel({"params": {"n_estimators": 20}})
        model.train(X[:150], y[:150])

        calibrator = ModelCalibrator(model)
        calibrator.calibrate(X[150:180], y[150:180])

        path = str(tmp_path / "cal_curve.png")
        calibrator.plot_calibration_curve(X[180:], y[180:], save_path=path)
        assert (tmp_path / "cal_curve.png").exists()
