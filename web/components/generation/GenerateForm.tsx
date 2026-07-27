"use client";

import { useState } from "react";
import type { GenerateRequest } from "@/lib/api";
import { Loader2, ImageIcon } from "lucide-react";

const PILLARS = [
  "ai_workflows",
  "ai_tools",
  "case_studies",
  "founder_lifestyle",
  "future_of_business",
];

const STYLES = ["", "candid", "film_editorial", "flash_candid", "paparazzi"];

const CTAS = ["none", "save", "share", "comment"];

const SCENE_PRESETS = [
  "minimal home office, clean white desk, MacBook showing AI workflow, warm desk lamp, morning light",
  "modern indie cafe, working on laptop at corner table, flat white, natural light through window",
  "modern office whiteboard with workflow diagrams, marker in hand, sticky notes",
  "city street at golden hour, walking with coffee, earbuds in, modern architecture",
  "modern coworking space, bright desk, laptop showing analytics dashboard",
];

export function GenerateForm({
  onSubmit,
  isLoading,
}: {
  onSubmit: (req: GenerateRequest) => void;
  isLoading: boolean;
}) {
  const [promptSeed, setPromptSeed] = useState(SCENE_PRESETS[0]);
  const [pillar, setPillar] = useState("ai_workflows");
  const [wardrobe, setWardrobe] = useState("");
  const [mood, setMood] = useState("");
  const [styleOverride, setStyleOverride] = useState("");
  const [ctaKind, setCtaKind] = useState("save");
  const [generateCaption, setGenerateCaption] = useState(true);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSubmit({
      prompt_seed: promptSeed,
      pillar,
      wardrobe: wardrobe || undefined,
      mood: mood || undefined,
      style_override: styleOverride || undefined,
      content_type: "image",
      generate_caption: generateCaption,
      cta_kind: ctaKind,
      aspect_ratio: "4:5",
    });
  };

  return (
    <div className="card">
      <div className="mb-4 flex items-center gap-2">
        <ImageIcon className="h-4 w-4 text-indigo-400" />
        <h2 className="text-sm font-semibold">Generate Content</h2>
      </div>

      <form onSubmit={handleSubmit} className="space-y-4">
        {/* Scene preset chips */}
        <div>
          <label className="label">Scene Preset</label>
          <div className="flex flex-wrap gap-2">
            {SCENE_PRESETS.map((s, i) => (
              <button
                key={i}
                type="button"
                onClick={() => setPromptSeed(s)}
                className={`rounded-md px-2.5 py-1 text-xs transition ${
                  promptSeed === s
                    ? "bg-indigo-600 text-white"
                    : "bg-brand-700 text-brand-300 hover:bg-brand-600"
                }`}
              >
                {s.split(",")[0]}
              </button>
            ))}
          </div>
        </div>

        {/* Custom prompt */}
        <div>
          <label className="label">Scene Description</label>
          <textarea
            value={promptSeed}
            onChange={(e) => setPromptSeed(e.target.value)}
            className="input h-20 resize-none"
            placeholder="Describe the scene..."
          />
        </div>

        {/* Pillar */}
        <div>
          <label className="label">Content Pillar</label>
          <select
            value={pillar}
            onChange={(e) => setPillar(e.target.value)}
            className="input"
          >
            {PILLARS.map((p) => (
              <option key={p} value={p}>
                {p.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())}
              </option>
            ))}
          </select>
        </div>

        {/* Two columns: wardrobe + mood */}
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="label">Wardrobe (optional)</label>
            <input
              value={wardrobe}
              onChange={(e) => setWardrobe(e.target.value)}
              className="input"
              placeholder="e.g. navy overshirt"
            />
          </div>
          <div>
            <label className="label">Mood (optional)</label>
            <input
              value={mood}
              onChange={(e) => setMood(e.target.value)}
              className="input"
              placeholder="e.g. focused"
            />
          </div>
        </div>

        {/* Style + CTA */}
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="label">Style</label>
            <select
              value={styleOverride}
              onChange={(e) => setStyleOverride(e.target.value)}
              className="input"
            >
              {STYLES.map((s) => (
                <option key={s} value={s}>
                  {s || "auto"}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="label">CTA</label>
            <select
              value={ctaKind}
              onChange={(e) => setCtaKind(e.target.value)}
              className="input"
            >
              {CTAS.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
          </div>
        </div>

        {/* Caption toggle */}
        <label className="flex items-center gap-2 text-sm text-brand-300">
          <input
            type="checkbox"
            checked={generateCaption}
            onChange={(e) => setGenerateCaption(e.target.checked)}
            className="rounded border-brand-600 bg-brand-900"
          />
          Generate caption via MiniMax
        </label>

        {/* Submit */}
        <button type="submit" disabled={isLoading} className="btn-primary w-full">
          {isLoading ? (
            <span className="flex items-center justify-center gap-2">
              <Loader2 className="h-4 w-4 animate-spin" /> Enqueuing...
            </span>
          ) : (
            "Generate"
          )}
        </button>
      </form>
    </div>
  );
}