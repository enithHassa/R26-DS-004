import { GitCompareArrows, LayoutList, ShieldCheck } from "lucide-react";

import type { FeatureModule } from "@/features/types";

import { CompliancePage } from "./pages/compliance";
import { ComparePage } from "./pages/compare";
import { ExplorerPage } from "./pages/explorer";

/** Component B — routes are mounted in ``App.tsx`` under ``/tax-optimization/*`` (standalone, not team sidebar). */
export { TaxOptimizationStandalone } from "./standalone-shell";
export { CompliancePage } from "./pages/compliance";
export { ComparePage } from "./pages/compare";
export { ExplorerPage } from "./pages/explorer";

const taxOptimization: FeatureModule = {
  id: "tax-optimization",
  title: "Tax Optimization",
  routes: [
    { path: "tax/compliance", element: <CompliancePage /> },
    { path: "tax/compare", element: <ComparePage /> },
    { path: "tax/explorer", element: <ExplorerPage /> },
  ],
  nav: [
    { to: "/tax/compliance", label: "Check my tax", icon: ShieldCheck },
    { to: "/tax/compare", label: "Compare strategies", icon: GitCompareArrows },
    { to: "/tax/explorer", label: "Find best strategy", icon: LayoutList },
  ],
};

export default taxOptimization;
