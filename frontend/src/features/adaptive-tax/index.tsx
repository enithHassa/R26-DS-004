import { Navigate, Outlet } from "react-router-dom";
import { Calculator, FileUp, LayoutDashboard } from "lucide-react";

import type { FeatureModule } from "@/features/types";

import { AdaptiveTaxAdminReviewPage } from "./pages/admin-review";
import { AdaptiveTaxAdminUploadPage } from "./pages/admin-upload";
import { AdaptiveTaxCalculatorPage } from "./pages/calculator";
import { AdaptiveTaxHomePage } from "./pages/home";
import { AdaptiveTaxReportPage } from "./pages/report";

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
        { path: "report/:calcId", element: <AdaptiveTaxReportPage /> },
        { path: "admin/upload", element: <AdaptiveTaxAdminUploadPage /> },
        { path: "admin/review/:jobId", element: <AdaptiveTaxAdminReviewPage /> },
      ],
    },
  ],
  // Report is linked from the calculator after a successful calc (not always in sidebar).
  nav: [
    { to: "/adaptive-tax/home", label: "Home", icon: LayoutDashboard },
    { to: "/adaptive-tax/calculator", label: "Calculator", icon: Calculator },
    { to: "/adaptive-tax/admin/upload", label: "Upload", icon: FileUp },
  ],
};

export default adaptiveTax;
