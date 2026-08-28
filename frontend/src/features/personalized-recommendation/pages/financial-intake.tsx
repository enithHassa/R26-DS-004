import type { ChangeEvent } from "react";
import { useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import { useMutation } from "@tanstack/react-query";
import { useFieldArray, useForm } from "react-hook-form";
import type { UseFormRegisterReturn } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Loader2, Trash2, Plus, ClipboardList, LogOut } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";

import { createProfile } from "../api/profiles";
import { WizardNav } from "../components/wizard-nav";
import { useUserSessionStore } from "../store/user-session-store";
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

const intakeSchema = z.object({
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

type IntakeForm = z.input<typeof intakeSchema>;
type IntakeFormOutput = z.output<typeof intakeSchema>;

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

function withTaxYearSanitize<T extends keyof IntakeForm>(
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

const STEP_FIELDS: (keyof IntakeForm)[][] = [
  ["full_name", "age_band", "gender", "marital_status", "residency_status", "nationality", "province", "dependents"],
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

function defaultValuesFor(fullName: string): IntakeForm {
  return {
    full_name: fullName,
    age_band: "" as IntakeForm["age_band"],
    gender: "" as IntakeForm["gender"],
    province: "" as IntakeForm["province"],
    marital_status: "" as IntakeForm["marital_status"],
    residency_status: "resident",
    nationality: "",
    occupation: "" as IntakeForm["occupation"],
    employment_type: "" as IntakeForm["employment_type"],
    employer_sector: "" as IntakeForm["employer_sector"],
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
    risk_tolerance: "" as IntakeForm["risk_tolerance"],
    investment_horizon_years: "",
    retirement_age_target: "60",
    tax_year: "",
    income_sources: [{ kind: "employment", monthly_amount: "", is_taxable: true }],
  };
}

const DOT_GRID_BG =
  "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='40' height='40'%3E%3Ccircle cx='2' cy='2' r='1.4' fill='white' fill-opacity='0.14'/%3E%3C/svg%3E";

export function FinancialIntakePage() {
  const navigate = useNavigate();
  const isAuthenticated = useUserSessionStore((s) => s.isAuthenticated);
  const role = useUserSessionStore((s) => s.role);
  const userId = useUserSessionStore((s) => s.userId);
  const profileId = useUserSessionStore((s) => s.profileId);
  const fullName = useUserSessionStore((s) => s.fullName);
  const setProfileId = useUserSessionStore((s) => s.setProfileId);
  const logout = useUserSessionStore((s) => s.logout);
  const [step, setStep] = useState(0);

  const form = useForm<IntakeForm, unknown, IntakeFormOutput>({
    resolver: zodResolver(intakeSchema),
    defaultValues: defaultValuesFor(fullName ?? ""),
  });
  const {
    register,
    handleSubmit,
    control,
    formState: { errors, isSubmitting },
  } = form;

  const incomeSources = useFieldArray({ control, name: "income_sources" });

  const createMutation = useMutation({
    mutationFn: (values: IntakeFormOutput) => {
      const payload: FinancialProfileCreate = {
        ...values,
        income_sources: values.income_sources.map((s) => ({
          kind: s.kind,
          monthly_amount: s.monthly_amount,
          currency: "LKR",
          is_taxable: s.is_taxable,
        })),
      };
      return createProfile(payload, userId ?? undefined);
    },
    onSuccess: (created) => {
      setProfileId(created.id);
      // Behavioural questions come next, then the recommendations portal.
      navigate("/taxwise?habits=open", { replace: true });
    },
  });

  if (!isAuthenticated || role !== "taxpayer") {
    return <Navigate to="/login" replace />;
  }
  if (profileId) {
    return <Navigate to="/taxwise" replace />;
  }

  const isLastStep = step === WIZARD_STEPS.length - 1;

  const onSubmit = (values: IntakeFormOutput) => createMutation.mutate(values);

  return (
    <div
      className="relative flex min-h-screen items-center justify-center overflow-hidden px-4 py-10"
      style={{
        background:
          "radial-gradient(1200px circle at 15% 20%, color-mix(in srgb, var(--tax-accent) 55%, transparent) 0%, transparent 42%)," +
          "radial-gradient(1000px circle at 85% 75%, color-mix(in srgb, var(--primary) 65%, transparent) 0%, transparent 50%)," +
          "radial-gradient(800px circle at 50% 100%, color-mix(in srgb, var(--tax-accent) 30%, transparent) 0%, transparent 55%)," +
          "linear-gradient(160deg, #241419 0%, #150d10 55%, #1b1013 100%)",
      }}
    >
      <div
        className="pointer-events-none absolute inset-0 opacity-40"
        style={{ backgroundImage: `url("${DOT_GRID_BG}")`, backgroundSize: "40px 40px" }}
        aria-hidden
      />

      <div className="relative z-10 flex w-full max-w-2xl flex-col items-center">
        <div className="mb-6 flex flex-col items-center gap-2 text-center">
          <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-white/10 shadow-lg ring-1 ring-white/20 backdrop-blur-sm">
            <ClipboardList className="h-7 w-7 text-white" />
          </div>
          <div className="text-lg font-semibold tracking-tight text-white">
            {fullName ? `Welcome, ${fullName.split(" ")[0]}` : "Before we begin"}
          </div>
          <button
            type="button"
            onClick={() => {
              logout();
              navigate("/login", { replace: true });
            }}
            className="mt-1 inline-flex items-center gap-1.5 text-sm text-white/70 transition-colors hover:text-white"
          >
            <LogOut className="h-3.5 w-3.5" />
            Sign out and switch account
          </button>
        </div>

        <Card className="w-full border-white/10 bg-white/95 shadow-2xl backdrop-blur-md">
          <form onSubmit={handleSubmit(onSubmit)}>
            <CardHeader>
              <CardTitle>Tell us about your finances</CardTitle>
              <CardDescription>
                Step {step + 1} of {WIZARD_STEPS.length} — all amounts in LKR. This tailors your
                recommendations.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <WizardNav steps={[...WIZARD_STEPS]} current={step} onStepClick={setStep} />

              {step === 0 && (
                <Section title="Personal">
                  <Field label="Full name" error={errors.full_name?.message}>
                    <Input {...register("full_name")} autoComplete="off" />
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
                  <Field label="Residency status" error={errors.residency_status?.message}>
                    <Select {...register("residency_status")} defaultValue="resident">
                      <option value="resident">Resident</option>
                      <option value="non_resident">Non-resident</option>
                      <option value="dual">Dual resident</option>
                    </Select>
                  </Field>
                  <Field label="Nationality (optional)" error={errors.nationality?.message}>
                    <Input {...register("nationality")} placeholder="e.g. Sri Lankan" autoComplete="off" />
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
                  <Field label="Annual bonus (LKR)" error={errors.annual_bonus_lkr?.message}>
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
                      List every income source you have (salary, rental, dividends, interest, etc.).
                    </p>
                    {errors.income_sources?.root?.message && (
                      <div className="text-xs text-destructive">{errors.income_sources.root.message}</div>
                    )}
                    {incomeSources.fields.map((field, index) => (
                      <div
                        key={field.id}
                        className="grid gap-3 rounded-lg border p-3 sm:grid-cols-[1.2fr_1fr_auto_auto]"
                      >
                        <Field label="Kind" error={errors.income_sources?.[index]?.kind?.message}>
                          <Select {...register(`income_sources.${index}.kind`)} defaultValue={field.kind}>
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
                    <Field
                      label="Life insurance premium"
                      error={errors.life_insurance_premium_annual?.message}
                    >
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
                    <Field label="Retirement age target" error={errors.retirement_age_target?.message}>
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

            <div className="flex flex-wrap justify-end gap-2 border-t p-4">
              {step > 0 && (
                <Button type="button" variant="outline" onClick={() => setStep((s) => s - 1)}>
                  Back
                </Button>
              )}
              {!isLastStep ? (
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
                  Continue
                </Button>
              )}
            </div>
          </form>
        </Card>
      </div>
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
