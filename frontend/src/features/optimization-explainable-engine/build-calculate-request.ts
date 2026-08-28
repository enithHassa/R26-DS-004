import type { CalculateComponentClaim, CalculateRequest } from "./api";
import { parseLkr } from "./format-lkr";
import { buildTerminalBenefitsPayload } from "./terminal-benefits";
import {
  type ReliefAnswer,
  businessIncomeLkr,
  employmentIncomeLkr,
  interestIncomeLkr,
  investmentIncomeLkr,
  otherIncomeLkr,
  rentsIncomeLkr,
  whtAlreadyPaidLkr,
  type InterviewSession,
} from "./types";

function componentClaims(answer: ReliefAnswer): CalculateComponentClaim[] {
  return Object.entries(answer.components ?? {}).map(([component_id, amount]) => ({
    component_id,
    amount: parseLkr(amount),
  }));
}

export function buildCalculateRequest(session: InterviewSession): CalculateRequest {
  const { income } = session;
  const terminalBenefits = buildTerminalBenefitsPayload(
    income.hasTerminalBenefits,
    income.terminalBenefits,
    session.assessmentYear,
  );
  return {
    assessment_year: session.assessmentYear,
    income: {
      employment: employmentIncomeLkr(income),
      business: businessIncomeLkr(income),
      investment: investmentIncomeLkr(income),
      other: otherIncomeLkr(income),
      interest: interestIncomeLkr(income),
      rents: rentsIncomeLkr(income),
      ...(terminalBenefits.length > 0 ? { terminal_benefits: terminalBenefits } : {}),
    },
    claims: session.reliefAnswers.map((a) => ({
      entry_id: a.entry_id,
      amount: parseLkr(a.amount ?? "0"),
      affirmed: a.affirmed ?? null,
      skipped: a.skipped ?? false,
      components: componentClaims(a),
    })),
    exclude_source_doc_id: session.excludeSourceDocId,
    wht_already_paid: whtAlreadyPaidLkr(income),
  };
}
