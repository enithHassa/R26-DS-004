import type { FeatureModule } from "@/features/types";
import personalizedRecommendation from "@/features/personalized-recommendation";
// Teammates register their modules here as they land:
// import transactionSemantic from "@/features/transaction-semantic";
// import taxOptimization from "@/features/tax-optimization";
// import languageModel from "@/features/language-model";

export const features: FeatureModule[] = [
  personalizedRecommendation,
  // transactionSemantic,
  // taxOptimization,
  // languageModel,
];
