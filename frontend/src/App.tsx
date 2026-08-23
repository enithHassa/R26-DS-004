import { Navigate, useRoutes, type RouteObject } from "react-router-dom";

import { AppShell } from "@/components/layout/app-shell";
import { features } from "@/features";
import { AboutYouPage } from "@/features/personalized-recommendation/pages/about-you";
import { UserLoginPage } from "@/features/personalized-recommendation/pages/user-login";
import { UserPortalPage } from "@/features/personalized-recommendation/pages/user-portal";
import { demoRoutes } from "@/pages/demo";
import { userViewRoutes } from "@/pages/user-view";

function buildOutletChildren(): RouteObject[] {
  return features.flatMap((feature) => {
    if (!feature.layout) return feature.routes;
    const Layout = feature.layout;
    return [{ element: <Layout />, children: feature.routes }];
  });
}

export default function App() {
  const routes: RouteObject[] = [
    {
      path: "/",
      element: <AppShell />,
      children: buildOutletChildren(),
    },
    { path: "/tax-optimization", element: <Navigate to="/tax/compliance" replace /> },
    { path: "/tax-optimization/compliance", element: <Navigate to="/tax/compliance" replace /> },
    { path: "/tax-optimization/compare", element: <Navigate to="/tax/compare" replace /> },
    { path: "/tax-optimization/explorer", element: <Navigate to="/tax/explorer" replace /> },
    { path: "/tax-optimization/filing", element: <Navigate to="/tax/filing" replace /> },
    { path: "/login", element: <UserLoginPage /> },
    { path: "/portal/about-you", element: <AboutYouPage /> },
    { path: "/portal/summary", element: <UserPortalPage /> },
    ...userViewRoutes,
    ...demoRoutes,
  ];
  return useRoutes(routes);
}
