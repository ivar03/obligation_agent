"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { Bell, CheckCheck, AlertTriangle, Info, AlertCircle, ShieldAlert, Radio } from "lucide-react";

interface NotificationItem {
  id: string;
  workspace_id: string;
  category: string;
  severity: "INFO" | "WARNING" | "ERROR" | "CRITICAL";
  title: string;
  message: string;
  link?: string;
  is_read: boolean;
  created_at: string;
}

export const NotificationCenter: React.FC = () => {
  const [isOpen, setIsOpen] = useState(false);
  const [notifications, setNotifications] = useState<NotificationItem[]>([]);
  const [unreadCount, setUnreadCount] = useState<number>(0);
  const [loading, setLoading] = useState(false);

  const fetchNotifications = async () => {
    try {
      const res = await fetch("/api/notifications?limit=20");
      if (res.ok) {
        const data = await res.json();
        setNotifications(data.items || []);
        setUnreadCount(data.unread_count || 0);
      }
    } catch {
      // Ignored if offline
    }
  };

  useEffect(() => {
    fetchNotifications();
    const interval = setInterval(fetchNotifications, 15000);
    return () => clearInterval(interval);
  }, []);

  const markAllRead = async () => {
    try {
      setLoading(true);
      await fetch("/api/notifications/read-all", { method: "POST" });
      setNotifications((prev) => prev.map((n) => ({ ...n, is_read: true })));
      setUnreadCount(0);
    } catch {
      // Failed to mark
    } finally {
      setLoading(false);
    }
  };

  const markRead = async (id: string) => {
    try {
      await fetch(`/api/notifications/${id}/read`, { method: "PATCH" });
      setNotifications((prev) => prev.map((n) => (n.id === id ? { ...n, is_read: true } : n)));
      setUnreadCount((c) => Math.max(0, c - 1));
    } catch {
      // Failed to mark
    }
  };

  const getCategoryIcon = (category: string, severity: string) => {
    if (category === "SECURITY") return <ShieldAlert className="w-4 h-4 text-orange-600" />;
    if (category === "INTEGRATION") return <Radio className="w-4 h-4 text-orange-600" />;
    if (severity === "CRITICAL" || severity === "ERROR") return <AlertCircle className="w-4 h-4 text-rose-600" />;
    if (severity === "WARNING") return <AlertTriangle className="w-4 h-4 text-amber-600" />;
    return <Info className="w-4 h-4 text-orange-600" />;
  };

  return (
    <div className="relative">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="relative p-2 rounded-lg text-stone-600 hover:text-stone-900 hover:bg-stone-100 transition-colors"
        title="Notifications"
      >
        <Bell className="w-4 h-4" />
        {unreadCount > 0 && (
          <span className="absolute top-1.5 right-1.5 w-2 h-2 rounded-full bg-orange-600 ring-2 ring-white animate-pulse" />
        )}
      </button>

      {isOpen && (
        <>
          <div className="fixed inset-0 z-40" onClick={() => setIsOpen(false)} />
          <div className="absolute right-0 mt-2 w-80 sm:w-96 rounded-xl bg-white border border-stone-200 shadow-xl z-50 overflow-hidden animate-in fade-in slide-in-from-top-2 duration-150">
            <div className="px-4 py-3 border-b border-stone-200 flex items-center justify-between bg-stone-50/80">
              <div className="flex items-center gap-2">
                <span className="text-sm font-semibold text-stone-900">Notifications</span>
                {unreadCount > 0 && (
                  <span className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-orange-50 text-orange-700 border border-orange-200">
                    {unreadCount} new
                  </span>
                )}
              </div>
              {unreadCount > 0 && (
                <button
                  onClick={markAllRead}
                  disabled={loading}
                  className="inline-flex items-center gap-1 text-xs text-stone-500 hover:text-stone-800 transition-colors"
                >
                  <CheckCheck className="w-3.5 h-3.5" />
                  <span>Mark all read</span>
                </button>
              )}
            </div>

            <div className="max-h-[380px] overflow-y-auto divide-y divide-stone-100">
              {notifications.length === 0 ? (
                <div className="py-8 text-center text-xs text-stone-400">No notifications right now.</div>
              ) : (
                notifications.map((n) => (
                  <div
                    key={n.id}
                    onClick={() => markRead(n.id)}
                    className={`p-3 text-xs transition-colors hover:bg-stone-50 cursor-pointer ${
                      !n.is_read ? "bg-orange-50/20" : ""
                    }`}
                  >
                    <div className="flex items-start gap-2.5">
                      <div className="mt-0.5 shrink-0">{getCategoryIcon(n.category, n.severity)}</div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center justify-between gap-1 mb-0.5">
                          <span className={`font-semibold truncate ${!n.is_read ? "text-stone-900" : "text-stone-700"}`}>
                            {n.title}
                          </span>
                          {!n.is_read && <span className="w-1.5 h-1.5 rounded-full bg-orange-600 shrink-0" />}
                        </div>
                        <p className="text-stone-600 line-clamp-2 leading-relaxed">{n.message}</p>
                        {n.link && (
                          <Link
                            href={n.link}
                            onClick={() => setIsOpen(false)}
                            className="inline-block mt-1 text-orange-600 hover:text-orange-700 font-medium"
                          >
                            View details &rarr;
                          </Link>
                        )}
                      </div>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
};
