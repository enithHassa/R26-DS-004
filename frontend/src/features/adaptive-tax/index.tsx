import { Navigate, Outlet } from "react-router-dom";
import {
  Calculator,
  FileUp,
  LayoutDashboard,
  BarChart3,
  MessageCircle,
  Library,
  GitCompare,
} from "lucide-react";

import type { FeatureModule } from "@/features/types";

import { AdaptiveTaxAdminReviewPage } from "./pages/admin-review";
import { AdaptiveTaxAdminUploadPage } from "./pages/admin-upload";
import { CatalogAdminJobPage } from "./pages/catalog-admin/job";
import { CatalogAdminLayout } from "./pages/catalog-admin/layout";
import { CatalogAdminQueuePage } from "./pages/catalog-admin/queue";
import { CatalogAdminReviewPage } from "./pages/catalog-admin/review";
import { CatalogAdminUploadPage } from "./pages/catalog-admin/upload";
import { AdaptiveTaxCalculatorPage } from "./pages/calculator";
import { RagTaxCalculatorPage } from "./pages/rag-tax-calculator";
import { AdaptiveTaxCoveragePage } from "./pages/coverage";
import { AdaptiveTaxHomePage } from "./pages/home";
import { AdaptiveTaxReportPage } from "./pages/report";
import { AdaptiveTaxComparePage } from "./pages/year-compare";
import { ReliefInterviewLayout } from "./pages/relief-interview/layout";
import { ReliefInterviewEntryPage } from "./pages/relief-interview/entry";
import { ReliefInterviewIncomePage } from "./pages/relief-interview/income";
import { ReliefInterviewReliefsPage } from "./pages/relief-interview/reliefs";
import { ReliefInterviewResultPage } from "./pages/relief-interview/result";
import { ReliefInterviewReportPage } from "./pages/relief-interview/report";

const adaptiveTax: FeatureModule = {
  id: "adaptive-tax",
  title: "Adaptive Tax",
  routes: [
    {
      path: "adaptive-tax",
      element: <Outlet />,
      children: [
        { index: true, element: <Navigate to="home" replace /> },
        { path: "home", element: <AdaptiveTaxHomePage /> },
        { path: "calculator", element: <AdaptiveTaxCalculatorPage /> },
        { path: "rag-calculator", element: <RagTaxCalculatorPage /> },
        {
          path: "relief-interview",
          element: <ReliefInterviewLayout />,
          children: [
            { index: true, element: <ReliefInterviewEntryPage /> },
            { path: "income", element: <ReliefInterviewIncomePage /> },
            { path: "reliefs", element: <ReliefInterviewReliefsPage /> },
            {
              path: "compare",
              element: <Navigate to="/adaptive-tax/compare" replace />,
            },
            { path: "result", element: <ReliefInterviewResultPage /> },
            { path: "report", element: <ReliefInterviewReportPage /> },
          ],
        },
        { path: "coverage", element: <AdaptiveTaxCoveragePage /> },
        { path: "compare", element: <AdaptiveTaxComparePage /> },
        { path: "report/:calcId", element: <AdaptiveTaxReportPage /> },
        { path: "admin/upload", element: <AdaptiveTaxAdminUploadPage /> },
        { path: "admin/review/:jobId", element: <AdaptiveTaxAdminReviewPage /> },
        {
          path: "catalog-admin",
          element: <CatalogAdminLayout />,
          children: [
            { index: true, element: <CatalogAdminQueuePage /> },
            { path: "upload", element: <CatalogAdminUploadPage /> },
            { path: "review/:sourceDocId", element: <CatalogAdminReviewPage /> },
            { path: "jobs/:jobId", element: <CatalogAdminJobPage /> },
          ],
        },
      ],
    },
  ],
  // Report is linked from the calculator after a successful calc (not always in sidebar).
  nav: [
    { to: "/adaptive-tax/home", label: "Home", icon: LayoutDashboard },
    { to: "/adaptive-tax/calculator", label: "Calculator", icon: Calculator },
    { to: "/adaptive-tax/rag-calculator", label: "RAG Calculator", icon: Calculator },
    {
      to: "/adaptive-tax/relief-interview",
      label: "Relief Interview",
      icon: MessageCircle,
    },
    { to: "/adaptive-tax/compare", label: "Compare", icon: GitCompare },
    { to: "/adaptive-tax/coverage", label: "Coverage", icon: BarChart3 },
    { to: "/adaptive-tax/admin/upload", label: "Upload", icon: FileUp },
    // Later: point this at the admin dashboard instead of catalog-admin directly.
    { to: "/adaptive-tax/catalog-admin", label: "Catalog admin", icon: Library },
  ],
};

export default adaptiveTax;
