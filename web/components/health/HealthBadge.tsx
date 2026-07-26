"use client";

import type { HealthResponse } from "@/lib/api";
import { cn } from "@/lib/utils";

export function HealthBadge({ health }: { health?: HealthResponse }) {
  if (!health) {
    return (
      <div className="flex items-center gap-2 text-xs text-brand-500">
        <div className="h-2 w-2 rounded-full bg-brand-600" />
        Connecting...
      </div>
    );
  }

  const isHealthy = health.status === "ok";
  const redisUp = health.redis_connected;

  return (
    <div className="flex items-center gap-3 text-xs">
      <div className="flex items-center gap-1.5">
        <div className={cn("h-2 w-2 rounded-full", isHealthy ? "bg-green-500" : "bg-yellow-500")} />
        <span className="text-brand-400">{health.status}</span>
      </div>
      <div className="flex items-center gap-1.5">
        <div className={cn("h-2 w-2 rounded-full", redisUp ? "bg-green-500" : "bg-red-500")} />
        <span className="text-brand-400">Redis</span>
      </div>
      <div className="flex items-center gap-1.5">
        <div className={cn("h-2 w-2 rounded-full", health.celery_running ? "bg-green-500" : "bg-red-500")} />
        <span className="text-brand-400">Celery</span>
      </div>
    </div>
  );
}