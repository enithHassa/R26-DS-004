import { useState } from "react";
import type { ChangeEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import type { UseFormRegisterReturn } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Loader2, Trash2, RefreshCw } from "lucide-react";

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
  getProfileFeatures,
  listProfiles,
} from "../api/profiles";
import { SL_DISTRICTS, type FinancialProfileCreate } from "../types";

const decimalString = z
  .string()
  .min(1, "Required")
  .refine((v) => !Number.isNaN(Number(v)) && Number(v) >= 0, "Must be ≥ 0");

const profileSchema = z.object({
  full_name: z.string().min(1).max(200),
  date_of_birth: z.string().refine((v) => /^\d{4}-\d{2}-\d{2}$/.test(v), "Invalid date"),
  gender: z.enum(["male", "female", "other"]),
  district: z.string().min(1),
  marital_status: z.enum(["single", "married", "divorced", "widowed"]),
  occupation: z.enum([
    "employee",
    "self_employed",
    "business_owner",
    "investor",
    "professional",
    "other",
  ]),
  dependents: z.coerce.number().int().min(0).max(20),
  years_employed: z.coerce.number().int().min(0).max(60),
  gross_monthly_income: decimalString,
  monthly_expenses: decimalString,
  monthly_debt_service: decimalString,
  liquid_savings: decimalString,
  existing_investments: decimalString,
  total_debt: decimalString,
  epf_balance: decimalString,
  etf_balance: decimalString,
  health_insurance: z.boolean(),
  life_insurance_premium_annual: decimalString,
  home_loan_interest_annual: decimalString,
  donations_annual: decimalString,
  risk_tolerance: z.enum(["low", "medium", "high"]),
  investment_horizon_years: z.coerce.number().int().min(0).max(50),
  tax_year: z.string().regex(/^\d{4}_\d{2}$/),
});

type ProfileForm = z.infer<typeof profileSchema>;

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

