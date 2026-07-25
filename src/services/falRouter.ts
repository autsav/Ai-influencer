/**
 * Core routing & payload construction for the fal.ai image pipeline.
 *
 * `generatePayload` is the single entry point: it looks up the workflow's
 * endpoint + baseline params, sanitizes the prompt, applies per-request
 * overrides, and assembles the workflow-specific request body.
 */
import { FAL_MODELS } from "../config/falModels.js";
import type {
  FalPayload,
  LoraRef,
  ModelConfig,
  PipelineInput,
  WorkflowParams,
} from "../types/falPipeline.js";
import { WorkflowType } from "../types/falPipeline.js";

/** Camera-focused replacement injected when AI buzzwords are stripped. */
const CAMERA_TOKENS = "shot on 35mm lens, raw JPEG texture, natural daylight";

/**
 * Buzzword anti-patterns that push Flux toward a plastic/3D-render look.
 * Order matters: multi-word phrases are removed before their single-word
 * subsets (e.g. "cinematic lighting" before a bare "cinematic").
 */
const BANNED_PATTERNS: readonly RegExp[] = [
  /\bcinematic lighting\b/gi,
  /\bhyper[-\s]?realistic\b/gi,
  /\bultra[-\s]?realistic\b/gi,
  /\bphoto[-\s]?realistic\b/gi,
  /\bhigh[-\s]?end retouch\b/gi,
  /\bperfect skin\b/gi,
  /\bmasterpiece\b/gi,
  /\bcinematic\b/gi,
  /\b[48]k\b/gi,
];

/** Collapse the whitespace/comma debris left after removing tokens. */
function tidy(text: string): string {
  return text
    .replace(/\s+/g, " ")
    .replace(/\s*,(?:\s*,)+/g, ",") // ", ,"  -> ","
    .replace(/,\s*(?=,)/g, "")
    .replace(/^[\s,]+|[\s,]+$/g, "") // trim leading/trailing spaces+commas
    .trim();
}

/**
 * Strip AI "buzzwords" (photorealistic, 8k, cinematic lighting, …) and, when
 * any were present, append camera-focused realism tokens. Idempotent: a prompt
 * that already reads clean is returned tidied but otherwise unchanged, and the
 * camera tokens are added at most once.
 */
export function cleansePrompt(rawPrompt: string): string {
  let out = rawPrompt;
  let stripped = false;
  for (const pattern of BANNED_PATTERNS) {
    const next = out.replace(pattern, "");
    if (next !== out) {
      stripped = true;
      out = next;
    }
  }
  out = tidy(out);
  if (stripped && !/35mm/i.test(out)) {
    out = out.length > 0 ? `${out}, ${CAMERA_TOKENS}` : CAMERA_TOKENS;
  }
  return out;
}

/** Merge baseline defaults with caller overrides (overrides win). */
function resolveParams(
  defaults: WorkflowParams,
  overrides: Partial<WorkflowParams> | undefined,
): WorkflowParams {
  return { ...defaults, ...(overrides ?? {}) };
}

/** Map the shared, workflow-agnostic params onto fal body fields. */
function applyCommonParams(
  body: Record<string, unknown>,
  params: WorkflowParams,
  seed: number | undefined,
): void {
  if (params.guidance_scale !== undefined) body.guidance_scale = params.guidance_scale;
  if (params.steps !== undefined) body.num_inference_steps = params.steps;
  if (params.aspect_ratio !== undefined) body.aspect_ratio = params.aspect_ratio;
  if (params.raw !== undefined) body.raw = params.raw;
  if (seed !== undefined) body.seed = seed;
}

/**
 * Build the endpoint + request body for a pipeline request.
 * @throws if the workflow is unknown or a required input is missing.
 */
export function generatePayload(input: PipelineInput): FalPayload {
  // Annotated as possibly-undefined so the runtime guard (for JS callers passing
  // an invalid workflow) type-checks under strict settings.
  const config: ModelConfig | undefined = FAL_MODELS[input.workflow];
  if (config === undefined) {
    throw new Error(`Unknown workflow: ${String(input.workflow)}`);
  }

  const params = resolveParams(config.defaults, input.overrides);
  const body: Record<string, unknown> = { prompt: cleansePrompt(input.prompt) };
  applyCommonParams(body, params, input.seed);

  switch (input.workflow) {
    case WorkflowType.IDENTITY_LOCKED_LORA: {
      const loras: LoraRef[] = [];
      if (input.identityLoraUrl !== undefined) {
        loras.push({ path: input.identityLoraUrl, scale: params.identity_lora_scale ?? 0.78 });
      }
      if (input.realismLoraUrl !== undefined) {
        loras.push({ path: input.realismLoraUrl, scale: params.realism_lora_scale ?? 0.45 });
      }
      body.loras = loras;
      break;
    }
    case WorkflowType.OUT_OF_BOX_PHOTOREAL: {
      const loras: LoraRef[] = [];
      if (input.identityLoraUrl !== undefined) {
        loras.push({ path: input.identityLoraUrl, scale: params.identity_lora_scale ?? 0.74 });
      }
      body.loras = loras;
      break;
    }
    case WorkflowType.IN_PAINTING_EDIT: {
      if (input.imageUrl === undefined) {
        throw new Error("IN_PAINTING_EDIT requires `imageUrl`");
      }
      body.image_url = input.imageUrl;
      if (input.maskUrl !== undefined) body.mask_url = input.maskUrl;
      break;
    }
    case WorkflowType.MULTI_REF_BLEND: {
      body.image_urls = input.referenceImageUrls ?? [];
      break;
    }
    case WorkflowType.HIGH_RES_EDITORIAL: {
      // raw + aspect_ratio already applied via common params.
      break;
    }
    default: {
      // Exhaustiveness guard: a new WorkflowType without a case fails to compile.
      const _exhaustive: never = input.workflow;
      throw new Error(`Unhandled workflow: ${String(_exhaustive)}`);
    }
  }

  return { endpoint: config.endpoint, body };
}
