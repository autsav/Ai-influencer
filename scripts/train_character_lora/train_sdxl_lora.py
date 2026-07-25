"""
SDXL LoRA Training on Aeloria reference images — M1 Pro MPS
============================================================
Key differences from SD1.5:
- Base: stabilityai/stable-diffusion-xl-base-1.0
- Resolution: 1024×1024 (vs 512×512)
- Dual text encoders (CLIP ViT-L/14 + OpenCLIP ViT-bigG)
- Two tokenizers
- Larger UNet (~2.6B params vs ~860M)
- VAE scaling factor: 0.1309 (vs 0.18215)
- Max token length: 77 per encoder (concatenated = 154 effective)
- LoRA targets both UNet attention + text encoder attention

Usage:
    python scripts/train_character_lora/train_sdxl_lora.py [--steps 1500] [--rank 32]
"""
from __future__ import annotations

import gc
import json
import math
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import torch
from PIL import Image
from torchvision import transforms as T
from tqdm import tqdm

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from diffusers import (
    StableDiffusionXLPipeline,
    DDPMScheduler,
)
from diffusers.training_utils import cast_training_params
from peft import LoraConfig, get_peft_model

# ── Config ────────────────────────────────────────────────────────────────────
@dataclass
class TrainConfig:
    base_model:           str = "stabilityai/stable-diffusion-xl-base-1.0"
    model_cache_dir:      str = str(PROJECT_ROOT / "models" / "sdxl-base")
    lora_rank:            int = 32
    lora_alpha:           int = 32
    lora_dropout:         float = 0.0
    num_steps:            int = 1500
    learning_rate:        float = 5e-5  # lower LR for SDXL stability
    lr_warmup_steps:      int = 100
    gradient_accumulation: int = 1
    batch_size:           int = 1
    resolution:           int = 768
    gradient_checkpointing: bool = True
    checkpoint_every:     int = 500
    output_dir:           str = str(PROJECT_ROOT / "models" / "aeloria_sdxl_lora")
    train_meta:           str = str(PROJECT_ROOT / "data" / "train_metadata.jsonl")
    val_meta:             str = str(PROJECT_ROOT / "data" / "train_metadata.jsonl")
    seed:                 int = 42


# ── Dataset ───────────────────────────────────────────────────────────────────
class SdxlLoraDataset:
    def __init__(self, metadata_path: str, split: str = "train", resolution: int = 1024):
        self.split = split
        self.resolution = resolution
        data_dir = PROJECT_ROOT / "data" / ("train" if split == "train" else "val")
        self.transform = T.Compose([
            T.Resize((resolution, resolution), interpolation=T.InterpolationMode.LANCZOS),
            T.ToTensor(),
        ])
        self.samples = []
        with open(metadata_path) as f:
            for line in f:
                rec = json.loads(line)
                if rec.get("split") == split:
                    self.samples.append({
                        "path": data_dir / rec["file_name"],
                        "caption": rec["caption"],
                    })
        if not self.samples:
            raise ValueError(f"No {split} samples in {metadata_path}")
        print(f"  [{split}] {len(self.samples)} samples loaded")

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, idx: int):
        rec = self.samples[idx]
        image = Image.open(rec["path"]).convert("RGB")
        image = self.transform(image)
        return {"pixel_values": image, "text": rec["caption"]}


