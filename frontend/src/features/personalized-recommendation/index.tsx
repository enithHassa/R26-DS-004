import { Navigate } from "react-router-dom";
import { BarChart3, GitCompare, LayoutDashboard, TrendingUp, User } from "lucide-react";

import type { FeatureModule } from "@/features/types";

import { FinancialModuleLayout } from "./financial-module-layout";
import { AuditorDashboardPage } from "./pages/auditor-dashboard";
import { ComparePage } from "./pages/compare";
import { HybridRecommendationsPage } from "./pages/hybrid-recommendations";
import { ImpactPage } from "./pages/impact";
import { ProfilePage } from "./pages/profile";
import { RagRecommendationsPage } from "./pages/rag-recommendations";
import { RecommendationsPage } from "./pages/recommendations";
import { StrategyDetailPage } from "./pages/strategy-detail";

const personalizedRecommendation: FeatureModule = {
  id: "personalized-recommendation",
  title: "Personalized Recommendation",
  layout: FinancialModuleLayout,
  routes: [
    { index: true, element: <Navigate to="/dashboard" replace /> },
    { path: "dashboard", element: <AuditorDashboardPage /> },
    { path: "profile", element: <ProfilePage /> },
    { path: "recommendations", element: <RecommendationsPage /> },
    { path: "strategy/:strategyId", element: <StrategyDetailPage /> },
    { path: "impact", element: <ImpactPage /> },
    { path: "impact/:strategyId", element: <ImpactPage /> },
    { path: "compare", element: <ComparePage /> },
    { path: "rag", element: <RagRecommendationsPage /> },
    { path: "hybrid", element: <HybridRecommendationsPage /> },
  ],
  nav: [
    { to: "/profile", label: "Profiles", icon: User },
    { to: "/hybrid", label: "Smart Recommendations", icon: BarChart3 },
    { to: "/impact", label: "Impact Lab", icon: TrendingUp },
    { to: "/compare", label: "Compare", icon: GitCompare },
    { to: "/dashboard", label: "Decision Dashboard", icon: LayoutDashboard },
  ],
};

export default personalizedRecommendation;
