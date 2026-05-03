import { Navigate } from "react-router-dom";
import { BarChart3, GitCompare, Sparkles, User } from "lucide-react";

import type { FeatureModule } from "@/features/types";

import { FinancialModuleLayout } from "./financial-module-layout";
import { ComparePage } from "./pages/compare";
import { ImpactPage } from "./pages/impact";
import { ProfilePage } from "./pages/profile";
import { RecommendationsPage } from "./pages/recommendations";
import { StrategyDetailPage } from "./pages/strategy-detail";

const personalizedRecommendation: FeatureModule = {
  id: "personalized-recommendation",
  title: "Personalized Recommendation",
  layout: FinancialModuleLayout,
  routes: [
    { index: true, element: <Navigate to="/profile" replace /> },
    { path: "profile", element: <ProfilePage /> },
    { path: "recommendations", element: <RecommendationsPage /> },
    { path: "strategy/:strategyId", element: <StrategyDetailPage /> },
    { path: "impact/:strategyId", element: <ImpactPage /> },
    { path: "compare", element: <ComparePage /> },
  ],
  nav: [
    { to: "/profile", label: "Profile", icon: User },
    { to: "/recommendations", label: "Recommendations", icon: Sparkles },
    { to: "/impact/new", label: "Impact", icon: BarChart3 },
    { to: "/compare", label: "Compare", icon: GitCompare },
  ],
};

export default personalizedRecommendation;
