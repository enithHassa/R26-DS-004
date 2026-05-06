import type { FeatureModule } from "@/features/types";
import personalizedRecommendation from "@/features/personalized-recommendation";
import transactionSemantic from "@/features/transaction-semantic";
// Teammates register their modules here as they land:
// import taxOptimization from "@/features/tax-optimization";
// import languageModel from "@/features/language-model";

/** Component B (tax optimization) uses its own page at `/tax-optimization/*` — not listed here so it stays off the team sidebar. */

export const features: FeatureModule[] = [
  personalizedRecommendation,
  transactionSemantic,
  // taxOptimization,
  // languageModel,
];
