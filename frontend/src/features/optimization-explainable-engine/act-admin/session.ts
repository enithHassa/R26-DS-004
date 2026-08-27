/** Act-admin session: token (gate) + reviewer name (attribution). */

export const ACT_ADMIN_SESSION_KEY = "oe-engine.act-admin.v1";

export type ActAdminSession = {
  token: string;
  reviewer: string;
};

function readRaw(): ActAdminSession | null {
  try {
    const raw = sessionStorage.getItem(ACT_ADMIN_SESSION_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Partial<ActAdminSession>;
    const token = typeof parsed.token === "string" ? parsed.token.trim() : "";
    const reviewer = typeof parsed.reviewer === "string" ? parsed.reviewer.trim() : "";
    if (!token || !reviewer) return null;
    return { token, reviewer };
  } catch {
    return null;
  }
}

export function loadActAdminSession(): ActAdminSession | null {
  return readRaw();
}

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
