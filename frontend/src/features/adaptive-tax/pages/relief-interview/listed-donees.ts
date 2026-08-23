/**
 * Fifth Schedule ¶1(b) listed public donees — presentation map.
 * compare_group_id is the approved-catalog identity; component_id is the
 * existing Calculator filing-line bucket (never invent new engine IDs).
 */

export type ListedDoneeDef = {
  compare_group_id: string;
  /** Roman item label(s) in the Act */
  roman: string;
  short_label: string;
  component_id:
    | "qp_government_sri_lanka"
    | "qp_local_authority"
    | "qp_university_hei"
    | "qp_government_fund"
    | "qp_other_listed_funds";
  /** Sec 52(4) CF from YA 2025/26 — engine flags government + government fund only */
  sec52_4_eligible: boolean;
};

/** Nine independent compare groups (iii)+(iv) share one group / engine bucket). */
export const LISTED_PUBLIC_DONEES: readonly ListedDoneeDef[] = [
  {
    compare_group_id: "qp_donee_government_sri_lanka",
    roman: "(i)",
    short_label: "Government of Sri Lanka",
    component_id: "qp_government_sri_lanka",
    sec52_4_eligible: true,
  },
  {
    compare_group_id: "qp_donee_local_authority",
    roman: "(ii)",
    short_label: "Local authority",
    component_id: "qp_local_authority",
    sec52_4_eligible: false,
  },
  {
    compare_group_id: "qp_donee_university_hei",
    roman: "(iii)–(iv)",
    short_label: "University / HEI / Buddhist & Pali University",
    component_id: "qp_university_hei",
    sec52_4_eligible: false,
  },
  {
    compare_group_id: "qp_donee_government_fund",
    roman: "(v)",
    short_label: "Government fund",
    component_id: "qp_government_fund",
    sec52_4_eligible: true,
  },
  {
    compare_group_id: "qp_donee_local_authority_fund",
    roman: "(vi)",
    short_label: "Local authority fund",
    component_id: "qp_other_listed_funds",
    sec52_4_eligible: false,
  },
  {
    compare_group_id: "qp_donee_sevana_fund",
    roman: "(vii)",
    short_label: "Sevana Fund",
    component_id: "qp_other_listed_funds",
    sec52_4_eligible: false,
  },
  {
    compare_group_id: "qp_donee_provincial_fund",
    roman: "(viii)",
    short_label: "Provincial Council fund",
    component_id: "qp_other_listed_funds",
    sec52_4_eligible: false,
  },
  {
    compare_group_id: "qp_donee_api_wenuwen_api",
    roman: "(ix)",
    short_label: "Api Wenuwen Api Fund",
    component_id: "qp_other_listed_funds",
    sec52_4_eligible: false,
  },
  {
    compare_group_id: "qp_donee_national_kidney_fund",
    roman: "(x)",
    short_label: "National Kidney Fund",
    component_id: "qp_other_listed_funds",
    sec52_4_eligible: false,
  },
] as const;

const DONE_ORDER = new Map(
  LISTED_PUBLIC_DONEES.map((d, i) => [d.compare_group_id, i]),
);

export function isListedPublicDoneeGroup(compareGroupId: string): boolean {
  return compareGroupId.startsWith("qp_donee_");
}

/** Compare page: all ¶1(b) donees as one type, not per-donee subtypes. */
export const LISTED_PUBLIC_DONEES_COMPARE_TYPE = "qp_listed_public_donees";

export const LISTED_PUBLIC_DONEES_COMPARE_LABEL =
  "¶1(b) listed public donees";

export function isListedPublicDoneesCompareType(compareGroupId: string): boolean {
  return (
    compareGroupId === LISTED_PUBLIC_DONEES_COMPARE_TYPE ||
    isListedPublicDoneeGroup(compareGroupId)
  );
}

export function listedDoneeMeta(
  compareGroupId: string,
): ListedDoneeDef | undefined {
  return LISTED_PUBLIC_DONEES.find((d) => d.compare_group_id === compareGroupId);
}

export function sortListedDoneeEntries<T extends { compare_group_id: string }>(
  entries: T[],
): T[] {
  return [...entries].sort((a, b) => {
    const ia = DONE_ORDER.get(a.compare_group_id) ?? 999;
    const ib = DONE_ORDER.get(b.compare_group_id) ?? 999;
    return ia - ib;
  });
}

export const LISTED_DONEES_BLOCK_PROMPT =
  "Did you make donations under Fifth Schedule paragraph 1(b) to any listed public body or fund?";

/** Plain-language conditions for taxpayers (not legal advice). */
export const LISTED_DONEES_HELP = {
  intro:
    "This is for donations to the specific public bodies and funds named in Fifth Schedule 1(b) — not ordinary charities (those use the separate approved-charity question).",
  who: "Individuals and entities can claim. Enter only donations you actually made to one of the listed donees below.",
  form: "The donation may be in money or otherwise (for example goods), as long as it goes to a listed body or fund.",
  limitsTitle: "Limits",
  limits: [
    "The Act does not set a fixed rupee or percentage cap for each 1(b) donee (unlike approved charity’s Rs 75,000 / one-third rule).",
    "You still cannot deduct more than your remaining taxable income once qualifying payments are applied.",
    "Local-authority funds and Provincial Council funds must be ones approved by the Minister where the Act requires that.",
  ],
  cfTitle: "Carry-forward (YA 2025/26)",
  cfBody:
    "If you cannot use the full amount this year, Sec 52(4) may allow unused donations to the Government of Sri Lanka or a Government fund to be carried forward. Other listed donees on this list do not get that carry-forward treatment in this calculator.",
  engineNote:
    "Enter each donee separately. University / HEI rows and the smaller named funds are combined into shared calculator buckets when tax is calculated.",
} as const;