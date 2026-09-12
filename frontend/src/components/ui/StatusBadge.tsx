import React from "react";
import { ObligationStatus } from "@/lib/types/obligation";

interface StatusBadgeProps {
  status: ObligationStatus;
  size?: "sm" | "md";
}

export const StatusBadge: React.FC<StatusBadgeProps> = ({ status, size = "md" }) => {
  const styles: Record<ObligationStatus, { bg: string; text: string; border: string; dot: string; label: string }> = {
    CONFIRMED: {
      bg: "bg-stone-100",
      text: "text-stone-700",
      border: "border-stone-200",
      dot: "bg-stone-500",
      label: "Confirmed",
    },
    IN_PROGRESS: {
      bg: "bg-amber-50",
      text: "text-amber-800",
      border: "border-amber-200",
      dot: "bg-amber-500 animate-pulse",
      label: "In Progress",
    },
    COMPLETED: {
      bg: "bg-emerald-50",
      text: "text-emerald-800",
      border: "border-emerald-200",
      dot: "bg-emerald-500",
      label: "Completed",
    },
    OVERDUE: {
      bg: "bg-rose-50",
      text: "text-rose-800",
      border: "border-rose-200",
      dot: "bg-rose-500",
      label: "Overdue",
    },
    BLOCKED: {
      bg: "bg-red-50",
      text: "text-red-800",
      border: "border-red-200",
      dot: "bg-red-500",
      label: "Blocked",
    },
    DETECTED: {
      bg: "bg-orange-50",
      text: "text-orange-800",
      border: "border-orange-200",
      dot: "bg-orange-500",
      label: "Detected",
    },
    CANCELLED: {
      bg: "bg-stone-100",
      text: "text-stone-600",
      border: "border-stone-200",
      dot: "bg-stone-400",
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
