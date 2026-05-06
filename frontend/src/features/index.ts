import type { FeatureModule } from "@/features/types";
import personalizedRecommendation from "@/features/personalized-recommendation";
import transactionSemantic from "@/features/transaction-semantic";
// Teammates register their modules here as they land:
// import taxOptimization from "@/features/tax-optimization";
// import languageModel from "@/features/language-model";

export const features: FeatureModule[] = [
  personalizedRecommendation,
  transactionSemantic,
  // taxOptimization,
  // languageModel,
];
