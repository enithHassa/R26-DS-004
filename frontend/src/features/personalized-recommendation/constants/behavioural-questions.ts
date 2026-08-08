/**
 * Simple click-through financial-behaviour questions shown to taxpayer users.
 * `question_key` values for `risk_comfort` and `investment_horizon` must match
 * `PROFILE_MAPPED_QUESTIONS` in the backend's
 * `app/services/behavioural_answer_service.py` — answering those two updates
 * the profile directly, so the very next recommendation call reflects them.
 * Any other question is stored for later use but does not yet affect scoring.
 */
export type BehaviouralQuestion = {
  key: string;
  prompt: string;
  options: { value: string; label: string }[];
  affectsRecommendations: boolean;
  /** Allows selecting more than one option; stored as a comma-separated `answer_value`. */
  multiSelect?: boolean;
};

export const BEHAVIOURAL_QUESTIONS: BehaviouralQuestion[] = [
  {
    key: "risk_comfort",
    prompt: "How comfortable are you with investment risk?",
    options: [
      { value: "low", label: "I prefer safe, steady options" },
      { value: "medium", label: "I'm okay with some ups and downs" },
      { value: "high", label: "I'm comfortable with bigger swings for bigger gains" },
    ],
    affectsRecommendations: true,
  },
  {
    key: "investment_horizon",
    prompt: "How long are you planning to invest for?",
    options: [
      { value: "3", label: "A few years (short term)" },
      { value: "10", label: "About a decade (medium term)" },
      { value: "20", label: "20+ years (long term)" },
    ],
    affectsRecommendations: true,
  },
  {
    key: "invest_frequency",
    prompt: "How often do you usually invest money?",
    options: [
      { value: "rarely", label: "Rarely, if ever" },
      { value: "occasionally", label: "Occasionally, when I have spare cash" },
      { value: "regularly", label: "Regularly, every month" },
    ],
    affectsRecommendations: false,
  },
  {
    key: "financial_goals",
    prompt: "What are you hoping to achieve financially? (choose all that apply)",
    options: [
      { value: "retirement", label: "Save for retirement" },
      { value: "home", label: "Buy or pay off a home" },
      { value: "family", label: "Support family or dependents" },
      { value: "debt_free", label: "Become debt-free" },
      { value: "grow_wealth", label: "Grow my savings and investments" },
    ],
    affectsRecommendations: false,
    multiSelect: true,
  },
  {
    key: "extra_money_use",
    prompt: "When you have spare money, where does it usually go? (choose all that apply)",
    options: [
      { value: "emergency_fund", label: "Emergency fund" },
      { value: "investments", label: "Investments" },
      { value: "debt_repayment", label: "Paying down debt" },
      { value: "leisure", label: "Leisure or travel" },
      { value: "family_support", label: "Family or dependents" },
    ],
    affectsRecommendations: false,
    multiSelect: true,
  },
];
