/** Act-admin API auth: shared engine token + auditor name from global /login. */

import { useUserSessionStore } from "@/features/personalized-recommendation/store/user-session-store";

export const ACT_ADMIN_SESSION_KEY = "oe-engine.act-admin.v1";

/** Must match backend ``OE_ENGINE_ACT_ADMIN_TOKEN`` (repo-root ``.env``). */
export function getActAdminToken(): string {
  const fromEnv = (import.meta.env.VITE_OE_ENGINE_ACT_ADMIN_TOKEN as string | undefined)?.trim();
  return fromEnv || "local-oe-act-admin";
}

export type ActAdminSession = {
  token: string;
  reviewer: string;
};

/**
 * Builds the act-admin API session from the global auditor login.
 * Returns null when the user is not signed in as an auditor (layout redirects to /login).
 */
export function loadActAdminSession(): ActAdminSession | null {
  const user = useUserSessionStore.getState();
  if (!user.isAuthenticated || user.role !== "auditor") {
    return null;
  }
  const reviewer = (user.fullName || "Auditor").trim() || "Auditor";
  return { token: getActAdminToken(), reviewer };
}

/** @deprecated Kept for cleanup of older middle-login sessions. */
export function saveActAdminSession(session: ActAdminSession): void {
  const token = session.token.trim();
  const reviewer = session.reviewer.trim();
  if (!token || !reviewer) {
    throw new Error("Token and reviewer name are both required.");
  }
  sessionStorage.setItem(ACT_ADMIN_SESSION_KEY, JSON.stringify({ token, reviewer }));
}

export function clearActAdminSession(): void {
  sessionStorage.removeItem(ACT_ADMIN_SESSION_KEY);
}

export function actAdminHeaders(
  session: ActAdminSession | null,
  opts?: { includeReviewer?: boolean },
): Record<string, string> {
  if (!session) return {};
  const headers: Record<string, string> = {
    "X-Oe-Act-Admin-Token": session.token,
  };
  if (opts?.includeReviewer !== false) {
    headers["X-Oe-Act-Admin-Reviewer"] = session.reviewer;
  }
  return headers;
}
