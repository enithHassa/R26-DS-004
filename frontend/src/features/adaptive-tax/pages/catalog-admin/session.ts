/**
 * Catalog-admin session: token (gate) + reviewer name (attribution).
 * sessionStorage only — never localStorage.
 */

export const CATALOG_ADMIN_SESSION_KEY = "adaptive-tax.catalog-admin.v1";

export type CatalogAdminSession = {
  token: string;
  reviewer: string;
};

function readRaw(): CatalogAdminSession | null {
  try {
    const raw = sessionStorage.getItem(CATALOG_ADMIN_SESSION_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Partial<CatalogAdminSession>;
    const token = typeof parsed.token === "string" ? parsed.token.trim() : "";
    const reviewer =
      typeof parsed.reviewer === "string" ? parsed.reviewer.trim() : "";
    if (!token || !reviewer) return null;
    return { token, reviewer };
  } catch {
    return null;
  }
}

export function loadCatalogAdminSession(): CatalogAdminSession | null {
  return readRaw();
}

export function saveCatalogAdminSession(session: CatalogAdminSession): void {
  const token = session.token.trim();
  const reviewer = session.reviewer.trim();
  if (!token || !reviewer) {
    throw new Error("Token and reviewer name are both required.");
  }
  sessionStorage.setItem(
    CATALOG_ADMIN_SESSION_KEY,
    JSON.stringify({ token, reviewer }),
  );
}

export function clearCatalogAdminSession(): void {
  sessionStorage.removeItem(CATALOG_ADMIN_SESSION_KEY);
}

export function catalogAdminHeaders(
  session: CatalogAdminSession | null,
  opts?: { includeReviewer?: boolean },
): Record<string, string> {
  if (!session) return {};
  const headers: Record<string, string> = {
    "X-Catalog-Admin-Token": session.token,
  };
  if (opts?.includeReviewer !== false) {
    headers["X-Catalog-Admin-Reviewer"] = session.reviewer;
  }
  return headers;
}
