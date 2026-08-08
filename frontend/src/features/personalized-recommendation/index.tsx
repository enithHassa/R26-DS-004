import { Navigate } from "react-router-dom";
import { BarChart3, GitCompare, Merge, User } from "lucide-react";

import type { FeatureModule } from "@/features/types";

import { FinancialModuleLayout } from "./financial-module-layout";
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
    { index: true, element: <Navigate to="/profile" replace /> },
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
    { to: "/profile", label: "Profile", icon: User },
    { to: "/hybrid", label: "Smart Recommendations", icon: Merge },
    { to: "/impact", label: "Impact", icon: BarChart3 },
    { to: "/compare", label: "Compare", icon: GitCompare },
  ],
};

export default personalizedRecommendation;
