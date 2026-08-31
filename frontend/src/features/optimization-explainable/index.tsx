import {
  Calculator,
  FileText,
  GitCompareArrows,
  LayoutDashboard,
  Library,
  ListChecks,
  MessageCircle,
  Wallet,
} from "lucide-react";

import type { FeatureModule } from "@/features/types";

import { OptimizationExplainableHomePage } from "./pages/home";
import { CompareLayout, InterviewLayout } from "./pages/layout";
import { InterviewEntryPage } from "./pages/entry";
import { InterviewActsPage } from "./pages/acts";
import { InterviewIncomePage } from "./pages/income";
import { InterviewReliefsPage } from "./pages/reliefs";
import { InterviewResultPage } from "./pages/result";
import { InterviewComparePage } from "./pages/compare";

const optimizationExplainable: FeatureModule = {
  id: "optimization-explainable",
  title: "Optimization and Explainable",
  routes: [
    { path: "optimization-explainable/home", element: <OptimizationExplainableHomePage /> },
    {
      path: "optimization-explainable/compare",
      element: <CompareLayout />,
      children: [{ index: true, element: <InterviewComparePage /> }],
    },
    {
      path: "optimization-explainable",
      element: <InterviewLayout />,
      children: [
        { index: true, element: <InterviewEntryPage /> },
        { path: "acts", element: <InterviewActsPage /> },
        { path: "income", element: <InterviewIncomePage /> },
        { path: "reliefs", element: <InterviewReliefsPage /> },
        { path: "result", element: <InterviewResultPage /> },
      ],
    },
  ],
  nav: [
    { to: "/optimization-explainable/home", label: "Home", icon: LayoutDashboard },
    { to: "/optimization-explainable", label: "Interview", icon: MessageCircle },
    { to: "/optimization-explainable/acts", label: "Acts", icon: FileText },
    { to: "/optimization-explainable/income", label: "Income", icon: Wallet },
    { to: "/optimization-explainable/reliefs", label: "Reliefs", icon: ListChecks },
    { to: "/optimization-explainable/compare", label: "Compare", icon: GitCompareArrows },
    { to: "/optimization-explainable/result", label: "Result", icon: Calculator },
    {
      to: "/adaptive-tax/catalog-admin",
      label: "Load new act",
      icon: Library,
    },
  ],
};

export default optimizationExplainable;
