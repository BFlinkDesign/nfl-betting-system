"""Tests for auto-remediation and result updater."""

import pytest

from src.self_healing.auto_remediation import AutoRemediation


class TestAutoRemediation:
    def test_high_cpu_runs_gc(self):
        r = AutoRemediation()
        result = r.remediate({"type": "high_cpu"})
        assert result["remediated"] is True
        assert result["action"] == "gc_collect"

    def test_high_memory_clears_cache(self):
        r = AutoRemediation()
        result = r.remediate({"type": "high_memory"})
        assert result["remediated"] is True
        assert "gc_collect" in result["action"]

    def test_high_error_rate_trips_breakers(self):
        r = AutoRemediation()
        result = r.remediate({"type": "high_error_rate"})
        assert result["remediated"] is True

    def test_database_connection_checks_files(self):
        r = AutoRemediation()
        result = r.remediate({"type": "database_connection_lost"})
        assert "dbs_checked" in result

    def test_component_disconnect_resets_agents(self):
        r = AutoRemediation()
        result = r.remediate({"type": "component_disconnect"})
        assert result["remediated"] is True

    def test_unknown_type(self):
        r = AutoRemediation()
        result = r.remediate({"type": "alien_invasion"})
        assert result["remediated"] is False

    def test_history_recorded(self):
        r = AutoRemediation()
        r.remediate({"type": "high_cpu"})
        r.remediate({"type": "high_memory"})
        assert len(r.remediation_history) == 2


class TestResultUpdater:
    def test_get_pending_no_db(self, tmp_path):
        from src.learning.result_updater import ResultUpdater

        updater = ResultUpdater(db_path=str(tmp_path / "nonexistent.db"))
        assert updater.get_pending_predictions() == []

    def test_update_from_scores_win(self, tmp_path):
        import sqlite3

        db_path = str(tmp_path / "test_learn.db")
        conn = sqlite3.connect(db_path)
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS predictions (
                prediction_id TEXT PRIMARY KEY,
                game_id TEXT, timestamp TEXT, home_team TEXT, away_team TEXT,
                pick TEXT, bet_type TEXT, line REAL, odds REAL,
                confidence REAL, edge REAL, model_name TEXT,
                council_consensus REAL, tier TEXT, features TEXT,
                actual_result TEXT, actual_score_home INTEGER,
                actual_score_away INTEGER, profit REAL,
                what_went_wrong TEXT, what_went_right TEXT
            );
            INSERT INTO predictions (prediction_id, game_id, timestamp, home_team,
                away_team, pick, bet_type, line, odds, confidence, edge,
                model_name, council_consensus, tier, features)
            VALUES ('pred_001', 'g1', '2024-01-01', 'KC', 'BUF', 'home',
                'moneyline', 0, -150, 0.65, 0.05, 'xgb', 0.8, 'A_tier', '{}');
            """
        )
        conn.commit()
        conn.close()

        from src.learning.result_updater import ResultUpdater

        updater = ResultUpdater(db_path=db_path)
        result = updater.update_from_scores(
            prediction_id="pred_001",
            home_score=27,
            away_score=24,
            pick="home",
            odds=-150,
        )
        assert result["result"] == "win"
        assert result["profit"] > 0
