import { useState, useEffect } from "react";
import type { ChangeEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useFieldArray, useForm } from "react-hook-form";
import type { UseFormRegisterReturn } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import {
  Loader2,
  Trash2,
  RefreshCw,
  X,
  Plus,
  UserRound,
  Briefcase,
  Wallet,
  PiggyBank,
  ShieldCheck,
  TrendingUp,
  Landmark,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";

import {
  createProfile,
  deleteProfile,
  getProfile,
  getProfileFeatures,
  listProfiles,
  setEligibilityOverride,
} from "../api/profiles";
import { PageHeader } from "../components/page-header";
import { WizardNav } from "../components/wizard-nav";
import { useDashboardStore } from "../store/dashboard-store";
import { AGE_BANDS, SL_PROVINCES, type FinancialProfileCreate } from "../types";

const decimalString = z
  .string()
  .min(1, "Required")
  .refine((v) => !Number.isNaN(Number(v)) && Number(v) >= 0, "Must be ≥ 0");

const integerString = (max: number, min = 0) =>
  z
    .string()
    .min(1, "Required")
    .regex(/^\d+$/, "Must be a whole number")
    .transform((v) => Number(v))
    .refine((n) => n <= max && n >= min, `Must be between ${min} and ${max}`);

const incomeSourceSchema = z.object({
  kind: z.enum(
    ["employment", "business", "rental", "interest", "dividend", "capital_gain", "other"],
    { errorMap: () => ({ message: "Required" }) },
  ),
  monthly_amount: decimalString,
  is_taxable: z.boolean(),
});

const profileSchema = z.object({
  full_name: z.string().min(1, "Required").max(200),
  age_band: z.enum(["18-24", "25-29", "30-34", "35-39", "40-44", "45-49", "50-54", "55-59", "60-64", "65-70", "70+"], {
    errorMap: () => ({ message: "Required" }),
  }),
  gender: z.enum(["male", "female", "other"], { errorMap: () => ({ message: "Required" }) }),
  province: z.enum(
    [
      "Western",
      "Central",
      "Southern",
      "Northern",
      "Eastern",
      "North Western",
      "North Central",
      "Uva",
      "Sabaragamuwa",
    ],
    { errorMap: () => ({ message: "Required" }) },
  ),
  marital_status: z.enum(["single", "married", "divorced", "widowed"], {
    errorMap: () => ({ message: "Required" }),
  }),
  residency_status: z.enum(["resident", "non_resident", "dual"], {
    errorMap: () => ({ message: "Required" }),
  }),
  nationality: z.string().max(64).optional().or(z.literal("")),
  occupation: z.enum(
    ["employee", "self_employed", "business_owner", "investor", "professional", "other"],
    { errorMap: () => ({ message: "Required" }) },
  ),
  employment_type: z.enum(
    ["permanent", "contract", "part_time", "freelance", "unemployed"],
    { errorMap: () => ({ message: "Required" }) },
  ),
  employer_sector: z.enum(["private", "public", "ngo", "self_employed"], {
    errorMap: () => ({ message: "Required" }),
  }),
  dependents: integerString(20),
  years_employed: integerString(60),
  gross_monthly_income: decimalString,
  annual_bonus_lkr: decimalString,
  monthly_expenses: decimalString,
  monthly_debt_service: decimalString,
  liquid_savings: decimalString,
  existing_investments: decimalString,
  total_debt: decimalString,
  epf_balance: decimalString,
  etf_balance: decimalString,
  vehicle_value: decimalString,
  property_value: decimalString,
  health_insurance: z.boolean(),
  life_insurance_premium_annual: decimalString,
  home_loan_interest_annual: decimalString,
  donations_annual: decimalString,
  risk_tolerance: z.enum(["low", "medium", "high"], { errorMap: () => ({ message: "Required" }) }),
  investment_horizon_years: integerString(50),
  retirement_age_target: integerString(75, 40),
  tax_year: z.string().regex(/^\d{4}_\d{2}$/, "Format YYYY_YY"),
  income_sources: z.array(incomeSourceSchema).min(1, "Add at least one income source"),
});

type ProfileForm = z.input<typeof profileSchema>;
type ProfileFormOutput = z.output<typeof profileSchema>;

function sanitizeIntegerString(raw: string): string {
  return raw.replace(/\D/g, "");
}

function sanitizeDecimalString(raw: string): string {
  let v = raw.replace(/[^\d.]/g, "");
  const dot = v.indexOf(".");
  if (dot !== -1) {
    v = v.slice(0, dot + 1) + v.slice(dot + 1).replace(/\./g, "");
  }
  return v;
}

function sanitizeTaxYearString(raw: string): string {
  return raw.replace(/[^\d_]/g, "").slice(0, 7);
}

function withIntegerSanitize<T extends string>(
  reg: UseFormRegisterReturn<T>,
): UseFormRegisterReturn<T> {
  return {
    ...reg,
    onChange: (e, ...rest) => {
      const ce = e as ChangeEvent<HTMLInputElement>;
      ce.target.value = sanitizeIntegerString(ce.target.value);
      return reg.onChange(e, ...rest);
    },
  };
}

function withDecimalSanitize<T extends string>(
  reg: UseFormRegisterReturn<T>,
): UseFormRegisterReturn<T> {
  return {
    ...reg,
    onChange: (e, ...rest) => {
      const ce = e as ChangeEvent<HTMLInputElement>;
      ce.target.value = sanitizeDecimalString(ce.target.value);
      return reg.onChange(e, ...rest);
    },
  };
}

function withTaxYearSanitize<T extends keyof ProfileForm>(
  reg: UseFormRegisterReturn<T>,
): UseFormRegisterReturn<T> {
  return {
    ...reg,
    onChange: (e, ...rest) => {
      const ce = e as ChangeEvent<HTMLInputElement>;
      ce.target.value = sanitizeTaxYearString(ce.target.value);
      return reg.onChange(e, ...rest);
    },
  };
}

function taxpayerName(total: number): string {
  return `Taxpayer_${String(total + 1).padStart(5, "0")}`;
}

const WIZARD_STEPS = [
  "Personal",
  "Employment",
  "Income",
  "Assets",
  "Income sources",
  "Insurance & horizon",
] as const;

const INCOME_SOURCE_KIND_LABEL: Record<string, string> = {
  employment: "Employment / salary",
  business: "Business",
  rental: "Rental",
  interest: "Interest",
  dividend: "Dividend",
  capital_gain: "Capital gain",
  other: "Other",
};

const STEP_FIELDS: (keyof ProfileForm)[][] = [
  [
    "full_name",
    "age_band",
    "gender",
    "marital_status",
    "residency_status",
    "nationality",
    "province",
    "dependents",
  ],
  ["occupation", "employment_type", "employer_sector", "years_employed"],
  ["gross_monthly_income", "annual_bonus_lkr", "monthly_expenses", "monthly_debt_service"],
  [
    "liquid_savings",
    "existing_investments",
    "total_debt",
    "epf_balance",
    "etf_balance",
    "vehicle_value",
    "property_value",
  ],
  ["income_sources"],
  [
    "life_insurance_premium_annual",
    "home_loan_interest_annual",
    "donations_annual",
    "health_insurance",
    "risk_tolerance",
    "investment_horizon_years",
    "retirement_age_target",
    "tax_year",
  ],
];

const defaultValues: ProfileForm = {
  full_name: taxpayerName(0),
  age_band: "" as ProfileForm["age_band"],
  gender: "" as ProfileForm["gender"],
  province: "" as ProfileForm["province"],
  marital_status: "" as ProfileForm["marital_status"],
  residency_status: "resident",
  nationality: "",
  occupation: "" as ProfileForm["occupation"],
  employment_type: "" as ProfileForm["employment_type"],
  employer_sector: "" as ProfileForm["employer_sector"],
  dependents: "",
  years_employed: "",
  gross_monthly_income: "",
  annual_bonus_lkr: "0",
  monthly_expenses: "",
  monthly_debt_service: "",
  liquid_savings: "",
  existing_investments: "",
  total_debt: "",
  epf_balance: "",
  etf_balance: "",
  vehicle_value: "0",
  property_value: "0",
  health_insurance: false,
  life_insurance_premium_annual: "",
  home_loan_interest_annual: "",
  donations_annual: "",
  risk_tolerance: "" as ProfileForm["risk_tolerance"],
  investment_horizon_years: "",
  retirement_age_target: "60",
  tax_year: "",
  income_sources: [{ kind: "employment", monthly_amount: "", is_taxable: true }],
};

function formatLkr(value: string | number): string {
  const num = typeof value === "string" ? Number(value) : value;
  if (Number.isNaN(num)) return String(value);
  return new Intl.NumberFormat("en-LK", {
    style: "currency",
    currency: "LKR",
    maximumFractionDigits: 0,
  }).format(num);
}

function formatPct(v: number): string {
  return `${(v * 100).toFixed(2)}%`;
}

function ageBandFromYears(age: number): string {
  if (age <= 24) return "18-24";
  if (age <= 29) return "25-29";
  if (age <= 34) return "30-34";
  if (age <= 39) return "35-39";
  if (age <= 44) return "40-44";
  if (age <= 49) return "45-49";
  if (age <= 54) return "50-54";
  if (age <= 59) return "55-59";
  if (age <= 64) return "60-64";
  if (age <= 70) return "65-70";
  return "70+";
}

export function ProfilePage() {
  const queryClient = useQueryClient();
  const setActiveProfileId = useDashboardStore((s) => s.setActiveProfileId);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [previewId, setPreviewId] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [step, setStep] = useState(0);

  const form = useForm<ProfileForm, unknown, ProfileFormOutput>({
    resolver: zodResolver(profileSchema),
    defaultValues,
  });
  const {
    register,
    handleSubmit,
    control,
    formState: { errors, isSubmitting, dirtyFields },
    reset,
    setValue,
  } = form;

  const incomeSources = useFieldArray({ control, name: "income_sources" });

  const profilesQuery = useQuery({
    queryKey: ["profiles", page],
    queryFn: () => listProfiles({ page, page_size: 10 }),
  });

  const countQuery = useQuery({
    queryKey: ["profiles-count"],
    queryFn: () => listProfiles({ page: 1, page_size: 1 }),
    staleTime: 0,
  });

  useEffect(() => {
    if (countQuery.data !== undefined && !dirtyFields.full_name) {
      setValue("full_name", taxpayerName(countQuery.data.total));
    }
  }, [countQuery.data, dirtyFields.full_name, setValue]);

  const featuresQuery = useQuery({
    queryKey: ["profile-features", selectedId],
    queryFn: () => getProfileFeatures(selectedId!),
    enabled: !!selectedId,
  });

  const previewQuery = useQuery({
    queryKey: ["profile-preview", previewId],
    queryFn: () => getProfile(previewId!),
    enabled: !!previewId,
  });

  const createMutation = useMutation({
    mutationFn: (payload: FinancialProfileCreate) => createProfile(payload),
    onSuccess: async (created) => {
      await queryClient.invalidateQueries({ queryKey: ["profiles"] });
      await queryClient.invalidateQueries({ queryKey: ["profiles-count"] });
      setSelectedId(created.id);
      setActiveProfileId(created.id);
      setStep(0);
      reset(defaultValues);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => deleteProfile(id),
    onSuccess: async (_, id) => {
      await queryClient.invalidateQueries({ queryKey: ["profiles"] });
      await queryClient.invalidateQueries({ queryKey: ["profiles-count"] });
      if (selectedId === id) setSelectedId(null);
    },
  });

  const overrideMutation = useMutation({
    mutationFn: ({ flag, value }: { flag: string; value: boolean | null }) =>
      setEligibilityOverride(selectedId!, flag, value),
    onSuccess: (updated) => {
      queryClient.setQueryData(["profile-features", selectedId], updated);
    },
  });

  const onSubmit = (values: ProfileFormOutput) => {
    const payload: FinancialProfileCreate = {
      ...values,
      income_sources: values.income_sources.map((s) => ({
        kind: s.kind,
        monthly_amount: s.monthly_amount,
        currency: "LKR",
        is_taxable: s.is_taxable,
      })),
    };
    createMutation.mutate(payload);
  };

  return (
    <div className="space-y-6">
      <PageHeader icon={UserRound} title="Financial profiles" />

      <div className="grid gap-6 lg:grid-cols-[1.1fr_0.9fr]">
        <Card className="border-t-4 border-t-primary/70">
          <form onSubmit={handleSubmit(onSubmit)}>
            <CardHeader>
              <CardTitle>Create profile</CardTitle>
              <CardDescription>
                Step {step + 1} of {WIZARD_STEPS.length} — all amounts in LKR.
              </CardDescription>
            </CardHeader>

            <CardContent className="space-y-6">
              <WizardNav
                steps={[...WIZARD_STEPS]}
                current={step}
                onStepClick={(i) => setStep(i)}
              />

              {step === 0 && (
              <Section title="Personal">
                <Field label="Full name" error={errors.full_name?.message}>
                  <Input {...register("full_name")} placeholder="Enter full name" autoComplete="off" />
                </Field>
                <Field label="Age band" error={errors.age_band?.message}>
                  <Select {...register("age_band")} defaultValue="">
                    <option value="" disabled>Select age band</option>
                    {AGE_BANDS.map((b) => (
                      <option key={b} value={b}>{b}</option>
                    ))}
                  </Select>
                </Field>
                <Field label="Gender" error={errors.gender?.message}>
                  <Select {...register("gender")} defaultValue="">
                    <option value="" disabled>Select gender</option>
                    <option value="male">Male</option>
                    <option value="female">Female</option>
                    <option value="other">Other</option>
                  </Select>
                </Field>
                <Field label="Marital status" error={errors.marital_status?.message}>
                  <Select {...register("marital_status")} defaultValue="">
                    <option value="" disabled>Select marital status</option>
                    <option value="single">Single</option>
                    <option value="married">Married</option>
                    <option value="divorced">Divorced</option>
                    <option value="widowed">Widowed</option>
                  </Select>
                </Field>
                <Field label="Province" error={errors.province?.message}>
                  <Select {...register("province")} defaultValue="">
                    <option value="" disabled>Select province</option>
                    {SL_PROVINCES.map((p) => (
                      <option key={p} value={p}>{p}</option>
                    ))}
                  </Select>
                </Field>
                <Field label="Dependents" error={errors.dependents?.message}>
                  <Input
                    type="text"
                    inputMode="numeric"
                    autoComplete="off"
                    {...withIntegerSanitize(register("dependents"))}
                  />
                </Field>
                <Field
                  label="Residency status"
                  error={errors.residency_status?.message}
                >
                  <Select {...register("residency_status")} defaultValue="resident">
                    <option value="resident">Resident</option>
                    <option value="non_resident">Non-resident</option>
                    <option value="dual">Dual resident</option>
                  </Select>
                </Field>
                <Field label="Nationality (optional)" error={errors.nationality?.message}>
                  <Input
                    {...register("nationality")}
                    placeholder="e.g. Sri Lankan"
                    autoComplete="off"
                  />
                </Field>
              </Section>
              )}

              {step === 1 && (
              <Section title="Employment">
                <Field label="Occupation" error={errors.occupation?.message}>
                  <Select {...register("occupation")} defaultValue="">
                    <option value="" disabled>Select occupation</option>
                    <option value="employee">Employee</option>
                    <option value="self_employed">Self-employed</option>
                    <option value="business_owner">Business owner</option>
                    <option value="investor">Investor</option>
                    <option value="professional">Professional</option>
                    <option value="other">Other</option>
                  </Select>
                </Field>
                <Field label="Years employed" error={errors.years_employed?.message}>
                  <Input
                    type="text"
                    inputMode="numeric"
                    autoComplete="off"
                    {...withIntegerSanitize(register("years_employed"))}
                  />
                </Field>
                <Field label="Employment type" error={errors.employment_type?.message}>
                  <Select {...register("employment_type")} defaultValue="">
                    <option value="" disabled>Select employment type</option>
                    <option value="permanent">Permanent</option>
                    <option value="contract">Contract</option>
                    <option value="part_time">Part-time</option>
                    <option value="freelance">Freelance</option>
                    <option value="unemployed">Unemployed</option>
                  </Select>
                </Field>
                <Field label="Employer sector" error={errors.employer_sector?.message}>
                  <Select {...register("employer_sector")} defaultValue="">
                    <option value="" disabled>Select employer sector</option>
                    <option value="private">Private</option>
                    <option value="public">Public / government</option>
                    <option value="ngo">NGO</option>
                    <option value="self_employed">Self-employed</option>
                  </Select>
                </Field>
              </Section>
              )}

              {step === 2 && (
              <Section title="Income & expenses (monthly LKR)">
                <Field label="Gross monthly income" error={errors.gross_monthly_income?.message}>
                  <Input
                    type="text"
                    inputMode="decimal"
                    autoComplete="off"
                    {...withDecimalSanitize(register("gross_monthly_income"))}
                  />
                </Field>
                <Field
                  label="Annual bonus (LKR)"
                  error={errors.annual_bonus_lkr?.message}
                >
                  <Input
                    type="text"
                    inputMode="decimal"
                    autoComplete="off"
                    {...withDecimalSanitize(register("annual_bonus_lkr"))}
                  />
                </Field>
                <Field label="Monthly expenses" error={errors.monthly_expenses?.message}>
                  <Input
                    type="text"
                    inputMode="decimal"
                    autoComplete="off"
                    {...withDecimalSanitize(register("monthly_expenses"))}
                  />
                </Field>
                <Field label="Monthly debt service" error={errors.monthly_debt_service?.message}>
                  <Input
                    type="text"
                    inputMode="decimal"
                    autoComplete="off"
                    {...withDecimalSanitize(register("monthly_debt_service"))}
                  />
                </Field>
              </Section>
              )}

              {step === 3 && (
              <Section title="Assets & liabilities (LKR)">
                <Field label="Liquid savings" error={errors.liquid_savings?.message}>
                  <Input
                    type="text"
                    inputMode="decimal"
                    autoComplete="off"
                    {...withDecimalSanitize(register("liquid_savings"))}
                  />
                </Field>
                <Field label="Existing investments" error={errors.existing_investments?.message}>
                  <Input
                    type="text"
                    inputMode="decimal"
                    autoComplete="off"
                    {...withDecimalSanitize(register("existing_investments"))}
                  />
                </Field>
                <Field label="Total debt" error={errors.total_debt?.message}>
                  <Input
                    type="text"
                    inputMode="decimal"
                    autoComplete="off"
                    {...withDecimalSanitize(register("total_debt"))}
                  />
                </Field>
                <Field label="EPF balance" error={errors.epf_balance?.message}>
                  <Input
                    type="text"
                    inputMode="decimal"
                    autoComplete="off"
                    {...withDecimalSanitize(register("epf_balance"))}
                  />
                </Field>
                <Field label="ETF balance" error={errors.etf_balance?.message}>
                  <Input
                    type="text"
                    inputMode="decimal"
                    autoComplete="off"
                    {...withDecimalSanitize(register("etf_balance"))}
                  />
                </Field>
                <Field label="Vehicle value" error={errors.vehicle_value?.message}>
                  <Input
                    type="text"
                    inputMode="decimal"
                    autoComplete="off"
                    {...withDecimalSanitize(register("vehicle_value"))}
                  />
                </Field>
                <Field label="Property value" error={errors.property_value?.message}>
                  <Input
                    type="text"
                    inputMode="decimal"
                    autoComplete="off"
                    {...withDecimalSanitize(register("property_value"))}
                  />
                </Field>
              </Section>
              )}

              {step === 4 && (
              <Section title="Income sources">
                <div className="col-span-full space-y-3">
                  <p className="text-sm text-muted-foreground">
                    List every income source for this taxpayer (salary, rental, dividends,
                    interest, etc.) so mixed income can be represented accurately.
                  </p>
                  {errors.income_sources?.root?.message && (
                    <div className="text-xs text-destructive">
                      {errors.income_sources.root.message}
                    </div>
                  )}
                  {incomeSources.fields.map((field, index) => (
                    <div
                      key={field.id}
                      className="grid gap-3 rounded-lg border p-3 sm:grid-cols-[1.2fr_1fr_auto_auto]"
                    >
                      <Field
                        label="Kind"
                        error={errors.income_sources?.[index]?.kind?.message}
                      >
                        <Select
                          {...register(`income_sources.${index}.kind`)}
                          defaultValue={field.kind}
                        >
                          {Object.entries(INCOME_SOURCE_KIND_LABEL).map(([k, label]) => (
                            <option key={k} value={k}>{label}</option>
                          ))}
                        </Select>
                      </Field>
                      <Field
                        label="Monthly amount (LKR)"
                        error={errors.income_sources?.[index]?.monthly_amount?.message}
                      >
                        <Input
                          type="text"
                          inputMode="decimal"
                          autoComplete="off"
                          {...withDecimalSanitize(register(`income_sources.${index}.monthly_amount`))}
                        />
                      </Field>
                      <div className="flex items-center gap-2 pt-6">
                        <Checkbox
                          id={`income_sources.${index}.is_taxable`}
                          {...register(`income_sources.${index}.is_taxable`)}
                        />
                        <Label htmlFor={`income_sources.${index}.is_taxable`}>Taxable</Label>
                      </div>
                      <div className="flex items-end justify-end pb-1">
                        <Button
                          type="button"
                          size="icon"
                          variant="ghost"
                          disabled={incomeSources.fields.length <= 1}
                          onClick={() => incomeSources.remove(index)}
                        >
                          <Trash2 className="h-4 w-4 text-muted-foreground" />
                        </Button>
                      </div>
                    </div>
                  ))}
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() =>
                      incomeSources.append({ kind: "other", monthly_amount: "", is_taxable: true })
                    }
                  >
                    <Plus className="h-4 w-4" />
                    Add income source
                  </Button>
                </div>
              </Section>
              )}

              {step === 5 && (
              <>
              <Section title="Insurance & reliefs (annual LKR)">
                <Field label="Life insurance premium" error={errors.life_insurance_premium_annual?.message}>
                  <Input
                    type="text"
                    inputMode="decimal"
                    autoComplete="off"
                    {...withDecimalSanitize(register("life_insurance_premium_annual"))}
                  />
                </Field>
                <Field label="Home loan interest" error={errors.home_loan_interest_annual?.message}>
                  <Input
                    type="text"
                    inputMode="decimal"
                    autoComplete="off"
                    {...withDecimalSanitize(register("home_loan_interest_annual"))}
                  />
                </Field>
                <Field label="Donations" error={errors.donations_annual?.message}>
                  <Input
                    type="text"
                    inputMode="decimal"
                    autoComplete="off"
                    {...withDecimalSanitize(register("donations_annual"))}
                  />
                </Field>
                <div className="flex items-center gap-2 pt-6">
                  <Checkbox id="health_insurance" {...register("health_insurance")} />
                  <Label htmlFor="health_insurance">Has health insurance</Label>
                </div>
              </Section>

              <Section title="Risk & horizon">
                <Field label="Risk tolerance" error={errors.risk_tolerance?.message}>
                  <Select {...register("risk_tolerance")} defaultValue="">
                    <option value="" disabled>Select risk tolerance</option>
                    <option value="low">Low</option>
                    <option value="medium">Medium</option>
                    <option value="high">High</option>
                  </Select>
                </Field>
                <Field label="Horizon (years)" error={errors.investment_horizon_years?.message}>
                  <Input
                    type="text"
                    inputMode="numeric"
                    autoComplete="off"
                    {...withIntegerSanitize(register("investment_horizon_years"))}
                  />
                </Field>
                <Field
                  label="Retirement age target"
                  error={errors.retirement_age_target?.message}
                >
                  <Input
                    type="text"
                    inputMode="numeric"
                    autoComplete="off"
                    {...withIntegerSanitize(register("retirement_age_target"))}
                  />
                </Field>
                <Field label="Tax year" error={errors.tax_year?.message}>
                  <Input
                    type="text"
                    inputMode="numeric"
                    autoComplete="off"
                    placeholder="2026_27"
                    {...withTaxYearSanitize(register("tax_year"))}
                  />
                </Field>
              </Section>
              </>
              )}

              {createMutation.isError && (
                <div className="rounded-md border border-destructive/40 bg-destructive/5 p-3 text-sm text-destructive">
                  {(createMutation.error as Error).message}
                </div>
              )}
            </CardContent>

            <CardFooter className="flex flex-wrap justify-between gap-2 border-t pt-4">
              <Button
                type="button"
                variant="outline"
                onClick={() => {
                  reset(defaultValues);
                  setStep(0);
                }}
                disabled={isSubmitting}
              >
                Reset
              </Button>
              <div className="flex gap-2">
                {step > 0 && (
                  <Button type="button" variant="outline" onClick={() => setStep((s) => s - 1)}>
                    Back
                  </Button>
                )}
                {step < WIZARD_STEPS.length - 1 ? (
                  <Button
                    type="button"
                    onClick={async () => {
                      const ok = await form.trigger(STEP_FIELDS[step]);
                      if (ok) setStep((s) => Math.min(s + 1, WIZARD_STEPS.length - 1));
                    }}
                  >
                    Next
                  </Button>
                ) : (
                  <Button type="submit" disabled={isSubmitting || createMutation.isPending}>
                    {createMutation.isPending && <Loader2 className="h-4 w-4 animate-spin" />}
                    Create profile
                  </Button>
                )}
              </div>
            </CardFooter>
          </form>
        </Card>

        <div className="space-y-6">
          <DerivedFeaturesCard
            isLoading={featuresQuery.isFetching}
            features={featuresQuery.data}
            error={(featuresQuery.error as Error | null)?.message}
            placeholder={!selectedId}
            onToggleFlag={(flag, nextValue) =>
              overrideMutation.mutate({ flag, value: nextValue })
            }
            pendingFlag={overrideMutation.isPending ? overrideMutation.variables?.flag : undefined}
          />

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0">
              <div>
                <CardTitle>Recent profiles</CardTitle>
                <CardDescription>
                  {profilesQuery.data
                    ? `${profilesQuery.data.total} total · page ${page}`
                    : "Loading…"}
                </CardDescription>
              </div>
              <Button
                size="icon"
                variant="ghost"
                onClick={() => profilesQuery.refetch()}
                disabled={profilesQuery.isFetching}
              >
                <RefreshCw className={profilesQuery.isFetching ? "h-4 w-4 animate-spin" : "h-4 w-4"} />
              </Button>
            </CardHeader>
            <CardContent className="space-y-2">
              {profilesQuery.isError && (
                <div className="text-sm text-destructive">
                  {(profilesQuery.error as Error).message}
                </div>
              )}
              {profilesQuery.data?.items.length === 0 && (
                <div className="text-sm text-muted-foreground">
                  No profiles yet. Create one with the form on the left.
                </div>
              )}
              <ul className="divide-y">
                {profilesQuery.data?.items.map((p) => (
                  <li
                    key={p.id}
                    className={`flex items-center justify-between gap-3 py-3 cursor-pointer rounded-md px-2 ${
                      selectedId === p.id ? "bg-accent/50" : "hover:bg-accent/30"
                    }`}
                    onClick={() => {
                      setSelectedId(p.id);
                      setActiveProfileId(p.id);
                      setPreviewId(p.id);
                    }}
                  >
                    <div className="min-w-0 flex-1">
                      <div className="truncate text-sm font-medium">{p.full_name}</div>
                      <div className="truncate text-xs text-muted-foreground">
                        {p.occupation} · {p.district} · {formatLkr(p.gross_monthly_income)}
                        /mo
                      </div>
                    </div>
                    <Button
                      size="icon"
                      variant="ghost"
                      onClick={(e) => {
                        e.stopPropagation();
                        if (confirm(`Delete ${p.full_name}?`)) {
                          deleteMutation.mutate(p.id);
                        }
                      }}
                    >
                      <Trash2 className="h-4 w-4 text-muted-foreground" />
                    </Button>
                  </li>
                ))}
              </ul>
            </CardContent>
            {profilesQuery.data && profilesQuery.data.total > profilesQuery.data.page_size && (
              <CardFooter className="flex justify-between border-t pt-4">
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  disabled={page === 1}
                >
                  Previous
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => setPage((p) => p + 1)}
                  disabled={
                    page * profilesQuery.data.page_size >= profilesQuery.data.total
                  }
                >
                  Next
                </Button>
              </CardFooter>
            )}
          </Card>
        </div>
      </div>

      {previewId && (
        <ProfilePreviewModal
          profile={previewQuery.data}
          isLoading={previewQuery.isFetching}
          error={(previewQuery.error as Error | null)?.message}
          onClose={() => setPreviewId(null)}
        />
      )}
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <div className="mb-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
        {title}
      </div>
      <div className="grid gap-4 sm:grid-cols-2">{children}</div>
    </div>
  );
}

