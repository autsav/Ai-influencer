import { describe, expect, it } from "vitest";

import { FAL_MODELS } from "../src/config/falModels.js";
import { cleansePrompt, generatePayload } from "../src/services/falRouter.js";
import { WorkflowType } from "../src/types/falPipeline.js";

const IDENTITY = "https://cdn/aeloria-identity.safetensors";
const REALISM = "https://huggingface.co/XLabs-AI/flux-RealismLora/resolve/main/lora.safetensors";

describe("cleansePrompt", () => {
  it("strips buzzwords and appends camera tokens", () => {
    const out = cleansePrompt("aeloria on a porch, photorealistic, 8k, cinematic lighting, masterpiece");
    expect(out).not.toMatch(/photorealistic|8k|cinematic|masterpiece/i);
    expect(out).toContain("shot on 35mm lens");
    expect(out).toContain("raw JPEG texture");
    expect(out.startsWith("aeloria on a porch")).toBe(true);
  });

  it("removes 'cinematic lighting' as a phrase without leaving 'lighting' debris around commas", () => {
    const out = cleansePrompt("soft window light, cinematic lighting, warm tones");
    expect(out).not.toMatch(/cinematic/i);
    expect(out).not.toMatch(/,\s*,/);
    expect(out).toContain("soft window light");
    expect(out).toContain("warm tones");
  });

  it("leaves a clean prompt unchanged (no camera tokens injected)", () => {
    const clean = "aeloria mid-laugh at a cafe, soft daylight";
    expect(cleansePrompt(clean)).toBe(clean);
  });

  it("is idempotent — does not double-append camera tokens", () => {
    const once = cleansePrompt("a face, hyperrealistic");
    const twice = cleansePrompt(once);
    expect(twice).toBe(once);
    expect((once.match(/35mm/g) ?? []).length).toBe(1);
  });
});

describe("generatePayload — IDENTITY_LOCKED_LORA", () => {
  it("targets flux-lora with identity + realism LoRAs and tuned params", () => {
    const { endpoint, body } = generatePayload({
      workflow: WorkflowType.IDENTITY_LOCKED_LORA,
      prompt: "aeloria on porch",
      identityLoraUrl: IDENTITY,
      realismLoraUrl: REALISM,
      seed: 42,
    });
    expect(endpoint).toBe("fal-ai/flux-lora");
    expect(body.guidance_scale).toBe(1.9);
    expect(body.num_inference_steps).toBe(30);
    expect(body.seed).toBe(42);
    expect(body.loras).toEqual([
      { path: IDENTITY, scale: 0.78 },
      { path: REALISM, scale: 0.45 },
    ]);
    expect(body.prompt).toBe("aeloria on porch");
  });

  it("honors per-request overrides", () => {
    const { body } = generatePayload({
      workflow: WorkflowType.IDENTITY_LOCKED_LORA,
      prompt: "x",
      identityLoraUrl: IDENTITY,
      overrides: { identity_lora_scale: 0.85, guidance_scale: 2.2 },
    });
    expect(body.guidance_scale).toBe(2.2);
    expect(body.loras).toEqual([{ path: IDENTITY, scale: 0.85 }]);
  });
});

describe("generatePayload — OUT_OF_BOX_PHOTOREAL", () => {
  it("targets juggernaut with a single identity LoRA at 0.74", () => {
    const { endpoint, body } = generatePayload({
      workflow: WorkflowType.OUT_OF_BOX_PHOTOREAL,
      prompt: "aeloria",
      identityLoraUrl: IDENTITY,
    });
    expect(endpoint).toBe("rundiffusion-fal/juggernaut-flux-lora");
    expect(body.guidance_scale).toBe(1.9);
    expect(body.num_inference_steps).toBe(30);
    expect(body.loras).toEqual([{ path: IDENTITY, scale: 0.74 }]);
    expect(body).not.toHaveProperty("realism_lora_scale");
  });
});

describe("generatePayload — IN_PAINTING_EDIT", () => {
  it("targets flux-kontext with image_url and edit-tuned params", () => {
    const { endpoint, body } = generatePayload({
      workflow: WorkflowType.IN_PAINTING_EDIT,
      prompt: "swap the jacket for a trench",
      imageUrl: "https://cdn/base.png",
      maskUrl: "https://cdn/mask.png",
    });
    expect(endpoint).toBe("fal-ai/flux-kontext/dev");
    expect(body.guidance_scale).toBe(3.5);
    expect(body.num_inference_steps).toBe(28);
    expect(body.image_url).toBe("https://cdn/base.png");
    expect(body.mask_url).toBe("https://cdn/mask.png");
  });

  it("throws when imageUrl is missing", () => {
    expect(() =>
      generatePayload({ workflow: WorkflowType.IN_PAINTING_EDIT, prompt: "edit" }),
    ).toThrow(/imageUrl/);
  });
});

describe("generatePayload — MULTI_REF_BLEND", () => {
  it("targets nano-banana-pro with image_urls and default aspect ratio", () => {
    const { endpoint, body } = generatePayload({
      workflow: WorkflowType.MULTI_REF_BLEND,
      prompt: "blend these",
      referenceImageUrls: ["https://cdn/a.png", "https://cdn/b.png"],
    });
    expect(endpoint).toBe("fal-ai/nano-banana-pro");
    expect(body.aspect_ratio).toBe("9:16");
    expect(body.image_urls).toEqual(["https://cdn/a.png", "https://cdn/b.png"]);
  });

  it("defaults image_urls to an empty array", () => {
    const { body } = generatePayload({ workflow: WorkflowType.MULTI_REF_BLEND, prompt: "x" });
    expect(body.image_urls).toEqual([]);
  });
});

describe("generatePayload — HIGH_RES_EDITORIAL", () => {
  it("targets flux-pro ultra with raw mode and aspect ratio", () => {
    const { endpoint, body } = generatePayload({
      workflow: WorkflowType.HIGH_RES_EDITORIAL,
      prompt: "editorial portrait",
    });
    expect(endpoint).toBe("fal-ai/flux-pro/v1.1-ultra");
    expect(body.raw).toBe(true);
    expect(body.aspect_ratio).toBe("9:16");
    expect(body).not.toHaveProperty("loras");
  });
});

describe("payload prompt sanitization is always applied", () => {
  it("cleanses the prompt for every workflow", () => {
    for (const workflow of Object.values(WorkflowType)) {
      const { body } = generatePayload({
        workflow,
        prompt: "aeloria, 8k, cinematic lighting",
        identityLoraUrl: IDENTITY,
        imageUrl: "https://cdn/base.png",
      });
      expect(body.prompt).not.toMatch(/8k|cinematic/i);
      expect(body.prompt).toContain("shot on 35mm lens");
    }
  });
});

describe("FAL_MODELS config", () => {
  it("maps every workflow to a non-empty endpoint", () => {
    for (const workflow of Object.values(WorkflowType)) {
      expect(FAL_MODELS[workflow].endpoint.length).toBeGreaterThan(0);
    }
  });
});