# ── Training ──────────────────────────────────────────────────────────────────
def train_sdxl_lora(config: TrainConfig):
    device = "mps" if torch.backends.mps.is_available() else "cpu"
    print(f"\n{'='*60}")
    print(f"  AELORIA SDXL LoRA TRAINING — M1 Pro MPS")
    print(f"{'='*60}")
    print(f"  Device:         {device}")
    print(f"  Base model:     {config.base_model}")
    print(f"  LoRA rank:      {config.lora_rank}")
    print(f"  Steps:          {config.num_steps}")
    print(f"  Resolution:     {config.resolution}×{config.resolution}")
    print(f"  Learning rate:  {config.learning_rate}")
    print(f"  Output:         {config.output_dir}")
    print()

    torch.manual_seed(config.seed)
    os.makedirs(config.output_dir, exist_ok=True)

    # ── 1. Load SDXL pipeline ─────────────────────────────────────────────────
    print("[1/5] Loading SDXL pipeline (FP16)...")
    t0 = time.time()

    # Text encoders use fp16 variant, UNet/VAE use full precision.
    # Load without variant — diffusers finds both .safetensors files.
    # We cast everything to fp16 manually after load.
    pipe = StableDiffusionXLPipeline.from_pretrained(
        config.base_model,
        cache_dir=config.model_cache_dir,
        torch_dtype=torch.float16,
    )

    # Move components individually to manage memory
    unet = pipe.unet
    vae = pipe.vae
    text_enc1 = pipe.text_encoder
    text_enc2 = pipe.text_encoder_2
    tokenizer1 = pipe.tokenizer
    tokenizer2 = pipe.tokenizer_2
    scheduler = pipe.scheduler

    unet.to(device)
    vae.to(device)
    text_enc1.to(device)
    text_enc2.to(device)

    print(f"  Pipeline loaded in {time.time()-t0:.1f}s")

    # Freeze all
    unet.requires_grad_(False)
    vae.requires_grad_(False)
    text_enc1.requires_grad_(False)
    text_enc2.requires_grad_(False)

    # ── 2. Attach LoRA to UNet ─────────────────────────────────────────────────
    print(f"\n[2/5] Attaching LoRA (rank={config.lora_rank})...")

    target_modules = [
        "to_k", "to_q", "to_v", "to_out.0",
        "add_k_proj", "add_q_proj", "add_v_proj", "add_out.0",
        "proj_attn", "proj_out",  # Additional SDXL attention modules
    ]

    lora_config = LoraConfig(
        r=config.lora_rank,
        lora_alpha=config.lora_alpha,
        target_modules=target_modules,
        lora_dropout=config.lora_dropout,
    )

    unet = get_peft_model(unet, lora_config)
    unet.print_trainable_parameters()

    cast_training_params(unet, dtype=torch.float32)

    if config.gradient_checkpointing:
        unet.enable_gradient_checkpointing()

    # ── 3. Dataset ─────────────────────────────────────────────────────────────
    print("\n[3/5] Loading dataset...")
    train_ds = SdxlLoraDataset(config.train_meta, split="train", resolution=config.resolution)
    val_ds = SdxlLoraDataset(config.val_meta, split="val", resolution=config.resolution)

    # ── 4. Optimizer + Scheduler ───────────────────────────────────────────────
    print("\n[4/5] Setting up optimizer and scheduler...")

    trainable_params = [p for p in unet.parameters() if p.requires_grad]
    optimizer = torch.optim.AdamW(trainable_params, lr=config.learning_rate,
                                  betas=(0.9, 0.999), weight_decay=0.01)

    total_steps = config.num_steps
    warmup = config.lr_warmup_steps

    def lr_lambda(step):
        if step < warmup:
            return float(step) / max(1, warmup)
        progress = (step - warmup) / max(1, total_steps - warmup)
        return max(0.0, 0.5 * (1.0 + math.cos(math.pi * progress)))

    lr_scheduler = torch.optim.lr_scheduler.LambdaLR(optimizer, lr_lambda)

    noise_scheduler = DDPMScheduler.from_pretrained(
        config.base_model, subfolder="scheduler", cache_dir=config.model_cache_dir
    )

    # ── 5. Training loop ───────────────────────────────────────────────────────
    print(f"\n[5/5] Training ({total_steps} steps)...")
    print("-" * 60)

    global_step = 0
    log_every = 25
    max_length = 77

    unet.train()
    text_enc1.eval()
    text_enc2.eval()
    vae.eval()

    pbar = tqdm(total=total_steps, desc="Training", ncols=80)

    while global_step < total_steps:
        for batch in torch.utils.data.DataLoader(
                train_ds, batch_size=config.batch_size,
                shuffle=True, drop_last=False):

            # ── Encode images via VAE ──
            pixel_values = batch["pixel_values"].float()
            vae_dtype = next(vae.parameters()).dtype
            pixel_values = pixel_values.to(device=device, dtype=vae_dtype)

            with torch.no_grad():
                latents = vae.encode(pixel_values).latent_dist.sample()
                # SDXL VAE scaling factor is 0.1309 (different from SD1.5's 0.18215)
                latents = latents * 0.1309
                latents = latents.to(device)

            del pixel_values
            gc.collect()

            # ── Encode text via dual text encoders ──
            # Tokenizer 1 (CLIP ViT-L/14)
            text_inputs1 = tokenizer1(
                batch["text"],
                padding="max_length", max_length=max_length,
                truncation=True, return_tensors="pt",
            )
            input_ids1 = text_inputs1.input_ids.to(device)

            # Tokenizer 2 (OpenCLIP ViT-bigG)
            text_inputs2 = tokenizer2(
                batch["text"],
                padding="max_length", max_length=max_length,
                truncation=True, return_tensors="pt",
            )
            input_ids2 = text_inputs2.input_ids.to(device)

            with torch.no_grad():
                text_embeds1 = text_enc1(input_ids1)[0]  # (batch, 77, 768)
                text_embeds2 = text_enc2(input_ids2, output_hidden_states=True)
                # SDXL uses penultimate hidden state from text_encoder_2
                text_embeds2_hidden = text_embeds2.hidden_states[-2]  # (batch, 77, 1280)
                # Concatenate along feature dim: [768 + 1280] = 2048
                text_embeds = torch.cat([text_embeds1, text_embeds2_hidden], dim=-1)  # (batch, 77, 2048)

            # ── Add noise ──
            noise = torch.randn_like(latents)
            timesteps = torch.randint(
                0, noise_scheduler.config.num_train_timesteps,
                (latents.shape[0],), device=device
            )
            noisy_latents = noise_scheduler.add_noise(
                latents, noise, timesteps
            )

            # ── Forward + loss (use autocast for FP16 stability) ──
            with torch.autocast(device_type="mps", dtype=torch.float16):
                noise_pred = unet(
                    noisy_latents, timesteps, text_embeds,
                    added_cond_kwargs={
                        "text_embeds": text_embeds2.text_embeds if hasattr(text_embeds2, 'text_embeds') else text_embeds2[1],
                        "time_ids": torch.tensor([[config.resolution, config.resolution, 0, 0, config.resolution, config.resolution]],
                                                 dtype=torch.float16, device=device).expand(latents.shape[0], -1),
                    }
                ).sample

            loss = torch.nn.functional.mse_loss(
                noise_pred.float(), noise.float(), reduction="mean"
            )

            # ── Backward ──
            loss.backward()
            optimizer.step()
            lr_scheduler.step()
            optimizer.zero_grad()

            global_step += 1
            pbar.update(1)

            if global_step % log_every == 0:
                loss_val = loss.item()
                lr_val = optimizer.param_groups[0]["lr"]
                pbar.set_postfix_str(f"loss={loss_val:.4f} lr={lr_val:.2e}")

            if global_step % config.checkpoint_every == 0:
                save_path = Path(config.output_dir) / f"lora-step-{global_step}"
                save_path.mkdir(exist_ok=True)
                unet.save_attn_procs(save_path)
                print(f"\n  ✓ Checkpoint saved: {save_path}")

            if global_step >= total_steps:
                break

    pbar.close()

    # ── Save final ─────────────────────────────────────────────────────────────
    final_path = Path(config.output_dir) / "final"
    final_path.mkdir(exist_ok=True)
    unet.save_attn_procs(final_path)
    print(f"\n  ✓ Final SDXL LoRA saved: {final_path}")

    print(f"\n{'='*60}")
    print(f"  SDXL TRAINING COMPLETE — {global_step} steps")
    print(f"  LoRA: {config.output_dir}/final/")
    print(f"{'='*60}")

    return str(final_path)


# ── CLI ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--steps",  type=int, default=1500)
    parser.add_argument("--rank",   type=int, default=32)
    parser.add_argument("--lr",     type=float, default=1e-4)
    args = parser.parse_args()

    config = TrainConfig(
        num_steps=args.steps,
        lora_rank=args.rank,
        lora_alpha=args.rank,
        learning_rate=args.lr,
    )
    result = train_sdxl_lora(config)
    print(f"\nTrained SDXL LoRA: {result}")