function Field({
  label,
  error,
  children,
}: {
  label: string;
  error?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-1.5">
      <Label>{label}</Label>
      {children}
      {error && <div className="text-xs text-destructive">{error}</div>}
    </div>
  );
}

interface FlagMeta {
  label: string;
  description: string;
  group: string;
}

const FLAG_META: Record<string, FlagMeta> = {
  above_tax_threshold: {
    label: "Above tax threshold",
    description: "Annual taxable income exceeds the tax-free allowance.",
    group: "Tax & income",
  },
  has_disposable_income: {
    label: "Has disposable income",
    description: "Income exceeds expenses, debt service, and tax each month.",
    group: "Tax & income",
  },
  high_debt_to_income: {
    label: "High debt-to-income",
    description: "Total debt is more than 40% of annual income.",
    group: "Tax & income",
  },
  has_employer_provident: {
    label: "Has employer provident fund",
    description: "Has an EPF balance, or is employed and accruing one.",
    group: "Employment & retirement",
  },
  is_retirement_eligible: {
    label: "Retirement eligible",
    description: "Aged 50 or over.",
    group: "Employment & retirement",
  },
  has_long_investment_horizon: {
    label: "Long investment horizon",
    description: "Plans to stay invested for 10+ years.",
    group: "Employment & retirement",
  },
  has_dependents: {
    label: "Has dependents",
    description: "Supports one or more dependents.",
    group: "Family",
  },
  has_health_insurance: {
    label: "Has health insurance",
    description: "Covered by a health insurance policy.",
    group: "Insurance & protection",
  },
  has_life_insurance: {
    label: "Has life insurance",
    description: "Pays an annual life insurance premium.",
    group: "Insurance & protection",
  },
  has_home_loan: {
    label: "Has home loan",
    description: "Pays annual home loan interest.",
    group: "Housing & debt",
  },
  has_liquidity_buffer: {
    label: "Has liquidity buffer",
    description: "Liquid savings cover 3+ months of expenses.",
    group: "Savings & investments",
  },
  has_etf_investment: {
    label: "Has ETF investment",
    description: "Holds a non-zero ETF balance.",
    group: "Savings & investments",
  },
  has_existing_investments: {
    label: "Has existing investments",
    description: "Holds investments outside EPF/ETF.",
    group: "Savings & investments",
  },
  has_donations: {
    label: "Makes donations",
    description: "Claims annual charitable donations.",
    group: "Giving",
  },
  has_vehicle: {
    label: "Owns a vehicle",
    description: "Holds a non-zero vehicle value.",
    group: "Savings & investments",
  },
  has_property: {
    label: "Owns property",
    description: "Holds a non-zero property value.",
    group: "Savings & investments",
  },
};

