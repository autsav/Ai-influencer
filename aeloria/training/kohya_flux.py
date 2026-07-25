"""
Kohya_ss local LoRA training for FLUX.1.

Replaces the unintegrated hermes_photo_trainer root-level output.
Standardizes on Kohya_ss / OneTrainer scripts for FLUX.1 LoRA fine-tuning,
requiring 15–30 images and achieving consistency in ~1,500 steps.

Training dataset should be prepared as a folder of Aeloria images
(cropped/aligned to 1024×1024) and registered via dataset_config.toml.
"""

import logging
import os
import subprocess
import threading
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Literal

from aeloria.config import Settings, get_settings

logger = logging.getLogger(__name__)

# Kohya_ss repo location (clone once)
DEFAULT_KOYYA_REPO = os.path.expanduser("~/github/kohya_ss")

TrainerBackend = Literal["kohya_ss", "onetrainer"]


@dataclass
class TrainingConfig:
    """End-to-end LoRA training configuration."""

    # Paths
    base_model: str = "black-forest-labs/FLUX.1-dev"
    dataset_config: str = ""       # path to dataset.toml
    output_dir: str = "aeloria/training/output"
    output_name: str = "aeloria_lora"

    # Hyperparameters
    max_train_steps: int = 1500
    learning_rate: float = 1e-4
    rank: int = 16                 # LoRA rank (16 = good balance speed/quality)
    batch_size: int = 1
    resolution: int = 1024
    crop_style: str = "center"
    enable_exif: bool = True       # read EXIF orientation from dataset images

    # Scheduler
    lr_scheduler: str = "cosine_with_restarts"
    lr_warmup_steps: int = 100
    scheduler_num_cycles: int = 3

    # Dataloading
    num_workers: int = 4
    persistent_data_loader: bool = True

    # Mixed precision / optimisation
    mixed_precision: str = "bf16"
    gradient_accumulation_steps: int = 4

    # Backend
    backend: TrainerBackend = "kohya_ss"

    # Optional: gradient checkpointing for lower VRAM
    gradient_checkpointing: bool = True

    _settings: field(default=None, repr=False) = field(default=None, repr=False)

    @classmethod
    def from_settings(cls, settings: Settings | None = None) -> "TrainingConfig":
        s = settings or get_settings()
        return cls()


@dataclass
class TrainingRun:
    """Live status of an in-progress training run."""

    run_id: str
    started_at: datetime
    status: Literal["queued", "running", "completed", "failed"] = "queued"
    current_step: int = 0
    max_steps: int = 0
    loss: float | None = None
    output_path: str | None = None
    error: str | None = None


