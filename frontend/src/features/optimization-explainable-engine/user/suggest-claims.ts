import { detailFromProfile } from "@/features/tax-return-profile/mappers";
import type { FinancialProfile } from "@/features/personalized-recommendation/types";
import type { TaxReturnDetail } from "@/features/tax-return-profile/types";

import { parseLkr, roundLkr } from "../format-lkr";
import {
  interestIncomeLkr,
  rentsIncomeLkr,
} from "../income-aggregate";
import type { InterviewIncomeState, ReliefAnswer, ReliefEntry } from "../types";

function num(raw: string | undefined | null): number {
  if (raw == null || raw === "") return 0;
  const n = Number(String(raw).replace(/,/g, ""));
  return Number.isFinite(n) ? roundLkr(n) : 0;
}

function ageFromDob(dob: string, assessmentYear: string): number | null {
  if (!dob) return null;
  const birth = new Date(dob);
  if (Number.isNaN(birth.getTime())) return null;
  const m = /^(\d{4})_\d{2}$/.exec(assessmentYear);
  const yaStart = m ? Number(m[1]) : new Date().getFullYear();
  // YA YYYY_YY starts 1 Apr YYYY
  const asOf = new Date(yaStart, 3, 1);
  let age = asOf.getFullYear() - birth.getFullYear();
  const md = asOf.getMonth() - birth.getMonth();
  if (md < 0 || (md === 0 && asOf.getDate() < birth.getDate())) age -= 1;
  return age;
}

function matchGroup(entry: ReliefEntry, ...needles: string[]): boolean {
  const id = (entry.compare_group_id ?? "").toLowerCase();
  const name = (entry.display_name ?? "").toLowerCase();
  const kind = (entry.engine_binding?.kind ?? "").toLowerCase();
  return needles.some((n) => id.includes(n) || name.includes(n) || kind.includes(n));
}

function claim(
  entry: ReliefEntry,
  amount: number,
  affirmed = true,
): ReliefAnswer | null {
  if (amount <= 0 && entry.input_kind !== "boolean" && entry.input_kind !== "notice") {
    return null;
  }
  return {
    entry_id: entry.entry_id,
    compare_group_id: entry.compare_group_id,
    affirmed,
    amount: String(roundLkr(amount)),
    skipped: false,
  };
}

/** Map Tax Return Profile + income into suggested OE relief claims for a YA catalog. */
export function suggestClaimsFromProfile(
  profile: FinancialProfile,
  income: InterviewIncomeState,
  entries: ReliefEntry[],
  assessmentYear: string,
): ReliefAnswer[] {
  const detail = detailFromProfile(profile);
  const answers: ReliefAnswer[] = [];
  const seen = new Set<string>();

  function push(answer: ReliefAnswer | null) {
    if (!answer || seen.has(answer.entry_id)) return;
    seen.add(answer.entry_id);
    answers.push(answer);
  }

  const s6 = detail.section6;
  const donationTotal =
    num(s6.charitablePresident) +
    num(s6.charitableApproved) +
    num(s6.charitableReligious) +
    num(s6.charitableOther);

  for (const entry of entries) {
    if (entry.auto_applied) continue;

    if (s6.hasLife && matchGroup(entry, "life_insurance", "life insurance", "insurance")) {
      push(claim(entry, num(s6.lifePremium)));
      continue;
    }
    if (s6.hasMedical && matchGroup(entry, "medical", "health_insurance")) {
      push(claim(entry, num(s6.medicalPremium)));
      continue;
    }
    // Charitable-institution donations only — do not also mark government/approved-fund
    // relief as claimed with the same total (that left a 0-amount "Claimed" sibling).
    if (
      s6.hasCharitable &&
      donationTotal > 0 &&
      matchGroup(entry, "donation_to_charitable", "charitable_institution", "charit") &&
      !matchGroup(entry, "government", "approved_fund", "approved fund")
    ) {
      push(claim(entry, donationTotal));
      continue;
    }
    if (
      s6.hasCharitable &&
      donationTotal > 0 &&
      matchGroup(entry, "donation") &&
      !matchGroup(entry, "government", "approved_fund", "approved fund", "charit")
    ) {
      // Generic "donations" group fallback when catalog id is not specific.
      push(claim(entry, donationTotal));
      continue;
    }
    if (s6.hasEducation && matchGroup(entry, "education", "school")) {
      push(claim(entry, num(s6.educationFees)));
      continue;
    }
    if (s6.hasPension && matchGroup(entry, "pension", "superannuation", "provident")) {
      push(claim(entry, num(s6.pensionAmount)));
      continue;
    }
    if (s6.hasMortgage && matchGroup(entry, "mortgage", "home_loan", "housing_loan")) {
      push(claim(entry, num(s6.mortgageInterest)));
      continue;
    }
    if (s6.hasRD && matchGroup(entry, "research", "r_and_d", "rd_")) {
      push(claim(entry, num(s6.rdAmount)));
      continue;
    }
    if (s6.hasDisability && matchGroup(entry, "disabilit")) {
      push(claim(entry, num(s6.disabilityAmount)));
      continue;
    }

    const rents = rentsIncomeLkr(income);
    if (rents > 0 && matchGroup(entry, "rent", "rental")) {
      // Cap on rental relief is a percent (e.g. 25), not an LKR ceiling.
      if (entry.unit === "percent") {
        const pct = entry.cap_amount != null && entry.cap_amount !== ""
          ? Number(String(entry.cap_amount).replace(/,/g, ""))
          : 25;
        const rate = Number.isFinite(pct) && pct > 0 ? pct : 25;
        push(claim(entry, roundLkr((rents * rate) / 100), true));
      } else {
        const cap = entry.cap_amount ? parseLkr(entry.cap_amount) : rents;
        push(claim(entry, Math.min(rents, cap || rents), true));
      }
      continue;
    }

    const interest = interestIncomeLkr(income);
    const age = ageFromDob(detail.section1.dob, assessmentYear);
    if (
      interest > 0 &&
      age != null &&
      age >= 60 &&
      matchGroup(entry, "senior", "senior_citizen")
    ) {
      push(claim(entry, interest, true));
    }
  }

  return answers;
}

export function profileHasUsableIncome(detail: TaxReturnDetail): boolean {
  const emp = detail.section2.employers.some((e) => num(e.gross) > 0);
  const biz = detail.section4.businesses.some((b) => num(b.revenue) > 0);
  const rent = detail.section5.properties.some((p) => num(p.gross || p.rent) > 0);
  const fd = detail.section3.fds.some((f) => num(f.interest) > 0);
  return emp || biz || rent || fd || detail.section4.hasFreelance || detail.section4.hasProfessional;
}