function withIntegerSanitize<T extends keyof ProfileForm>(
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

function withDecimalSanitize<T extends keyof ProfileForm>(
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

const defaultValues: ProfileForm = {
  full_name: "Nuwan Perera",
  date_of_birth: "1990-04-15",
  gender: "male",
  district: "Colombo",
  marital_status: "married",
  occupation: "employee",
  dependents: 2,
  years_employed: 8,
  gross_monthly_income: "350000",
  monthly_expenses: "180000",
  monthly_debt_service: "45000",
  liquid_savings: "1200000",
  existing_investments: "850000",
  total_debt: "2400000",
  epf_balance: "950000",
  etf_balance: "180000",
  health_insurance: true,
  life_insurance_premium_annual: "60000",
  home_loan_interest_annual: "300000",
  donations_annual: "0",
  risk_tolerance: "medium",
  investment_horizon_years: 15,
  tax_year: "2024_25",
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

export function ProfilePage() {
  const queryClient = useQueryClient();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [page, setPage] = useState(1);

  const form = useForm<ProfileForm>({
    resolver: zodResolver(profileSchema),
    defaultValues,
  });
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
    reset,
  } = form;

  const profilesQuery = useQuery({
    queryKey: ["profiles", page],
    queryFn: () => listProfiles({ page, page_size: 10 }),
  });

  const featuresQuery = useQuery({
    queryKey: ["profile-features", selectedId],
    queryFn: () => getProfileFeatures(selectedId!),
    enabled: !!selectedId,
  });

  const createMutation = useMutation({
    mutationFn: (payload: FinancialProfileCreate) => createProfile(payload),
    onSuccess: (created) => {
      queryClient.invalidateQueries({ queryKey: ["profiles"] });
      setSelectedId(created.id);
      reset(defaultValues);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => deleteProfile(id),
    onSuccess: (_, id) => {
      queryClient.invalidateQueries({ queryKey: ["profiles"] });
      if (selectedId === id) setSelectedId(null);
    },
  });

  const onSubmit = (values: ProfileForm) => {
    const payload: FinancialProfileCreate = {
      ...values,
      income_sources: [
        {
          kind: values.occupation === "business_owner" ? "business" : "employment",
          monthly_amount: values.gross_monthly_income,
          currency: "LKR",
          is_taxable: true,
        },
      ],
    };
    createMutation.mutate(payload);
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Financial Profile</h1>
        <p className="text-muted-foreground">
          Capture income, expenses, dependents, and risk tolerance. These values
          power every downstream recommendation and impact simulation (FR1, FR2).
        </p>
      </div>

      <div className="grid gap-6 lg:grid-cols-[1.1fr_0.9fr]">
        <Card>
          <form onSubmit={handleSubmit(onSubmit)}>
            <CardHeader>
              <CardTitle>Create profile</CardTitle>
              <CardDescription>
                All amounts are in LKR. Defaults reflect a typical mid-career employee.
              </CardDescription>
            </CardHeader>

            <CardContent className="space-y-6">
              <Section title="Personal">
                <Field label="Full name" error={errors.full_name?.message}>
                  <Input {...register("full_name")} />
                </Field>
                <Field label="Date of birth" error={errors.date_of_birth?.message}>
                  <Input type="date" {...register("date_of_birth")} />
                </Field>
                <Field label="Gender">
                  <Select {...register("gender")}>
                    <option value="male">Male</option>
                    <option value="female">Female</option>
                    <option value="other">Other</option>
                  </Select>
                </Field>
                <Field label="Marital status">
                  <Select {...register("marital_status")}>
                    <option value="single">Single</option>
                    <option value="married">Married</option>
                    <option value="divorced">Divorced</option>
                    <option value="widowed">Widowed</option>
                  </Select>
                </Field>
                <Field label="District">
                  <Select {...register("district")}>
                    {SL_DISTRICTS.map((d) => (
                      <option key={d} value={d}>
                        {d}
                      </option>
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
              </Section>

              <Section title="Employment">
                <Field label="Occupation">
                  <Select {...register("occupation")}>
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
              </Section>

              <Section title="Income & expenses (monthly LKR)">
                <Field label="Gross monthly income" error={errors.gross_monthly_income?.message}>
                  <Input
                    type="text"
                    inputMode="decimal"
                    autoComplete="off"
                    {...withDecimalSanitize(register("gross_monthly_income"))}
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

              <Section title="Assets & liabilities (LKR)">
                <Field label="Liquid savings">
                  <Input
                    type="text"
                    inputMode="decimal"
                    autoComplete="off"
                    {...withDecimalSanitize(register("liquid_savings"))}
                  />
                </Field>
                <Field label="Existing investments">
                  <Input
                    type="text"
                    inputMode="decimal"
                    autoComplete="off"
                    {...withDecimalSanitize(register("existing_investments"))}
                  />
                </Field>
                <Field label="Total debt">
                  <Input
                    type="text"
                    inputMode="decimal"
                    autoComplete="off"
                    {...withDecimalSanitize(register("total_debt"))}
                  />
                </Field>
                <Field label="EPF balance">
                  <Input
                    type="text"
                    inputMode="decimal"
                    autoComplete="off"
                    {...withDecimalSanitize(register("epf_balance"))}
                  />
                </Field>
                <Field label="ETF balance">
                  <Input
                    type="text"
                    inputMode="decimal"
                    autoComplete="off"
                    {...withDecimalSanitize(register("etf_balance"))}
                  />
                </Field>
              </Section>

              <Section title="Insurance & reliefs (annual LKR)">
                <Field label="Life insurance premium">
                  <Input
                    type="text"
                    inputMode="decimal"
                    autoComplete="off"
                    {...withDecimalSanitize(register("life_insurance_premium_annual"))}
                  />
                </Field>
                <Field label="Home loan interest">
                  <Input
                    type="text"
                    inputMode="decimal"
                    autoComplete="off"
                    {...withDecimalSanitize(register("home_loan_interest_annual"))}
                  />
                </Field>
                <Field label="Donations">
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
                <Field label="Risk tolerance">
                  <Select {...register("risk_tolerance")}>
                    <option value="low">Low</option>
                    <option value="medium">Medium</option>
                    <option value="high">High</option>
                  </Select>
                </Field>
                <Field label="Horizon (years)">
                  <Input
                    type="text"
                    inputMode="numeric"
                    autoComplete="off"
                    {...withIntegerSanitize(register("investment_horizon_years"))}
                  />
                </Field>
                <Field label="Tax year">
                  <Input
                    type="text"
                    inputMode="numeric"
                    autoComplete="off"
                    {...withTaxYearSanitize(register("tax_year"))}
                  />
                </Field>
              </Section>

              {createMutation.isError && (
                <div className="rounded-md border border-destructive/40 bg-destructive/5 p-3 text-sm text-destructive">
                  {(createMutation.error as Error).message}
                </div>
              )}
            </CardContent>

            <CardFooter className="flex justify-end gap-2 border-t pt-4">
              <Button
                type="button"
                variant="outline"
                onClick={() => reset(defaultValues)}
                disabled={isSubmitting}
              >
                Reset
              </Button>
              <Button type="submit" disabled={isSubmitting || createMutation.isPending}>
                {createMutation.isPending && <Loader2 className="h-4 w-4 animate-spin" />}
                Create profile
              </Button>
            </CardFooter>
          </form>
        </Card>

        <div className="space-y-6">
          <DerivedFeaturesCard
            isLoading={featuresQuery.isFetching}
            features={featuresQuery.data}
            error={(featuresQuery.error as Error | null)?.message}
            placeholder={!selectedId}
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
                    onClick={() => setSelectedId(p.id)}
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

function DerivedFeaturesCard({
  features,
  isLoading,
  error,
  placeholder,
}: {
  features?: import("../types").DerivedFeatures;
  isLoading: boolean;
  error?: string;
  placeholder: boolean;
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
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-3 text-sm">
              <Stat label="Age" value={`${features.age_years} years`} />
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
              <div className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                Eligibility flags
              </div>
              <div className="flex flex-wrap gap-1.5">
                {Object.entries(features.eligibility_flags).map(([k, v]) => (
                  <span
                    key={k}
                    className={`rounded-full border px-2 py-0.5 text-xs ${
                      v
                        ? "border-emerald-300 bg-emerald-50 text-emerald-700 dark:border-emerald-700 dark:bg-emerald-950 dark:text-emerald-300"
                        : "border-border bg-muted text-muted-foreground"
                    }`}
                  >
                    {v ? "✓" : "·"} {k}
                  </span>
                ))}
              </div>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
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