class KohyaFluxTrainer:
    """
    Orchestrates local FLUX.1 LoRA training via Kohya_ss or OneTrainer.

    Usage:
        trainer = KohyaFluxTrainer()
        run = trainer.start_training(
            dataset_config="/path/to/dataset.toml",
            output_name="aeloria_v2",
        )
        # Poll status:
        status = trainer.get_status(run.run_id)
        # Wait for completion:
        result = trainer.wait_for_completion(run.run_id)
    """

    def __init__(self, settings: Settings | None = None):
        s = settings or get_settings()
        self._kohya_repo = os.environ.get(
            "KOYYA_REPO", DEFAULT_KOYYA_REPO
        )
        self._venv_python = os.environ.get(
            "KOYYA_PYTHON", "python3"
        )
        self._runs: dict[str, TrainingRun] = {}
        self._lock = threading.Lock()

    # ── Internals ─────────────────────────────────────────────────────────────

    def _ensure_kohya(self) -> Path:
        """Verify Kohya_ss is cloned; raise if not found."""
        path = Path(self._kohya_repo)
        if not path.exists():
            raise RuntimeError(
                f"Kohya_ss not found at {self._kohya_repo}. "
                "Clone with: git clone https://github.com/kohya-ss/sd-scripts.git ~/github/kohya_ss"
            )
        return path

    def _build_kohya_cmd(self, cfg: TrainingConfig) -> list[str]:
        """Build the kohya_ss train_network.py command line."""
        cmd = [
            self._venv_python,
            str(self._ensure_kohya() / "sd-scripts" / "train_network.py"),
            f"--pretrained_model_name_or_path={cfg.base_model}",
            f"--train_data_dir={cfg.dataset_config}",   # dataset.toml path
            f"--output_dir={cfg.output_dir}",
            f"--output_name={cfg.output_name}",
            f"--network_module=networks.lora",
            f"--network_dim={cfg.rank}",
            f"--network_alpha=8",                        # alpha = rank / 2 is typical
            f"--max_train_steps={cfg.max_train_steps}",
            f"--learning_rate={cfg.learning_rate}",
            f"--lr_scheduler={cfg.lr_scheduler}",
            f"--lr_warmup_steps={cfg.lr_warmup_steps}",
            f"--scheduler_num_cycles={cfg.scheduler_num_cycles}",
            f"--batch_size={cfg.batch_size}",
            f"--resolution={cfg.resolution}",
            f"--crop_style={cfg.crop_style}",
            f"--enable_exif={str(cfg.enable_exif).lower()}",
            f"--num_workers={cfg.num_workers}",
            f"--persistent_data_loader={str(cfg.persistent_data_loader).lower()}",
            f"--mixed_precision={cfg.mixed_precision}",
            f"--gradient_accumulation_steps={cfg.gradient_accumulation_steps}",
            f"--gradient_checkpointing={str(cfg.gradient_checkpointing).lower()}",
        ]
        return cmd

    def _run_loop(self, run_id: str, cmd: list[str], env: dict) -> None:
        """Background thread: runs training and updates run status."""
        run = self._runs[run_id]
        run.status = "running"

        logger.info("Training run %s started: %s", run_id, " ".join(cmd[:4]))
        try:
            proc = subprocess.Popen(
                cmd,
                env={**os.environ, **env},
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            for line in proc.stdout:  # type: ignore[union-attr]
                line = line.strip()
                # Parse step info from kohya output
                if "step=" in line or "loss" in line.lower():
                    logger.debug("  [kohya] %s", line)
                # Update current step (kohya outputs "step: N" or "step=N")
                if "step" in line.lower():
                    try:
                        step = int("".join(filter(str.isdigit, line.split("step")[-1].split(",")[0])))
                        with self._lock:
                            if run_id in self._runs:
                                self._runs[run_id].current_step = step
                    except ValueError:
                        pass

            proc.wait()
            with self._lock:
                if run_id in self._runs:
                    if proc.returncode == 0:
                        self._runs[run_id].status = "completed"
                        self._runs[run_id].output_path = (
                            f"{self._runs[run_id].output_path or ''}"
                        )
                        logger.info("Training run %s completed successfully.", run_id)
                    else:
                        self._runs[run_id].status = "failed"
                        self._runs[run_id].error = f"exit code {proc.returncode}"
                        logger.error("Training run %s failed with exit code %s.", run_id, proc.returncode)
        except Exception as exc:
            with self._lock:
                if run_id in self._runs:
                    self._runs[run_id].status = "failed"
                    self._runs[run_id].error = str(exc)
            logger.error("Training run %s crashed: %s", run_id, exc)

    # ── Public API ────────────────────────────────────────────────────────────

    def start_training(
        self,
        dataset_config: str,
        output_name: str = "aeloria_lora",
        config: TrainingConfig | None = None,
    ) -> TrainingRun:
        """
        Launch a new LoRA training run in a background thread.

        Args:
            dataset_config: Path to a Kohya-format dataset.toml file
                            (points at your 15-30 Aeloria images).
            output_name:    Base name for the output .safetensors file.
            config:         Optional TrainingConfig override.

        Returns:
            TrainingRun object with a run_id you can poll with get_status().
        """
        cfg = (config or TrainingConfig()).from_settings(None)
        cfg.dataset_config = dataset_config
        cfg.output_name = output_name

        run_id = f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        run = TrainingRun(
            run_id=run_id,
            started_at=datetime.now(),
            max_steps=cfg.max_train_steps,
            output_path=str(Path(cfg.output_dir) / f"{cfg.output_name}.safetensors"),
        )

        with self._lock:
            self._runs[run_id] = run

        cmd = self._build_kohya_cmd(cfg)
        thread = threading.Thread(
            target=self._run_loop,
            args=(run_id, cmd, {}),
            daemon=True,
        )
        thread.start()

        logger.info("Training queued: run_id=%s steps=%d", run_id, cfg.max_train_steps)
        return run

    def get_status(self, run_id: str) -> TrainingRun | None:
        """Return the current TrainingRun status."""
        with self._lock:
            return self._runs.get(run_id)

    def wait_for_completion(
        self, run_id: str, poll_interval: float = 30.0, timeout: float = 7200.0
    ) -> TrainingRun:
        """
        Block until the training run completes or fails.

        Args:
            poll_interval: Seconds between status checks.
            timeout:       Max seconds to wait (raises TimeoutError).

        Returns:
            Final TrainingRun with status = 'completed' or 'failed'.
        """
        import time

        start = time.monotonic()
        while True:
            run = self.get_status(run_id)
            if run and run.status in ("completed", "failed"):
                return run
            if time.monotonic() - start > timeout:
                raise TimeoutError(f"Training run {run_id} timed out after {timeout}s")
            time.sleep(poll_interval)

    def list_runs(self) -> list[TrainingRun]:
        """Return all known training runs."""
        with self._lock:
            return list(self._runs.values())
