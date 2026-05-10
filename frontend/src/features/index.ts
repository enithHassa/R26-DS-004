import type { FeatureModule } from "@/features/types";
import personalizedRecommendation from "@/features/personalized-recommendation";
import transactionSemantic from "@/features/transaction-semantic";
import taxOptimization from "@/features/tax-optimization";
// Teammates register their modules here as they land:
// import languageModel from "@/features/language-model";

export const features: FeatureModule[] = [
  personalizedRecommendation,
  transactionSemantic,
  taxOptimization,
  // languageModel,
];
