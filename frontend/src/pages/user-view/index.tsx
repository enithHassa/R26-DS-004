import type { RouteObject } from "react-router-dom";

import { UserDashboardPage } from "@/pages/user-view/pages/dashboard";

/** Taxpayer User View routes — outside AppShell and auditor feature modules. */
export const userViewRoutes: RouteObject[] = [
  { path: "/portal", element: <UserDashboardPage /> },
];