const FLAG_GROUP_ORDER = [
  "Tax & income",
  "Employment & retirement",
  "Family",
  "Insurance & protection",
  "Housing & debt",
  "Savings & investments",
  "Giving",
];

function flagMeta(key: string): FlagMeta {
  return FLAG_META[key] ?? { label: titleCase(key), description: "", group: "Other" };
}

function DerivedFeaturesCard({
  features,
  isLoading,
  error,
  placeholder,
  onToggleFlag,
  pendingFlag,
}: {
  features?: import("../types").DerivedFeatures;
  isLoading: boolean;
  error?: string;
  placeholder: boolean;
  onToggleFlag: (flag: string, nextValue: boolean | null) => void;
  pendingFlag?: string;
}) {
  if (placeholder) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Derived features</CardTitle>
          <CardDescription>
            Select a profile (or create a new one) to see disposable income,
            baseline tax liability, savings rate, and eligibility flags.
          </CardDescription>
        </CardHeader>
      </Card>
    );
  }

  const groups = features
    ? FLAG_GROUP_ORDER.map((group) => ({
        group,
        flags: Object.entries(features.eligibility_flags).filter(
          ([k]) => flagMeta(k).group === group,
        ),
      })).filter((g) => g.flags.length > 0)
    : [];

  return (
    <Card>
      <CardHeader>
        <CardTitle>Derived features</CardTitle>
        <CardDescription>Computed by the rules engine in the backend.</CardDescription>
      </CardHeader>
      <CardContent>
        {isLoading && <Loader2 className="h-4 w-4 animate-spin" />}
        {error && <div className="text-sm text-destructive">{error}</div>}
        {features && (
          <div className="space-y-5">
            <p className="rounded-lg border bg-muted/30 p-3 text-sm text-muted-foreground">
              At {formatPct(features.effective_tax_rate)} effective tax, this profile keeps{" "}
              <span className="font-medium text-foreground">
                {formatLkr(features.disposable_income_monthly)}
              </span>{" "}
              disposable per month — a {formatPct(features.savings_rate)} savings rate with{" "}
              {features.liquidity_ratio.toFixed(1)} months of expenses in liquid savings.
            </p>

            <div className="grid grid-cols-2 gap-3 text-sm">
              <Stat label="Age band" value={ageBandFromYears(features.age_years)} />
              <Stat
                label="Annual taxable income"
                value={formatLkr(features.gross_annual_taxable_income)}
              />
              <Stat
                label="Baseline tax liability"
                value={formatLkr(features.baseline_tax_liability_annual)}
              />
              <Stat
                label="Effective tax rate"
                value={formatPct(features.effective_tax_rate)}
              />
              <Stat
                label="Disposable / month"
                value={formatLkr(features.disposable_income_monthly)}
              />
              <Stat label="Savings rate" value={formatPct(features.savings_rate)} />
              <Stat
                label="Debt-to-income"
                value={features.debt_to_income.toFixed(2)}
              />
              <Stat
                label="Liquidity (months)"
                value={features.liquidity_ratio.toFixed(1)}
              />
            </div>

            <div>
              <div className="mb-1 flex items-baseline justify-between">
                <div className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                  Eligibility flags
                </div>
                <div className="text-xs text-muted-foreground">Click a flag to pin it on/off</div>
              </div>
              <div className="space-y-3">
                {groups.map(({ group, flags }) => (
                  <div key={group}>
                    <div className="mb-1.5 text-[11px] font-medium text-muted-foreground">
                      {group}
                    </div>
                    <div className="flex flex-wrap gap-1.5">
                      {flags.map(([k, v]) => {
                        const meta = flagMeta(k);
                        const isOverridden = k in features.eligibility_overrides;
                        const isPending = pendingFlag === k;
                        return (
                          <span key={k} className="group relative inline-flex">
                            <button
                              type="button"
                              title={meta.description}
                              disabled={isPending}
                              onClick={() => onToggleFlag(k, !v)}
                              className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs transition-colors disabled:opacity-60 ${
                                v
                                  ? "border-emerald-300 bg-emerald-50 text-emerald-700 hover:bg-emerald-100 dark:border-emerald-700 dark:bg-emerald-950 dark:text-emerald-300"
                                  : "border-border bg-muted text-muted-foreground hover:bg-accent"
                              } ${isOverridden ? "ring-1 ring-offset-1 ring-primary/50" : ""}`}
                            >
                              {isPending ? (
                                <Loader2 className="h-3 w-3 animate-spin" />
                              ) : (
                                <span>{v ? "✓" : "·"}</span>
                              )}
                              {meta.label}
                            </button>
                            {isOverridden && (
                              <button
                                type="button"
                                title="Reset to computed value"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  onToggleFlag(k, null);
                                }}
                                className="absolute -right-1.5 -top-1.5 hidden h-3.5 w-3.5 items-center justify-center rounded-full border bg-background text-[9px] leading-none text-muted-foreground hover:text-foreground group-hover:flex"
                              >
                                <X className="h-2.5 w-2.5" />
                              </button>
                            )}
                          </span>
                        );
                      })}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function ageFromDob(dob: string): number {
  const birth = new Date(dob);
  if (Number.isNaN(birth.getTime())) return NaN;
  const now = new Date();
  let age = now.getFullYear() - birth.getFullYear();
  const monthDiff = now.getMonth() - birth.getMonth();
  if (monthDiff < 0 || (monthDiff === 0 && now.getDate() < birth.getDate())) age -= 1;
  return age;
}

function formatDate(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString("en-LK", { year: "numeric", month: "short", day: "numeric" });
}

function titleCase(v: string): string {
  return v.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

function initials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "?";
  if (parts.length === 1) return parts[0]!.slice(0, 2).toUpperCase();
  return `${parts[0]![0]}${parts[parts.length - 1]![0]}`.toUpperCase();
}

const RISK_BADGE: Record<string, string> = {
  low: "border-emerald-300 bg-emerald-50 text-emerald-700 dark:border-emerald-700 dark:bg-emerald-950 dark:text-emerald-300",
  medium:
    "border-amber-300 bg-amber-50 text-amber-700 dark:border-amber-700 dark:bg-amber-950 dark:text-amber-300",
  high: "border-rose-300 bg-rose-50 text-rose-700 dark:border-rose-700 dark:bg-rose-950 dark:text-rose-300",
};

function ProfilePreviewModal({
  profile,
  isLoading,
  error,
  onClose,
}: {
  profile?: import("../types").FinancialProfile;
  isLoading: boolean;
  error?: string;
  onClose: () => void;
}) {
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 backdrop-blur-sm"
      onClick={onClose}
    >
      <Card
        className="flex max-h-[88vh] w-full max-w-2xl flex-col overflow-hidden p-0"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="relative shrink-0 overflow-hidden bg-gradient-to-br from-primary/90 to-primary px-6 py-6 text-primary-foreground">
          <Button
            size="icon"
            variant="ghost"
            onClick={onClose}
            className="absolute right-3 top-3 text-primary-foreground hover:bg-white/15 hover:text-primary-foreground"
          >
            <X className="h-4 w-4" />
          </Button>
          <div className="flex items-center gap-4">
            <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-full bg-white/15 text-lg font-semibold ring-2 ring-white/30">
              {profile ? initials(profile.full_name) : "…"}
            </div>
            <div className="min-w-0">
              <div className="truncate text-xl font-semibold">
                {profile?.full_name ?? "Loading profile…"}
              </div>
              {profile && (
                <div className="mt-1 flex flex-wrap items-center gap-1.5 text-sm text-primary-foreground/80">
                  <span>{titleCase(profile.occupation)}</span>
                  <span>·</span>
                  <span>{profile.district}</span>
                  <span>·</span>
                  <span>{ageFromDob(profile.date_of_birth)} yrs</span>
                </div>
              )}
            </div>
          </div>
        </div>

        <CardContent className="flex-1 space-y-6 overflow-y-auto p-6">
          {isLoading && (
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" /> Loading profile details…
            </div>
          )}
          {error && <div className="text-sm text-destructive">{error}</div>}
          {profile && (
            <>
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                <HighlightTile
                  label="Monthly income"
                  value={formatLkr(profile.gross_monthly_income)}
                  accent="emerald"
                />
                <HighlightTile
                  label="Monthly expenses"
                  value={formatLkr(profile.monthly_expenses)}
                  accent="rose"
                />
                <HighlightTile
                  label="Liquid savings"
                  value={formatLkr(profile.liquid_savings)}
                  accent="sky"
                />
                <HighlightTile
                  label="Total debt"
                  value={formatLkr(profile.total_debt)}
                  accent="amber"
                />
              </div>

              <PreviewSection title="Personal" icon={UserRound}>
                <Stat label="Date of birth" value={formatDate(profile.date_of_birth)} />
                <Stat label="Age" value={`${ageFromDob(profile.date_of_birth)}`} />
                <Stat label="Gender" value={titleCase(profile.gender)} />
                <Stat label="Marital status" value={titleCase(profile.marital_status)} />
                <Stat label="District" value={profile.district} />
                <Stat label="Dependents" value={`${profile.dependents}`} />
                <Stat label="Residency status" value={titleCase(profile.residency_status)} />
                <Stat label="Nationality" value={profile.nationality || "—"} />
              </PreviewSection>

              <PreviewSection title="Employment" icon={Briefcase}>
                <Stat label="Occupation" value={titleCase(profile.occupation)} />
                <Stat label="Years employed" value={`${profile.years_employed}`} />
                <Stat label="Employment type" value={titleCase(profile.employment_type)} />
                <Stat label="Employer sector" value={titleCase(profile.employer_sector)} />
              </PreviewSection>

              <PreviewSection title="Income & expenses (monthly)" icon={Wallet}>
                <Stat label="Gross monthly income" value={formatLkr(profile.gross_monthly_income)} />
                <Stat label="Annual bonus" value={formatLkr(profile.annual_bonus_lkr)} />
                <Stat label="Monthly expenses" value={formatLkr(profile.monthly_expenses)} />
                <Stat label="Monthly debt service" value={formatLkr(profile.monthly_debt_service)} />
              </PreviewSection>

              <PreviewSection title="Assets & liabilities" icon={PiggyBank}>
                <Stat label="Liquid savings" value={formatLkr(profile.liquid_savings)} />
                <Stat label="Existing investments" value={formatLkr(profile.existing_investments)} />
                <Stat label="Total debt" value={formatLkr(profile.total_debt)} />
                <Stat label="EPF balance" value={formatLkr(profile.epf_balance)} />
                <Stat label="ETF balance" value={formatLkr(profile.etf_balance)} />
                <Stat label="Vehicle value" value={formatLkr(profile.vehicle_value)} />
                <Stat label="Property value" value={formatLkr(profile.property_value)} />
              </PreviewSection>

              <PreviewSection title="Insurance & reliefs (annual)" icon={ShieldCheck}>
                <Stat
                  label="Health insurance"
                  value={profile.health_insurance ? "Yes" : "No"}
                />
                <Stat
                  label="Life insurance premium"
                  value={formatLkr(profile.life_insurance_premium_annual)}
                />
                <Stat
                  label="Home loan interest"
                  value={formatLkr(profile.home_loan_interest_annual)}
                />
                <Stat label="Donations" value={formatLkr(profile.donations_annual)} />
              </PreviewSection>

              <PreviewSection title="Risk & horizon" icon={TrendingUp}>
                <div className="space-y-1">
                  <div className="text-xs text-muted-foreground">Risk tolerance</div>
                  <span
                    className={`inline-flex rounded-full border px-2 py-0.5 text-xs font-medium ${
                      RISK_BADGE[profile.risk_tolerance] ?? RISK_BADGE.medium
                    }`}
                  >
                    {titleCase(profile.risk_tolerance)}
                  </span>
                </div>
                <Stat
                  label="Investment horizon"
                  value={`${profile.investment_horizon_years} yrs`}
                />
                <Stat
                  label="Retirement age target"
                  value={`${profile.retirement_age_target}`}
                />
                <Stat label="Tax year" value={profile.tax_year.replace("_", "/")} />
              </PreviewSection>

              {profile.income_sources.length > 0 && (
                <PreviewSection title="Income sources" icon={Landmark}>
                  <div className="col-span-full space-y-1.5">
                    {profile.income_sources.map((s, i) => (
                      <div
                        key={i}
                        className="flex items-center justify-between rounded-lg border bg-muted/30 px-3 py-2 text-sm"
                      >
                        <span className="font-medium">{titleCase(s.kind)}</span>
                        <span className="text-muted-foreground">
                          {formatLkr(s.monthly_amount)}/mo
                          {s.is_taxable === false && " · non-taxable"}
                        </span>
                      </div>
                    ))}
                  </div>
                </PreviewSection>
              )}
            </>
          )}
        </CardContent>
        <CardFooter className="shrink-0 border-t bg-muted/20 py-3">
          <Button variant="outline" onClick={onClose} className="ml-auto">
            Close
          </Button>
        </CardFooter>
      </Card>
    </div>
  );
}

const TILE_ACCENT: Record<string, string> = {
  emerald: "border-emerald-200 bg-emerald-50 text-black",
  rose: "border-rose-200 bg-rose-50 text-black",
  sky: "border-sky-200 bg-sky-50 text-black",
  amber: "border-amber-200 bg-amber-50 text-black",
};

function HighlightTile({
  label,
  value,
  accent,
}: {
  label: string;
  value: string;
  accent: keyof typeof TILE_ACCENT;
}) {
  return (
    <div className={`rounded-lg border px-3 py-2.5 ${TILE_ACCENT[accent]}`}>
      <div className="text-[11px] font-medium uppercase tracking-wide opacity-80">{label}</div>
      <div className="mt-0.5 truncate text-sm font-semibold">{value}</div>
    </div>
  );
}

function PreviewSection({
  title,
  icon: Icon,
  children,
}: {
  title: string;
  icon: React.ComponentType<{ className?: string }>;
  children: React.ReactNode;
}) {
  return (
    <div className="rounded-lg border p-4">
      <div className="mb-3 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
        <Icon className="h-3.5 w-3.5" />
        {title}
      </div>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">{children}</div>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className="font-medium">{value}</div>
    </div>
  );
}
