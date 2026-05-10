import { Navigate, useRoutes, type RouteObject } from "react-router-dom";

import { AppShell } from "@/components/layout/app-shell";
import { features } from "@/features";
import {
  ComparePage,
  CompliancePage,
  ExplorerPage,
  TaxOptimizationStandalone,
} from "@/features/tax-optimization";

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
    {
      path: "/tax-optimization",
      element: <TaxOptimizationStandalone />,
      children: [
        { index: true, element: <Navigate to="compliance" replace /> },
        { path: "compliance", element: <CompliancePage /> },
        { path: "compare", element: <ComparePage /> },
        { path: "explorer", element: <ExplorerPage /> },
      ],
    },
  ];
  return useRoutes(routes);
}
