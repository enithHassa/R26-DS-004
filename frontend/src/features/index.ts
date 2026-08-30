import type { FeatureModule } from "@/features/types";
import personalizedRecommendation from "@/features/personalized-recommendation";
import transactionSemantic from "@/features/transaction-semantic";
import languageModel from "@/features/language-model";
import taxOptimization from "@/features/tax-optimization";
import adaptiveTax from "@/features/adaptive-tax";
import optimizationExplainable from "@/features/optimization-explainable";
import optimizationExplainableEngine from "@/features/optimization-explainable-engine";

export const features: FeatureModule[] = [
  personalizedRecommendation,
  transactionSemantic,
  languageModel,
  optimizationExplainableEngine,
  taxOptimization,
  adaptiveTax,
  optimizationExplainable,
];
