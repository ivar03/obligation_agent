import React from "react";
import { ObligationStatus } from "@/lib/types/obligation";

interface StatusBadgeProps {
  status: ObligationStatus;
  size?: "sm" | "md";
}

export const StatusBadge: React.FC<StatusBadgeProps> = ({ status, size = "md" }) => {
  const styles: Record<ObligationStatus, { bg: string; text: string; border: string; dot: string; label: string }> = {
    CONFIRMED: {
      bg: "bg-blue-500/10",
      text: "text-blue-500",
      border: "border-blue-500/20",
      dot: "bg-blue-500",
      label: "Confirmed",
    },
    IN_PROGRESS: {
      bg: "bg-amber-500/10",
      text: "text-amber-400",
      border: "border-amber-500/20",
      dot: "bg-amber-400 animate-pulse",
      label: "In Progress",
    },
    COMPLETED: {
      bg: "bg-emerald-500/10",
      text: "text-emerald-400",
      border: "border-emerald-500/20",
      dot: "bg-emerald-400",
      label: "Completed",
    },
    OVERDUE: {
      bg: "bg-rose-500/15",
      text: "text-rose-400",
      border: "border-rose-500/30",
      dot: "bg-rose-500",
      label: "Overdue",
    },
    BLOCKED: {
      bg: "bg-red-500/10",
      text: "text-red-400",
      border: "border-red-500/20",
      dot: "bg-red-400",
      label: "Blocked",
    },
    DETECTED: {
      bg: "bg-purple-500/10",
      text: "text-purple-400",
      border: "border-purple-500/20",
      dot: "bg-purple-400",
      label: "Detected",
    },
    CANCELLED: {
      bg: "bg-stone-500/10",
      text: "text-stone-600",
      border: "border-stone-500/20",
      dot: "bg-stone-500",
      label: "Cancelled",
    },
  };

  const current = styles[status] || styles.CONFIRMED;
  const sizeClasses = size === "sm" ? "px-2 py-0.5 text-xs" : "px-2.5 py-1 text-xs font-medium";

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border ${current.bg} ${current.text} ${current.border} ${sizeClasses}`}
    >
      <span className={`h-1.5 w-1.5 rounded-full ${current.dot}`} />
      {current.label}
    </span>
  );
};
