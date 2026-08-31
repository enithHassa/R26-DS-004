import type { CalculateRequest } from "./api";
import { parseLkr } from "./format-lkr";
import {
  businessIncomeLkr,
  employmentIncomeLkr,
  interestIncomeLkr,
  investmentIncomeLkr,
  otherIncomeLkr,
  rentsIncomeLkr,
  type InterviewSession,
} from "./types";

export function buildCalculateRequest(session: InterviewSession): CalculateRequest {
  const { income } = session;
  return {
    assessment_year: session.assessmentYear,
    income: {
      employment: employmentIncomeLkr(income),
      business: businessIncomeLkr(income),
      investment: investmentIncomeLkr(income),
      other: otherIncomeLkr(income),
      interest: interestIncomeLkr(income),
      rents: rentsIncomeLkr(income),
    },
    claims: session.reliefAnswers.map((a) => ({
      entry_id: a.entry_id,
      amount: parseLkr(a.amount ?? "0"),
      affirmed: a.affirmed ?? null,
      skipped: a.skipped ?? false,
    })),
    exclude_source_doc_id: session.excludeSourceDocId,
  };
}
