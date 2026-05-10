import { Navigate, Outlet } from "react-router-dom";
import { BookOpen, Sparkles } from "lucide-react";

import type { FeatureModule } from "@/features/types";

import { LawQueryPage } from "./pages/law-query";
import { NluParsePage } from "./pages/nlu-parse";

const languageModel: FeatureModule = {
  id: "language-model",
  title: "Language Model",
  routes: [
    {
      path: "language-model",
      element: <Outlet />,
      children: [
        { index: true, element: <Navigate to="nlu" replace /> },
        { path: "nlu", element: <NluParsePage /> },
        { path: "query", element: <LawQueryPage /> },
      ],
    },
  ],
  nav: [
    { to: "/language-model/nlu", label: "NLU parse", icon: Sparkles },
    { to: "/language-model/query", label: "Law query", icon: BookOpen },
  ],
};

export default languageModel;
