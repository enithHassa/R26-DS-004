import type { CalculateResponse } from "@/features/optimization-explainable-engine/api";
import type {
  InterviewIncomeState,
  InterviewSession,
  ReliefAnswer,
} from "@/features/optimization-explainable-engine/types";
import {
  adjacentCompareYa,
  hydrateIncomeAmounts,
} from "@/features/optimization-explainable-engine/types";
import type { TaxComputationSnapshotDetail } from "@/features/personalized-recommendation/api/profiles";

export type SnapshotSaveOptions = {
  status: "draft" | "calculated" | "finalized";
  calculateResult?: CalculateResponse | null;
  explainNarrative?: string | null;
  source?: "auditor_manual" | "profile_load" | "transaction_merge";
};

export function buildSnapshotPayload(
  session: InterviewSession,
  options: SnapshotSaveOptions,
) {
  return {
    assessment_year: session.assessmentYear,
    status: options.status,
    taxpayer_name: session.income.taxpayerName || null,
    tin: session.income.tin || null,
    income_state: session.income as unknown as Record<string, unknown>,
    relief_answers: session.reliefAnswers as unknown as Record<string, unknown>[],
    evidence_checks: session.evidenceChecks,
    session_meta: {
      compareYear: session.compareYear,
      excludeSourceDocId: session.excludeSourceDocId,
      selectedCompareGroupId: session.selectedCompareGroupId,
    },
    calculate_result: (options.calculateResult ?? null) as Record<string, unknown> | null,
    explain_narrative: options.explainNarrative ?? null,
    source: options.source ?? "auditor_manual",
  };
}

export function sessionFromSnapshot(snapshot: TaxComputationSnapshotDetail): InterviewSession {
  const meta = snapshot.session_meta ?? {};
  const assessmentYear = snapshot.assessment_year;
  return {
    assessmentYear,
    compareYear:
      typeof meta.compareYear === "string"
        ? meta.compareYear
        : adjacentCompareYa(assessmentYear),
    excludeSourceDocId:
      typeof meta.excludeSourceDocId === "string" ? meta.excludeSourceDocId : null,
    selectedCompareGroupId:
      typeof meta.selectedCompareGroupId === "string" ? meta.selectedCompareGroupId : null,
    income: hydrateIncomeAmounts(snapshot.income_state as unknown as InterviewIncomeState),
    reliefAnswers: (snapshot.relief_answers ?? []) as unknown as ReliefAnswer[],
    evidenceChecks: (snapshot.evidence_checks ?? {}) as Record<string, Record<string, boolean>>,
  };
}

export function sessionCalculationFingerprint(session: InterviewSession): string {
  return JSON.stringify({
    assessmentYear: session.assessmentYear,
    excludeSourceDocId: session.excludeSourceDocId,
    income: session.income,
    reliefAnswers: session.reliefAnswers,
  });
}

export function snapshotCalculationFingerprint(snapshot: TaxComputationSnapshotDetail): string {
  return JSON.stringify({
    assessmentYear: snapshot.assessment_year,
    excludeSourceDocId:
      typeof snapshot.session_meta?.excludeSourceDocId === "string"
        ? snapshot.session_meta.excludeSourceDocId
        : null,
    income: snapshot.income_state,
    reliefAnswers: snapshot.relief_answers,
  });
}
