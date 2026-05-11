import { Navigate, useRoutes, type RouteObject } from "react-router-dom";

import { AppShell } from "@/components/layout/app-shell";
import { features } from "@/features";

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
  ];
  return useRoutes(routes);
}
