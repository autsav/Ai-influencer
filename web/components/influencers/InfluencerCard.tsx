"use client";

import type { InfluencerProfile } from "@/lib/api";
import { User } from "lucide-react";

export function InfluencerCard({ profile }: { profile: InfluencerProfile }) {
  return (
    <div className="card space-y-4">
      <div className="flex items-center gap-3">
        <div className="flex h-10 w-10 items-center justify-center rounded-full bg-indigo-600/20">
          <User className="h-5 w-5 text-indigo-400" />
        </div>
        <div>
          <h3 className="font-semibold">{profile.name}</h3>
          <p className="text-xs text-brand-500">v{profile.version} · {profile.niche}</p>
        </div>
      </div>

      <p className="text-sm text-brand-300">{profile.bio}</p>

      {/* Visual DNA */}
      <div className="space-y-1">
        <span className="label">Visual DNA</span>
        {Object.entries(profile.visual_dna).map(([key, val]) => (
          <div key={key} className="flex gap-2 text-xs">
            <span className="text-brand-500 capitalize">{key}:</span>
            <span className="text-brand-300">{val}</span>
          </div>
        ))}
      </div>

      {/* Content mix bar */}
      <div className="space-y-1">
        <span className="label">Content Mix</span>
        <div className="flex h-2 overflow-hidden rounded-full">
          {Object.entries(profile.content_mix).map(([key, val]) => {
            const colors: Record<string, string> = {
              photo: "bg-indigo-500",
              carousel: "bg-purple-500",
              video: "bg-pink-500",
              stories: "bg-amber-500",
            };
            return (
              <div
                key={key}
                className={colors[key] || "bg-brand-600"}
                style={{ width: `${val * 100}%` }}
              />
            );
          })}
        </div>
      </div>
    </div>
  );
}