"""Tests for aeloria.training.kohya_flux."""
from unittest.mock import MagicMock, patch

import pytest

from aeloria.training.kohya_flux import (
    KohyaFluxTrainer,
    TrainingConfig,
    TrainingRun,
)


class TestTrainingConfig:
    def test_defaults(self):
        cfg = TrainingConfig()
        assert cfg.max_train_steps == 1500
        assert cfg.rank == 16
        assert cfg.resolution == 1024
        assert cfg.backend == "kohya_ss"

    def test_from_settings_none(self):
        """from_settings(None) uses get_settings() internally — settings must be loadable."""
        cfg = TrainingConfig.from_settings(None)
        assert isinstance(cfg, TrainingConfig)

    def test_custom_values(self):
        cfg = TrainingConfig(max_train_steps=500, rank=8, batch_size=2)
        assert cfg.max_train_steps == 500
        assert cfg.rank == 8
        assert cfg.batch_size == 2


class TestTrainingRun:
    def test_defaults(self):
        from datetime import datetime
        run = TrainingRun(run_id="r1", started_at=datetime.now())
        assert run.status == "queued"
        assert run.current_step == 0
        assert run.loss is None


class TestKohyaFluxTrainer:
    def test_init_no_koha_dir(self, monkeypatch, tmp_path):
        """Trainer initialises without KOHA_DIR existing (auto-creates)."""
        monkeypatch.setenv("KOHA_DIR", str(tmp_path / "nonexistent"))
        from aeloria.config import get_settings
        trainer = KohyaFluxTrainer(get_settings())
        assert trainer is not None

    def test_start_training_returns_run(self, monkeypatch, tmp_path):
        """start_training returns a TrainingRun with expected fields."""
        monkeypatch.setenv("KOHA_DIR", str(tmp_path))
        monkeypatch.setenv("HF_TOKEN", "fake")
        from aeloria.config import get_settings
        trainer = KohyaFluxTrainer(get_settings())
        cfg = TrainingConfig(max_train_steps=10)

        # Mock _ensure_kohya to return a fake Path so no filesystem check happens
        fake_path = tmp_path / "kohya_ss"
        with patch.object(KohyaFluxTrainer, "_ensure_kohya", return_value=fake_path):
            with patch.object(KohyaFluxTrainer, "_build_kohya_cmd", return_value=["echo", "ok"]):
                run = trainer.start_training("", "test_lora", cfg)

        assert isinstance(run, TrainingRun)
        assert run.run_id is not None
        assert hasattr(run, "status")
        assert hasattr(run, "current_step")
        assert hasattr(run, "max_steps")
        assert run.max_steps == 10
        assert run.status in {"queued", "running"}
