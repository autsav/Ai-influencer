/**
 * Type definitions for the fal.ai image-generation router.
 *
 * The router is a pure payload builder: given a {@link PipelineInput} it returns
 * the target endpoint plus the request body for that workflow. It performs no
 * network I/O, so it carries no fal client dependency.
 */

/** Supported generation/edit workflows, each mapped to a fal endpoint. */
export enum WorkflowType {
  /** Custom identity LoRA + anti-plastic realism LoRA on `fal-ai/flux-lora`. */
  IDENTITY_LOCKED_LORA = "IDENTITY_LOCKED_LORA",
  /** Juggernaut-FLUX out-of-the-box photoreal, single identity LoRA. */
  OUT_OF_BOX_PHOTOREAL = "OUT_OF_BOX_PHOTOREAL",
  /** Instruction/in-painting edit of a source image via flux-kontext. */
  IN_PAINTING_EDIT = "IN_PAINTING_EDIT",
  /** Multi-reference blend via nano-banana-pro. */
  MULTI_REF_BLEND = "MULTI_REF_BLEND",
  /** High-resolution editorial stills via flux-pro ultra. */
  HIGH_RES_EDITORIAL = "HIGH_RES_EDITORIAL",
}

/**
 * Tunable, workflow-scoped parameters. Every field is optional so a workflow
 * only declares the knobs it actually uses; callers may override via
 * {@link PipelineInput.overrides}.
 */
export interface WorkflowParams {
  /** Identity LoRA weight (kept < 1.0 to avoid plastic over-fit). */
  identity_lora_scale?: number;
  /** Anti-plastic realism LoRA weight, stacked beneath identity. */
  realism_lora_scale?: number;
  /** CFG-style guidance. Lower = less artificial rim light / contrast. */
  guidance_scale?: number;
  /** Denoising steps. */
  steps?: number;
  /** Aspect ratio token, e.g. "9:16". */
  aspect_ratio?: string;
  /** flux-pro "raw" mode — less processed, more natural. */
  raw?: boolean;
}

/** A single fal LoRA reference. */
export interface LoraRef {
  path: string;
  scale: number;
}

/** Endpoint + baseline parameters for one workflow. */
export interface ModelConfig {
  endpoint: string;
  defaults: WorkflowParams;
}

/** A caller's request into the router. */
export interface PipelineInput {
  workflow: WorkflowType;
  /** Raw prompt; sanitized by the router before it reaches the body. */
  prompt: string;
  /** Identity LoRA URL (LoRA workflows). */
  identityLoraUrl?: string;
  /** Realism LoRA URL (IDENTITY_LOCKED_LORA only). */
  realismLoraUrl?: string;
  /** Source image for IN_PAINTING_EDIT (required for that workflow). */
  imageUrl?: string;
  /** Optional mask for IN_PAINTING_EDIT. */
  maskUrl?: string;
  /** Reference images for MULTI_REF_BLEND. */
  referenceImageUrls?: string[];
  /** Deterministic seed. */
  seed?: number;
  /** Per-request overrides of the workflow defaults. */
  overrides?: Partial<WorkflowParams>;
}

/** The router's output: endpoint id + ready-to-send request body. */
export interface FalPayload {
  endpoint: string;
  body: Record<string, unknown>;
}
