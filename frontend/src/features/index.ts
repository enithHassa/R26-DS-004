import type { FeatureModule } from "@/features/types";
import personalizedRecommendation from "@/features/personalized-recommendation";
// Teammates register their modules here as they land:
// import transactionSemantic from "@/features/transaction-semantic";
// import languageModel from "@/features/language-model";

/** Component B (tax optimization) uses its own page at `/tax-optimization/*` — not listed here so it stays off the team sidebar. */

export const features: FeatureModule[] = [
  personalizedRecommendation,
  // transactionSemantic,
  // languageModel,
];
