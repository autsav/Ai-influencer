"use client";

import { useState, useCallback } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api, type GenerateRequest, type JobResponse } from "@/lib/api";
import { GenerateForm } from "@/components/generation/GenerateForm";
import { JobCard } from "@/components/jobs/JobCard";
import { InfluencerCard } from "@/components/influencers/InfluencerCard";
import { HealthBadge } from "@/components/health/HealthBadge";
import { Sparkles, Loader2 } from "lucide-react";

interface ActiveJob {
  jobId: string;
  data: JobResponse;
}

export function Dashboard() {
  const [activeJobs, setActiveJobs] = useState<ActiveJob[]>([]);
  const queryClient = useQueryClient();

  const { data: health } = useQuery({
    queryKey: ["health"],
    queryFn: api.health,
    refetchInterval: 15000,
  });

  const { data: influencers } = useQuery({
    queryKey: ["influencers"],
    queryFn: api.listInfluencers,
  });

  const generateMutation = useMutation({
    mutationFn: (req: GenerateRequest) => api.generate(req),
    onSuccess: (job) => {
      setActiveJobs((prev) => [{ jobId: job.job_id, data: job }, ...prev]);
      // Poll for updates
      const interval = setInterval(async () => {
        try {
          const updated = await api.getJob(job.job_id);
          setActiveJobs((prev) =>
            prev.map((j) => (j.jobId === job.job_id ? { ...j, data: updated } : j))
          );
          if (updated.status === "COMPLETED" || updated.status === "FAILED") {
            clearInterval(interval);
          }
        } catch {
          clearInterval(interval);
        }
      }, 2000);
    },
  });

  return (
    <div className="min-h-screen">
      {/* Header */}
      <header className="border-b border-brand-700 bg-brand-800/50 backdrop-blur">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-4">
          <div className="flex items-center gap-2">
            <Sparkles className="h-5 w-5 text-indigo-400" />
            <span className="text-lg font-semibold">Aeloria Pipeline</span>
          </div>
          <HealthBadge health={health} />
        </div>
      </header>

      <main className="mx-auto max-w-7xl px-6 py-8">
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
          {/* Left: Generation Form */}
          <div className="lg:col-span-1">
            <GenerateForm
              onSubmit={(req) => generateMutation.mutate(req)}
              isLoading={generateMutation.isPending}
            />
          </div>

          {/* Right: Jobs + Influencer Profile */}
          <div className="space-y-6 lg:col-span-2">
            {/* Active Jobs */}
            <div>
              <h2 className="mb-3 text-sm font-medium text-brand-400">
                Recent Generations
              </h2>
              {activeJobs.length === 0 ? (
                <div className="card flex items-center justify-center py-12 text-brand-500">
                  <Loader2 className="mr-2 h-4 w-4" />
                  No generations yet. Submit the form to create one.
                </div>
              ) : (
                <div className="space-y-3">
                  {activeJobs.map((job) => (
                    <JobCard key={job.jobId} job={job.data} />
                  ))}
                </div>
              )}
            </div>

            {/* Influencer Profile */}
            {influencers && influencers.length > 0 && (
              <div>
                <h2 className="mb-3 text-sm font-medium text-brand-400">
                  Active Persona
                </h2>
                <InfluencerCard profile={influencers[0]} />
              </div>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}