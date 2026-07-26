import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatStatus(status: string): string {
  const map: Record<string, string> = {
    PENDING: "Pending",
    STARTED: "Generating",
    COMPLETED: "Completed",
    FAILED: "Failed",
    RETRYING: "Retrying",
  };
  return map[status] || status;
}

export function badgeClass(status: string): string {
  const map: Record<string, string> = {
    PENDING: "badge-pending",
    STARTED: "badge-started",
    COMPLETED: "badge-completed",
    FAILED: "badge-failed",
    RETRYING: "badge-pending",
  };
  return map[status] || "badge-pending";
}