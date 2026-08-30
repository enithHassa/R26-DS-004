import type { RouteObject } from "react-router-dom";

import { DemoLandingPage } from "@/pages/demo/landing-page";

/** Standalone demo/marketing routes — outside AppShell and feature modules. */
export const demoRoutes: RouteObject[] = [
  { path: "/demo", element: <DemoLandingPage /> },
];
