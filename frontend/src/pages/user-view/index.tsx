import type { RouteObject } from "react-router-dom";
import { Navigate } from "react-router-dom";

import { UserAboutYouPage } from "@/pages/user-view/pages/about-you";
import { UserDashboardPage } from "@/pages/user-view/pages/dashboard";
import { UserFinancialImpactPage } from "@/pages/user-view/pages/financial-impact";
import { UserProfilePage } from "@/pages/user-view/pages/profile";
import { UserRecommendationsPage } from "@/pages/user-view/pages/recommendations";
import { PortalSummaryRedirect } from "@/pages/user-view/portal-summary-redirect";
import {
  TAXWISE_ABOUT_YOU,
  TAXWISE_BASE,
  TAXWISE_FINANCIAL_IMPACT,
  TAXWISE_PROFILE,
  TAXWISE_RECOMMENDATIONS,
} from "@/pages/user-view/paths";

export { TAXWISE_ABOUT_YOU, TAXWISE_BASE, TAXWISE_FINANCIAL_IMPACT, TAXWISE_PROFILE, TAXWISE_RECOMMENDATIONS } from "@/pages/user-view/paths";

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
  { path: TAXWISE_ABOUT_YOU, element: <UserAboutYouPage /> },
  { path: TAXWISE_PROFILE, element: <UserProfilePage /> },
  { path: TAXWISE_RECOMMENDATIONS, element: <UserRecommendationsPage /> },
  { path: TAXWISE_FINANCIAL_IMPACT, element: <UserFinancialImpactPage /> },
  // Legacy Comp 3 summary tabs → TaxWise pages
  {
    path: "/portal/summary",
    element: <PortalSummaryRedirect />,
  },
  { path: "/portal", element: <Navigate to={TAXWISE_BASE} replace /> },
  { path: "/portal/profile", element: <Navigate to={TAXWISE_PROFILE} replace /> },
];
