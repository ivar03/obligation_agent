"use client";

import React, { createContext, useContext, useState, useEffect, useCallback } from "react";
import {
  User,
  Workspace,
  WorkspaceRole,
  LoginRequest,
  RegisterRequest,
} from "../lib/types/obligation";
import { authApi, workspacesApi, setApiAuth, getActiveWorkspaceId } from "../lib/api/obligations";

const ROLE_RANKS: Record<WorkspaceRole, number> = {
  VIEWER: 10,
  MEMBER: 20,
  ADMIN: 30,
  OWNER: 40,
};

interface AuthContextType {
  user: User | null;
  workspaces: Workspace[];
  activeWorkspace: Workspace | null;
  activeRole: WorkspaceRole;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (credentials: LoginRequest) => Promise<void>;
  register: (data: RegisterRequest) => Promise<void>;
  logout: () => Promise<void>;
  switchWorkspace: (workspaceId: string) => void;
  refreshWorkspaces: () => Promise<void>;
  hasRole: (minRole: WorkspaceRole) => boolean;
  canMutate: () => boolean;
  canAdmin: () => boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [activeWorkspace, setActiveWorkspace] = useState<Workspace | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // Initialize session on mount
  const initSession = useCallback(async () => {
    try {
      setIsLoading(true);
      const res = await authApi.getMe();
      if (res && res.user) {
        setUser(res.user);
        setWorkspaces(res.workspaces || []);

        const savedWsId = getActiveWorkspaceId() || res.active_workspace_id;
        const matchedWs = (res.workspaces || []).find((w) => w.id === savedWsId) || res.workspaces?.[0] || null;
        
        setActiveWorkspace(matchedWs);
        setApiAuth(res.token || localStorage.getItem("obligation_auth_token"), matchedWs?.id || null);
      }
    } catch {
      // In dev mode without auth, setup default fallback
      setUser({
        id: "usr-default",
        email: "demo@obligation.local",
        display_name: "Demo Operator",
        is_active: true,
        created_at: new Date().toISOString(),
      });
      const defaultWs: Workspace = {
        id: "ws-default",
        name: "Default Workspace",
        slug: "default",
        role: "OWNER",
        created_at: new Date().toISOString(),
      };
      setWorkspaces([defaultWs]);
      setActiveWorkspace(defaultWs);
      setApiAuth(null, "ws-default");
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    initSession();
  }, [initSession]);

  const login = async (credentials: LoginRequest) => {
    setIsLoading(true);
    try {
      const res = await authApi.login(credentials);
      setUser(res.user);
      setWorkspaces(res.workspaces || []);

      const matchedWs = (res.workspaces || []).find((w) => w.id === res.active_workspace_id) || res.workspaces?.[0] || null;
      setActiveWorkspace(matchedWs);
      setApiAuth(res.token || null, matchedWs?.id || null);
    } finally {
      setIsLoading(false);
    }
  };

  const register = async (data: RegisterRequest) => {
    setIsLoading(true);
    try {
      const res = await authApi.register(data);
      setUser(res.user);
      setWorkspaces(res.workspaces || []);

      const matchedWs = (res.workspaces || []).find((w) => w.id === res.active_workspace_id) || res.workspaces?.[0] || null;
      setActiveWorkspace(matchedWs);
      setApiAuth(res.token || null, matchedWs?.id || null);
    } finally {
      setIsLoading(false);
    }
  };

  const logout = async () => {
    try {
      await authApi.logout();
    } catch {
      // Ignore network errors on logout
    }
    setUser(null);
    setWorkspaces([]);
    setActiveWorkspace(null);
    setApiAuth(null, null);
  };

  const switchWorkspace = (workspaceId: string) => {
    const ws = workspaces.find((w) => w.id === workspaceId);
    if (ws) {
      setActiveWorkspace(ws);
      setApiAuth(localStorage.getItem("obligation_auth_token"), ws.id);
      // Reload current route state to refresh data for new workspace
      if (typeof window !== "undefined") {
        window.location.reload();
      }
    }
  };

  const refreshWorkspaces = async () => {
    try {
      const wsList = await workspacesApi.list();
      setWorkspaces(wsList);
      if (activeWorkspace) {
        const updatedActive = wsList.find((w) => w.id === activeWorkspace.id);
        if (updatedActive) setActiveWorkspace(updatedActive);
      }
    } catch (e) {
      console.error("Failed to refresh workspaces", e);
    }
  };

  const activeRole: WorkspaceRole = (activeWorkspace?.role as WorkspaceRole) || "MEMBER";

  const hasRole = (minRole: WorkspaceRole): boolean => {
    const currentRank = ROLE_RANKS[activeRole] || 20;
    const requiredRank = ROLE_RANKS[minRole] || 20;
    return currentRank >= requiredRank;
  };

  const canMutate = (): boolean => hasRole("MEMBER");
  const canAdmin = (): boolean => hasRole("ADMIN");

  return (
    <AuthContext.Provider
      value={{
        user,
        workspaces,
        activeWorkspace,
        activeRole,
        isAuthenticated: !!user,
        isLoading,
        login,
        register,
        logout,
        switchWorkspace,
        refreshWorkspaces,
        hasRole,
        canMutate,
        canAdmin,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
