"""Manual smoke test: generate one Aeloria image end-to-end and upload to R2.

Usage: python scripts/smoke_generate.py
Requires: AELORIA_LORA_URL set in .env (run train_lora.py first).
"""
from datetime import datetime, timezone

from aeloria.generation.fal_images import generate_image
from aeloria.storage.r2 import R2


def main():
    r = generate_image(
        "aeloria, a young woman with auburn hair in a loose bun, green eyes, "
        "freckles, sitting on wooden porch steps of a forest cabin holding a "
        "mug of tea, golden hour sunlight through trees, photorealistic, "
        "candid smartphone photo"
    )
    key = f"smoke/{datetime.now(timezone.utc):%Y%m%dT%H%M%S}.png"
    url = R2().upload(r.image_bytes, key, "image/png")
    print(f"cost: ${r.cost_usd}\nurl: {url}")


if __name__ == "__main__":
    main()
