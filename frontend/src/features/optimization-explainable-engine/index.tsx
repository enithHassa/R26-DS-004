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
import { CompareLayout, InterviewLayout, LoadActLayout } from "./pages/layout";
import { InterviewEntryPage } from "./pages/entry";
import { InterviewActsPage } from "./pages/acts";
import { InterviewIncomePage } from "./pages/income";
import { InterviewReliefsPage } from "./pages/reliefs";
import { InterviewResultPage } from "./pages/result";
import { InterviewComparePage } from "./pages/compare";
import { LoadNewActPage } from "./pages/load-act";
import { ActAdminJobPage } from "./act-admin/job";
import { ActAdminLayout } from "./act-admin/layout";
import { ActAdminQueuePage } from "./act-admin/queue";
import { ActAdminReviewPage } from "./act-admin/review";
import { ActAdminUploadPage } from "./act-admin/upload";

const optimizationExplainableEngine: FeatureModule = {
  id: "optimization-explainable-engine",
  title: "Optimization and Explainable Engine",
  routes: [
    {
      path: "optimization-explainable-engine/home",
      element: <OptimizationExplainableHomePage />,
    },
    {
      path: "optimization-explainable-engine/compare",
      element: <CompareLayout />,
      children: [{ index: true, element: <InterviewComparePage /> }],
    },
    {
      path: "optimization-explainable-engine/load-act",
      element: <LoadActLayout />,
      children: [{ index: true, element: <LoadNewActPage /> }],
    },
    {
      path: "optimization-explainable-engine/act-admin",
      element: <ActAdminLayout />,
      children: [
        { index: true, element: <ActAdminQueuePage /> },
        { path: "upload", element: <ActAdminUploadPage /> },
        { path: "jobs/:jobId", element: <ActAdminJobPage /> },
        { path: "review/:sourceDocId", element: <ActAdminReviewPage /> },
      ],
    },
    {
      path: "optimization-explainable-engine",
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
    { to: "/optimization-explainable-engine/home", label: "Home", icon: LayoutDashboard },
    { to: "/optimization-explainable-engine", label: "Interview", icon: MessageCircle },
    { to: "/optimization-explainable-engine/acts", label: "Acts", icon: FileText },
    { to: "/optimization-explainable-engine/income", label: "Income", icon: Wallet },
    { to: "/optimization-explainable-engine/reliefs", label: "Reliefs", icon: ListChecks },
    { to: "/optimization-explainable-engine/compare", label: "Compare", icon: GitCompareArrows },
    { to: "/optimization-explainable-engine/result", label: "Result", icon: Calculator },
    { to: "/optimization-explainable-engine/load-act", label: "Load new act", icon: Library },
  ],
};

export default optimizationExplainableEngine;
