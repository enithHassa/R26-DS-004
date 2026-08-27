import type { RouteObject } from "react-router-dom";
import { Navigate } from "react-router-dom";

import { UserDashboardPage } from "@/pages/user-view/pages/dashboard";
import { TAXWISE_BASE } from "@/pages/user-view/paths";

export { TAXWISE_BASE } from "@/pages/user-view/paths";

/**
 * TaxWise — taxpayer User View (code name for the new dark portal shell).
 *
 * Do not confuse with:
 * - Auditor Comp 3: `/profile`, `/hybrid`, `/impact`, `/compare` (AppShell)
 * - Comp 3 taxpayer hub / onboarding: `/portal/financial-intake`, `/portal/about-you`, `/portal/summary`
 */
/** Taxpayer User View routes — outside AppShell and auditor feature modules. */
export const userViewRoutes: RouteObject[] = [
  { path: TAXWISE_BASE, element: <UserDashboardPage /> },
  {
    path: `${TAXWISE_BASE}/profile`,
    // Temporary bridge: Comp 3 “My Profile” tab until a TaxWise profile page exists.
    element: <Navigate to="/portal/summary?tab=profile" replace />,
  },
  // Legacy /portal landing used before the TaxWise rename.
  { path: "/portal", element: <Navigate to={TAXWISE_BASE} replace /> },
  { path: "/portal/profile", element: <Navigate to={`${TAXWISE_BASE}/profile`} replace /> },
];
