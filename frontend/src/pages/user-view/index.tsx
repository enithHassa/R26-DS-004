import type { RouteObject } from "react-router-dom";
import { Navigate } from "react-router-dom";

import { UserDashboardPage } from "@/pages/user-view/pages/dashboard";

/** Taxpayer User View routes — outside AppShell and auditor feature modules. */
export const userViewRoutes: RouteObject[] = [
  { path: "/portal", element: <UserDashboardPage /> },
  { path: "/portal/profile", element: <Navigate to="/portal/summary?tab=profile" replace /> },
];
