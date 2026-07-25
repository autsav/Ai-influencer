/**
 * Model endpoints and baseline parameter mappings, keyed by workflow.
 *
 * These baselines mirror the tuned values used by the Python pipeline
 * (`aeloria/config.py`): identity LoRA 0.78, realism 0.45, guidance 1.9.
 * A `Record<WorkflowType, ModelConfig>` guarantees every workflow is mapped —
 * adding a new enum member is a compile error until it is configured here.
 */
import type { ModelConfig } from "../types/falPipeline.js";
import { WorkflowType } from "../types/falPipeline.js";

export const FAL_MODELS: Record<WorkflowType, ModelConfig> = {
  [WorkflowType.IDENTITY_LOCKED_LORA]: {
    endpoint: "fal-ai/flux-lora",
    defaults: {
      identity_lora_scale: 0.78,
      realism_lora_scale: 0.45,
      guidance_scale: 1.9,
      steps: 30,
    },
  },
  [WorkflowType.OUT_OF_BOX_PHOTOREAL]: {
    endpoint: "rundiffusion-fal/juggernaut-flux-lora",
    defaults: {
      identity_lora_scale: 0.74,
      guidance_scale: 1.9,
      steps: 30,
    },
  },
  [WorkflowType.IN_PAINTING_EDIT]: {
    endpoint: "fal-ai/flux-kontext/dev",
    defaults: {
      guidance_scale: 3.5,
      steps: 28,
    },
  },
  [WorkflowType.MULTI_REF_BLEND]: {
    endpoint: "fal-ai/nano-banana-pro",
    defaults: {
      aspect_ratio: "9:16",
    },
  },
  [WorkflowType.HIGH_RES_EDITORIAL]: {
    endpoint: "fal-ai/flux-pro/v1.1-ultra",
    defaults: {
      raw: true,
      aspect_ratio: "9:16",
    },
  },
};
