"use client";

import type { JobResponse } from "@/lib/api";
import { formatStatus, badgeClass } from "@/lib/utils";
import { CheckCircle2, XCircle, Loader2, Clock } from "lucide-react";

export function JobCard({ job }: { job: JobResponse }) {
  const icon = {
    PENDING: <Clock className="h-4 w-4 text-yellow-400" />,
    STARTED: <Loader2 className="h-4 w-4 animate-spin text-blue-400" />,
    COMPLETED: <CheckCircle2 className="h-4 w-4 text-green-400" />,
    FAILED: <XCircle className="h-4 w-4 text-red-400" />,
    RETRYING: <Loader2 className="h-4 w-4 animate-spin text-yellow-400" />,
  }[job.status] || <Clock className="h-4 w-4" />;

  return (
    <div className="card space-y-3">
      {/* Header: status + job ID */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          {icon}
          <span className={`badge ${badgeClass(job.status)}`}>
            {formatStatus(job.status)}
          </span>
        </div>
        <span className="text-xs text-brand-500 font-mono">
          {job.job_id.slice(0, 8)}
        </span>
      </div>

      {/* Result image */}
      {job.result_url && (
        <div className="overflow-hidden rounded-lg border border-brand-700">
          <img
            src={job.result_url}
            alt="Generated content"
            className="w-full object-contain"
          />
        </div>
      )}

      {/* Caption */}
      {job.caption && (
        <div className="rounded-lg bg-brand-900 p-3 text-sm text-brand-200">
          <p className="whitespace-pre-wrap">{job.caption}</p>
        </div>
      )}

      {/* Error */}
      {job.error && (
        <div className="rounded-lg bg-red-950/50 p-3 text-sm text-red-300">
          {job.error}
        </div>
      )}

      {/* Footer: cost */}
      {job.cost_usd !== null && job.cost_usd !== undefined && (
        <div className="text-xs text-brand-500">
          Cost: ${job.cost_usd.toFixed(4)}
        </div>
      )}
    </div>
  );
}