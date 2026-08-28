import {
  AlertCircle,
  Award,
  Briefcase,
  Building2,
  CheckCircle,
  FileCheck,
  FileText,
  Gift,
  Globe,
  Home,
  Landmark,
  MapPin,
  PiggyBank,
  Save,
  Send,
  Shield,
  TrendingUp,
  User,
  Zap,
} from "lucide-react";

import { cn } from "@/lib/utils";

import {
  blankBiz,
  blankDiv,
  blankEmployer,
  blankFd,
  blankProp,
} from "../defaults";
import { assessmentYearSelectOptions } from "../assessment-years";
import type { TaxReturnDetail } from "../types";
import {
  AmountField,
  Builder,
  Card,
  DateField,
  Field,
  G2,
  G3,
  G4,
  InfoBox,
  NicField,
  Rule,
  SectionHeader,
  Select,
  Stack,
  StatChip,
  Textarea,
  Toggle,
  TRP_COLORS,
} from "./primitives";

const C = TRP_COLORS;

const DISTRICTS = [
  "Ampara", "Anuradhapura", "Badulla", "Batticaloa", "Colombo", "Galle", "Gampaha",
  "Hambantota", "Jaffna", "Kalutara", "Kandy", "Kegalle", "Kilinochchi", "Kurunegala",
  "Mannar", "Matale", "Matara", "Monaragala", "Mullaitivu", "Nuwara Eliya",
  "Polonnaruwa", "Puttalam", "Ratnapura", "Trincomalee", "Vavuniya",
].map((d) => ({ value: d, label: d }));

const BANKS = [
  "Bank of Ceylon", "People's Bank", "Commercial Bank of Ceylon", "Hatton National Bank",
  "Sampath Bank", "Nations Trust Bank", "National Savings Bank", "Seylan Bank",
  "DFCC Bank", "Pan Asia Banking Corporation", "Union Bank", "Amana Bank", "LB Finance",
  "Central Finance", "Citizens Development Business Finance", "Softlogic Finance", "LOLC Finance",
].map((b) => ({ value: b, label: b }));

const COUNTRIES = [
  "Australia", "Belgium", "Canada", "China", "Denmark", "Finland", "France", "Germany",
  "India", "Indonesia", "Iran", "Italy", "Japan", "Malaysia", "Netherlands", "Norway",
  "Pakistan", "Poland", "Russia", "Singapore", "South Korea", "Sweden", "Switzerland",
  "Thailand", "UAE", "United Kingdom", "United States",
].map((c) => ({ value: c, label: c }));

const CURRENCIES = [
  "USD", "GBP", "EUR", "AUD", "CAD", "SGD", "AED", "INR", "JPY", "CNY", "CHF",
].map((c) => ({ value: c.toLowerCase(), label: c }));

type SecProps = {
  detail: TaxReturnDetail;
  onDetailChange: (d: TaxReturnDetail) => void;
  onComplete: () => void;
  onSave: () => void;
};

function patchDetail<K extends keyof TaxReturnDetail>(
  detail: TaxReturnDetail,
  onDetailChange: (d: TaxReturnDetail) => void,
  section: K,
  patch: Partial<TaxReturnDetail[K]>,
) {
  onDetailChange({
    ...detail,
    [section]: { ...detail[section], ...patch },
  });
}


function Sec1({ detail, onDetailChange, onComplete, onSave }: SecProps) {
  const s = detail.section1;
  const patch = (p: Partial<typeof s>) => patchDetail(detail, onDetailChange, "section1", p);

  return (
    <Stack gap={16}>
      <SectionHeader
        icon={User}
        color={C.teal}
        title="Taxpayer Identity & Statutory Status"
        subtitle="Your legal identity, NIC, TIN, residency classification, and correspondence details."
        sectionNum={1}
        totalSections={8}
        onSave={onSave}
        onComplete={onComplete}
      />

      <Card
        title="Personal Identification"
        subtitle="Legal name, NIC, TIN and citizenship"
        icon={User}
        accent={C.teal}
        defaultOpen
      >
        <Stack>
          <G3>
            <Field
              label="Full Legal Name"
              value={s.fullName}
              onChange={(v) => patch({ fullName: v })}
              required
              placeholder="As it appears on your NIC"
            />
            <Field
              label="Preferred Name / Display Name"
              value={s.preferredName}
              onChange={(v) => patch({ preferredName: v })}
              placeholder="What should we call you?"
            />
            <Field
              label="Passport Number"
              value={s.passport}
              onChange={(v) => patch({ passport: v })}
              mono
              placeholder="Optional — for international transactions"
            />
          </G3>
          <G3>
            <NicField value={s.nic} onChange={(v) => patch({ nic: v })} />
            <Field
              label="Tax Identification Number (TIN)"
              value={s.tin}
              onChange={(v) => patch({ tin: v })}
              required
              mono
              placeholder="9-digit IRD number"
              hint="Issued by the Inland Revenue Department"
            />
            <Select
              label="Year of Assessment"
              value={s.taxYear}
              onChange={(v) => patch({ taxYear: v })}
              options={assessmentYearSelectOptions()}
              required
            />
          </G3>
          <G4>
            <DateField
              label="Date of Birth"
              value={s.dob}
              onChange={(v) => patch({ dob: v })}
              required
            />
            <Select
              label="Gender"
              value={s.gender}
              onChange={(v) => patch({ gender: v })}
              options={[
                { value: "male", label: "Male" },
                { value: "female", label: "Female" },
                { value: "other", label: "Other" },
              ]}
            />
            <Select
              label="Nationality"
              value={s.nationality}
              onChange={(v) => patch({ nationality: v })}
              options={[
                { value: "lk", label: "Sri Lankan" },
                { value: "dual", label: "Dual Citizen" },
                { value: "foreign", label: "Foreign National" },
              ]}
            />
            <Select
              label="Marital Status"
              value={s.marital}
              onChange={(v) => patch({ marital: v })}
              options={[
                { value: "single", label: "Single" },
                { value: "married", label: "Married" },
                { value: "divorced", label: "Divorced" },
                { value: "widowed", label: "Widowed" },
              ]}
            />
          </G4>
        </Stack>
      </Card>

      <Card
        title="Residency & Tax Classification"
        subtitle="Determines worldwide vs source-based income taxation"
        icon={Globe}
        accent={C.blue}
      >
        <Stack>
          <InfoBox color="blue">
            Sri Lanka taxes{" "}
            <strong>resident individuals</strong> on worldwide
            income. You are a tax resident if present in Sri
            Lanka for 183+ days in the year of assessment, or if
            your permanent home is here.
          </InfoBox>
          <G3>
            <Select
              label="Residency Status"
              value={s.residency}
              onChange={(v) => patch({ residency: v })}
              required
              options={[
                {
                  value: "resident",
                  label: "Resident Individual",
                },
                {
                  value: "non-resident",
                  label: "Non-Resident",
                },
                { value: "deemed", label: "Deemed Resident" },
              ]}
              hint="Determines whether worldwide income is taxable"
            />
            <Select
              label="Tax Filing Basis"
              value={s.filingBasis}
              onChange={(v) => patch({ filingBasis: v })}
              required
              options={[
                { value: "individual", label: "Individual" },
                {
                  value: "joint",
                  label: "Joint (Husband & Wife)",
                },
              ]}
              hint="Joint filing may allow combined deduction reliefs"
            />
            <Field
              label="Number of Qualified Dependants"
              value={s.dependants}
              onChange={(v) => patch({ dependants: v })}
              type="number"
              placeholder="0"
              hint="Children or eligible relatives in your care"
            />
          </G3>
          {s.residency === "non-resident" && (
            <InfoBox color="amber">
              As a non-resident, only your Sri Lanka-sourced
              income is taxable. A flat rate of 14% applies to
              most categories. Ensure you attach Form IT-NR with
              your return.
            </InfoBox>
          )}
        </Stack>
      </Card>

      <Card
        title="Spouse & Joint Filing Details"
        subtitle="Required if married and opting for joint assessment"
        icon={Award}
        accent={C.purple}
        optional
      >
        <Stack>
          <Toggle
            label="Spouse has assessable income or I am filing jointly"
            subLabel="Enable to declare spouse income and access joint qualifying payment reliefs"
            checked={s.hasSpouse}
            onChange={(v) => patch({ hasSpouse: v })}
          />
          {s.hasSpouse && (
            <>
              <Rule label="SPOUSE INFORMATION" />
              <G4>
                <Field
                  label="Spouse Full Legal Name"
                  value={s.spouseName}
                  onChange={(v) => patch({ spouseName: v })}
                  required
                />
                <Field
                  label="Spouse NIC"
                  value={s.spouseNic}
                  onChange={(v) => patch({ spouseNic: v })}
                  mono
                  required
                />
                <Field
                  label="Spouse TIN"
                  value={s.spouseTin}
                  onChange={(v) => patch({ spouseTin: v })}
                  mono
                />
                <Field
                  label="Spouse Employer"
                  value={s.spouseEmployer}
                  onChange={(v) => patch({ spouseEmployer: v })}
                />
              </G4>
            </>
          )}
        </Stack>
      </Card>

      <Card
        title="Correspondence Address"
        subtitle="IRD notifications and tax statements will be sent here"
        icon={MapPin}
        accent={C.amber}
      >
        <Stack>
          <G2>
            <Field
              label="Email Address"
              value={s.email}
              onChange={(v) => patch({ email: v })}
              required
              type="email"
            />
            <Field
              label="Primary Mobile Number"
              value={s.phone}
              onChange={(v) => patch({ phone: v })}
              required
              placeholder="+94 XX XXX XXXX"
            />
          </G2>
          <G2>
            <Field
              label="Address Line 1"
              value={s.addr1}
              onChange={(v) => patch({ addr1: v })}
              required
              placeholder="House / Unit number and street"
            />
            <Field
              label="Address Line 2"
              value={s.addr2}
              onChange={(v) => patch({ addr2: v })}
              placeholder="Apartment, suite, floor (optional)"
            />
          </G2>
          <G4>
            <Field
              label="City / Town"
              value={s.city}
              onChange={(v) => patch({ city: v })}
            />
            <Select
              label="District"
              value={s.district}
              onChange={(v) => patch({ district: v })}
              options={DISTRICTS}
            />
            <Select
              label="Province"
              value={s.province}
              onChange={(v) => patch({ province: v })}
              options={[
                "Central",
                "Eastern",
                "Northern",
                "North Central",
                "North Western",
                "Sabaragamuwa",
                "Southern",
                "Uva",
                "Western",
              ].map((p) => ({
                value: p.toLowerCase().replace(/ /g, "-"),
                label: p,
              }))}
            />
            <Field
              label="Postal Code"
              value={s.postal}
              onChange={(v) => patch({ postal: v })}
              mono
            />
          </G4>
        </Stack>
      </Card>

      <Card
        title="Tax Agent / Authorised Representative"
        subtitle="Only complete if a registered tax agent is filing on your behalf"
        icon={FileCheck}
        accent={C.green}
        optional
      >
        <Stack>
          <Toggle
            label="A registered IRD-authorised tax agent is filing on my behalf"
            subLabel="Agent must hold a valid IRD practitioner registration"
            checked={s.hasAgent}
            onChange={(v) => patch({ hasAgent: v })}
          />
          {s.hasAgent && (
            <>
              <Rule label="AGENT DETAILS" />
              <G3>
                <Field
                  label="Agent / Firm Name"
                  value={s.agentName}
                  onChange={(v) => patch({ agentName: v })}
                  required
                />
                <Field
                  label="Agent Registration / TIN"
                  value={s.agentTin}
                  onChange={(v) => patch({ agentTin: v })}
                  mono
                  required
                />
                <Field
                  label="Agent Firm / Practice Name"
                  value={s.agentFirm}
                  onChange={(v) => patch({ agentFirm: v })}
                />
              </G3>
              <G2>
                <Field
                  label="Agent Phone Number"
                  value={s.agentPhone}
                  onChange={(v) => patch({ agentPhone: v })}
                />
                <Field
                  label="Agent Email"
                  value={s.agentEmail}
                  onChange={(v) => patch({ agentEmail: v })}
                  type="email"
                />
              </G2>
              <InfoBox color="green">
                By authorising an agent, you allow them to file,
                amend, and correspond with IRD on your behalf.
                You remain legally responsible for the accuracy
                of all declared information.
              </InfoBox>
            </>
          )}
        </Stack>
      </Card>
    </Stack>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// SECTION 2 — Employment & Remuneration
// ─────────────────────────────────────────────────────────────────────────────

function Sec2({ detail, onDetailChange, onComplete, onSave }: SecProps) {
  const s = detail.section2;
  const patch = (p: Partial<typeof s>) => patchDetail(detail, onDetailChange, "section2", p);
  const employers = s.employers;
  const upd = (i: number, k: keyof typeof employers[0], v: string) =>
    patch({ employers: employers.map((e, j) => (j === i ? { ...e, [k]: v } : e)) });

  return (
    <Stack gap={16}>
      <SectionHeader
        icon={Briefcase}
        color={C.blue}
        title="Employment & Remuneration"
        subtitle="Declare all salary income, APIT deducted, EPF/ETF, and employment benefits for every employer."
        sectionNum={2}
        totalSections={8}
        onSave={onSave}
        onComplete={onComplete}
      />

      <InfoBox color="blue">
        APIT (Advance Personal Income Tax) deducted at source by
        your employer is a tax credit — not a final payment.
        Cross-reference each figure with the APIT Certificate
        (Form 16) issued by your employer before the April 30
        deadline.
      </InfoBox>

      <Card
        title="Primary & Secondary Employment"
        subtitle="Add all employers including part-time, seconded, and contract roles"
        icon={Briefcase}
        accent={C.blue}
        defaultOpen
        badge={`${employers.length} employer${employers.length !== 1 ? "s" : ""}`}
        badgeColor={C.blue}
      >
        <Builder
          items={employers}
          onAdd={() => patch({ employers: [...employers, blankEmployer()] })}
          onRemove={(i) =>
            patch({ employers: employers.filter((_, j) => j !== i) })
          }
          onChange={upd}
          addLabel="Add Another Employer"
          entryLabel="Employer"
          render={(e, _i, u) => (
            <Stack>
              <G3>
                <Field
                  label="Employer Name"
                  value={e.name}
                  onChange={(v) => u("name", v)}
                  required
                  placeholder="Full legal name of employer"
                />
                <Field
                  label="Employer TIN"
                  value={e.tin}
                  onChange={(v) => u("tin", v)}
                  mono
                  placeholder="9-digit TIN"
                  hint="From your employment contract or Form 16"
                />
                <Field
                  label="Your Designation / Role"
                  value={e.role}
                  onChange={(v) => u("role", v)}
                  placeholder="e.g. Senior Engineer"
                />
              </G3>
              <G4>
                <DateField
                  label="Employment Start Date"
                  value={e.from}
                  onChange={(v) => u("from", v)}
                  required
                />
                <Select
                  label="Still Employed Here?"
                  value={e.current}
                  onChange={(v) => u("current", v)}
                  options={[
                    { value: "yes", label: "Yes — Current" },
                    {
                      value: "no",
                      label: "No — Resigned / Terminated",
                    },
                  ]}
                />
                {e.current === "no" && (
                  <DateField
                    label="Last Day of Employment"
                    value={e.to}
                    onChange={(v) => u("to", v)}
                  />
                )}
              </G4>
              <Rule label="REMUNERATION BREAKDOWN" />
              <G3>
                <AmountField
                  label="Gross Annual Salary (LKR)"
                  value={e.gross}
                  onChange={(v) => u("gross", v)}
                  required
                  hint="Total before all deductions"
                />
                <AmountField
                  label="APIT Deducted at Source (LKR)"
                  value={e.apit}
                  onChange={(v) => u("apit", v)}
                  required
                  hint="From APIT Certificate / Form 16"
                />
                <AmountField
                  label="Annual Bonus & Performance Pay (LKR)"
                  value={e.bonus}
                  onChange={(v) => u("bonus", v)}
                />
              </G3>
              <G4>
                <AmountField
                  label="EPF — Employee Share (LKR)"
                  value={e.epf}
                  onChange={(v) => u("epf", v)}
                  hint="8% of gross salary (employee)"
                />
                <AmountField
                  label="ETF Contribution (LKR)"
                  value={e.etf}
                  onChange={(v) => u("etf", v)}
                  hint="3% employer contribution for reference"
                />
                <AmountField
                  label="Taxable Allowances (LKR)"
                  value={e.allowances}
                  onChange={(v) => u("allowances", v)}
                  hint="Vehicle, rent, meal allowances"
                />
                <AmountField
                  label="Overtime Pay (LKR)"
                  value={e.overtime}
                  onChange={(v) => u("overtime", v)}
                />
              </G4>
              <AmountField
                label="Non-Cash Benefits / Perquisites (LKR)"
                value={e.noncash}
                onChange={(v) => u("noncash", v)}
                hint="Company car, employer-provided housing, group health insurance, staff loans at concessionary rates"
              />
            </Stack>
          )}
        />
      </Card>

      <Card
        title="Director Fees & Board Remunerations"
        subtitle="Income from company directorships, advisory boards, or secretarial roles"
        icon={Award}
        accent={C.purple}
        optional
      >
        <Stack>
          <Toggle
            label="I received director fees or board-level remuneration this year"
            subLabel="Including fees from subsidiary, associate, or parent companies"
            checked={s.hasDirector}
            onChange={(v) => patch({ hasDirector: v })}
          />
          {s.hasDirector && (
            <G3>
              <AmountField
                label="Total Director Fees (LKR)"
                value={s.directorFees}
                onChange={(v) => patch({ directorFees: v })}
                required
              />
              <Field
                label="Company / Entity Name"
                value={s.companyName}
                onChange={(v) => patch({ companyName: v })}
                required
              />
              <Field
                label="Company TIN"
                value={s.directorTin}
                onChange={(v) => patch({ directorTin: v })}
                mono
              />
            </G3>
          )}
        </Stack>
      </Card>

      <Card
        title="Gratuity & Terminal Benefits"
        subtitle="One-off payments upon retirement, resignation, or retrenchment"
        icon={PiggyBank}
        accent={C.green}
        optional
      >
        <Stack>
          <Toggle
            label="I received a gratuity or terminal benefit payment this year"
            subLabel="Gratuity may be partially or fully exempt based on years of service"
            checked={s.hasGratuity}
            onChange={(v) => patch({ hasGratuity: v })}
          />
          {s.hasGratuity && (
            <>
              <InfoBox color="green">
                Gratuity is exempt up to LKR 2,000,000 per
                employer for continuous service ≥ 5 years.
                Beyond that, the excess is taxable. Check
                Section 13 of IRA 2017.
              </InfoBox>
              <G3>
                <AmountField
                  label="Gratuity / Terminal Payment (LKR)"
                  value={s.gratuityAmount}
                  onChange={(v) => patch({ gratuityAmount: v })}
                  required
                />
                <Field
                  label="Years of Continuous Service"
                  value={s.gratuityYears}
                  onChange={(v) => patch({ gratuityYears: v })}
                  type="number"
                  hint="Determines the exempt portion"
                />
                <Select
                  label="Nature of Termination"
                  value={s.gratuityType}
                  onChange={(v) => patch({ gratuityType: v })}
                  options={[
                    {
                      value: "resign",
                      label: "Voluntary Resignation",
                    },
                    {
                      value: "retire",
                      label: "Normal Retirement",
                    },
                    {
                      value: "early",
                      label: "Early Retirement",
                    },
                    {
                      value: "retrench",
                      label: "Retrenchment / Redundancy",
                    },
                    {
                      value: "medical",
                      label: "Medical Incapacity",
                    },
                    {
                      value: "death",
                      label: "Death / Disability",
                    },
                  ]}
                />
              </G3>
            </>
          )}
        </Stack>
      </Card>

      <Card
        title="Severance Pay & Compensation"
        subtitle="Payments for wrongful dismissal, contract breach, or legal settlements"
        icon={FileText}
        accent={C.amber}
        optional
      >
        <Stack>
          <Toggle
            label="I received severance pay or compensation related to employment"
            checked={s.hasSeverance}
            onChange={(v) => patch({ hasSeverance: v })}
          />
          {s.hasSeverance && (
            <G2>
              <AmountField
                label="Severance / Compensation Amount (LKR)"
                value={s.severanceAmount}
                onChange={(v) => patch({ severanceAmount: v })}
                required
              />
              <Select
                label="Reason for Payment"
                value={s.severanceReason}
                onChange={(v) => patch({ severanceReason: v })}
                options={[
                  {
                    value: "wrongful",
                    label: "Wrongful Dismissal Award",
                  },
                  {
                    value: "contract",
                    label: "Contract Breach Settlement",
                  },
                  {
                    value: "redundancy",
                    label: "Redundancy Payment",
                  },
                  {
                    value: "other",
                    label: "Other Compensation",
                  },
                ]}
              />
            </G2>
          )}
        </Stack>
      </Card>

      <Card
        title="Commission & Sales-Based Income"
        subtitle="Variable income earned as commissions, referral fees, or sales bonuses"
        icon={TrendingUp}
        accent={C.teal}
        optional
      >
        <Stack>
          <Toggle
            label="I earned commission or variable sales-based income"
            checked={s.hasCommission}
            onChange={(v) => patch({ hasCommission: v })}
          />
          {s.hasCommission && (
            <G2>
              <AmountField
                label="Total Commission Earned (LKR)"
                value={s.commissionAmount}
                onChange={(v) => patch({ commissionAmount: v })}
                required
              />
              <Field
                label="Paying Organisation"
                value={s.commissionPayer}
                onChange={(v) => patch({ commissionPayer: v })}
              />
            </G2>
          )}
        </Stack>
      </Card>

      <Card
        title="Pension Payments"
        subtitle="Regular pension income from a former employer or approved scheme (Sec 5(2)(a))"
        icon={PiggyBank}
        accent={C.blue}
        optional
      >
        <Stack>
          <Toggle
            label="I received pension payments during the year"
            subLabel="Include employer or private pension paid to you — not EPF lump withdrawals (use Gratuity if applicable)"
            checked={s.hasPension}
            onChange={(v) => patch({ hasPension: v })}
          />
          {s.hasPension && (
            <G3>
              <AmountField
                label="Total Pension Received (LKR)"
                value={s.pensionAmount}
                onChange={(v) => patch({ pensionAmount: v })}
                required
              />
              <Field
                label="Paying Organisation / Scheme"
                value={s.pensionPayer}
                onChange={(v) => patch({ pensionPayer: v })}
                placeholder="e.g. Former employer, SLA Pension"
              />
              <Select
                label="Pension Type"
                value={s.pensionType}
                onChange={(v) => patch({ pensionType: v })}
                options={[
                  { value: "employer", label: "Employer Pension" },
                  { value: "government", label: "Government / Public Service" },
                  { value: "private", label: "Private / Approved Scheme" },
                  { value: "foreign", label: "Foreign Pension" },
                ]}
              />
            </G3>
          )}
        </Stack>
      </Card>

      <Card
        title="Gifts in Respect of Employment"
        subtitle="Cash or benefits received as gifts from your employer (Sec 5(2)(i))"
        icon={Gift}
        accent={C.purple}
        optional
      >
        <Stack>
          <Toggle
            label="I received gifts from my employer or in connection with employment"
            subLabel="Report the amount you received — your auditor confirms whether it is taxable employment income"
            checked={s.hasGifts}
            onChange={(v) => patch({ hasGifts: v })}
          />
          {s.hasGifts && (
            <G2>
              <AmountField
                label="Total Gift Value Received (LKR)"
                value={s.giftAmount}
                onChange={(v) => patch({ giftAmount: v })}
                required
              />
              <Field
                label="Description / Occasion"
                value={s.giftDescription}
                onChange={(v) => patch({ giftDescription: v })}
                placeholder="e.g. Long-service award, festival gift"
              />
            </G2>
          )}
        </Stack>
      </Card>
    </Stack>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// SECTION 3 — Fixed Deposits & Financial Investments
// ─────────────────────────────────────────────────────────────────────────────

function Sec3({ detail, onDetailChange, onComplete, onSave }: SecProps) {
  const s = detail.section3;
  const patch = (p: Partial<typeof s>) => patchDetail(detail, onDetailChange, "section3", p);
  const fds = s.fds;
  const divs = s.divs;

  return (
    <Stack gap={16}>
      <SectionHeader
        icon={Landmark}
        color={C.green}
        title="Fixed Deposits & Financial Investments"
        subtitle="Declare interest income, dividends, government securities, and capital gains from all financial investments."
        sectionNum={3}
        totalSections={8}
        onSave={onSave}
        onComplete={onComplete}
      />

      <InfoBox>
        WHT deducted on FD interest (5% for residents) and
        dividends (15%) is a <strong>final tax</strong> — no
        additional tax is payable on these. However, amounts
        must still be declared for income completeness.
        Non-residents are taxed at 14%.
      </InfoBox>

      <Card
        title="Fixed Deposits & Term Investments"
        subtitle="Add each FD account separately for accurate WHT reconciliation"
        icon={PiggyBank}
        accent={C.green}
        defaultOpen
        badge={`${fds.length} account${fds.length !== 1 ? "s" : ""}`}
        badgeColor={C.green}
      >
        <Builder
          items={fds}
          onAdd={() => patch({ fds: [...fds, blankFd()] })}
          onRemove={(i) =>
            patch({ fds: fds.filter((_, j) => j !== i) })
          }
          onChange={(i, k, v) =>
            patch({ fds: fds.map((e, j) => (j === i ? { ...e, [k]: v } : e)) })
          }
          addLabel="Add Fixed Deposit / Term Account"
          entryLabel="FD Account"
          render={(fd, _i, u) => (
            <G3>
              <Select
                label="Bank / Finance Company"
                value={fd.bank}
                onChange={(v) => u("bank", v)}
                options={BANKS}
                required
              />
              <Field
                label="FD / Account Reference Number"
                value={fd.accNo}
                onChange={(v) => u("accNo", v)}
                mono
                placeholder="Reference as on FD certificate"
              />
              <Select
                label="Deposit Type"
                value={fd.type}
                onChange={(v) => u("type", v)}
                options={[
                  { value: "fd", label: "Fixed Deposit" },
                  { value: "td", label: "Term Deposit" },
                  { value: "rd", label: "Recurring Deposit" },
                  { value: "call", label: "Call Deposit" },
                ]}
              />
              <DateField
                label="Maturity / Year-End Date"
                value={fd.maturity}
                onChange={(v) => u("maturity", v)}
              />
              <AmountField
                label="Principal Amount (LKR)"
                value={fd.principal}
                onChange={(v) => u("principal", v)}
              />
              <AmountField
                label="Gross Interest Earned (LKR)"
                value={fd.interest}
                onChange={(v) => u("interest", v)}
                required
                hint="Before WHT deduction"
              />
              <AmountField
                label="WHT Deducted (LKR)"
                value={fd.wht}
                onChange={(v) => u("wht", v)}
                hint="5% of interest for resident individuals"
              />
            </G3>
          )}
        />
      </Card>

      <Card
        title="Savings Account Interest"
        subtitle="Interest credited to regular savings and flexi-savings accounts"
        icon={Landmark}
        accent={C.teal}
      >
        <Stack>
          <Toggle
            label="I earned interest from savings or current accounts during the year"
            checked={s.hasSavings}
            onChange={(v) => patch({ hasSavings: v })}
          />
          {s.hasSavings && (
            <G3>
              <AmountField
                label="Total Savings Interest Earned (LKR)"
                value={s.savingsInterest}
                onChange={(v) => patch({ savingsInterest: v })}
                required
              />
              <AmountField
                label="WHT Deducted on Savings Interest (LKR)"
                value={s.savingsWht}
                onChange={(v) => patch({ savingsWht: v })}
              />
            </G3>
          )}
        </Stack>
      </Card>

      <Card
        title="Dividend Income"
        subtitle="Dividends from listed/unlisted companies, ETFs, and equity funds"
        icon={TrendingUp}
        accent={C.blue}
        badge={
          divs.length > 0 && divs[0].company
            ? `${divs.length} source${divs.length !== 1 ? "s" : ""}`
            : undefined
        }
        badgeColor={C.blue}
      >
        <Stack>
          <InfoBox color="blue">
            Dividends from <strong>resident companies</strong>{" "}
            carry 15% WHT (final tax). Dividends from
            non-resident companies are taxed at your marginal
            rate and must be grossed up for foreign tax credits.
          </InfoBox>
          <Builder
            items={divs}
            onAdd={() => patch({ divs: [...divs, blankDiv()] })}
            onRemove={(i) =>
              patch({ divs: divs.filter((_, j) => j !== i) })
            }
            onChange={(i, k, v) =>
              patch({ divs: divs.map((e, j) => (j === i ? { ...e, [k]: v } : e)) })
            }
            addLabel="Add Dividend Source"
            entryLabel="Dividend"
            render={(d, _i, u) => (
              <G3>
                <Field
                  label="Company / ETF / Fund Name"
                  value={d.company}
                  onChange={(v) => u("company", v)}
                  required
                  placeholder="e.g. John Keells Holdings PLC"
                />
                <Select
                  label="Company Residency"
                  value={d.resident}
                  onChange={(v) => u("resident", v)}
                  options={[
                    {
                      value: "yes",
                      label: "Resident Sri Lankan Company",
                    },
                    {
                      value: "no",
                      label: "Non-Resident / Foreign Company",
                    },
                  ]}
                />
                <Field
                  label="Number of Shares / Units Held"
                  value={d.shares}
                  onChange={(v) => u("shares", v)}
                  type="number"
                />
                <AmountField
                  label="Dividend Per Share (LKR)"
                  value={d.dps}
                  onChange={(v) => u("dps", v)}
                />
                <AmountField
                  label="Total Gross Dividend (LKR)"
                  value={d.total}
                  onChange={(v) => u("total", v)}
                  required
                />
                <AmountField
                  label="WHT Deducted (LKR)"
                  value={d.wht}
                  onChange={(v) => u("wht", v)}
                  hint="15% for resident companies"
                />
              </G3>
            )}
          />
        </Stack>
      </Card>

      <Card
        title="Government Securities — T-Bills & Treasury Bonds"
        subtitle="Interest from Central Bank-issued instruments and development bonds"
        icon={FileText}
        accent={C.purple}
        optional
      >
        <Stack>
          <Toggle
            label="I held or traded government securities during the year"
            checked={s.hasGovSec}
            onChange={(v) => patch({ hasGovSec: v })}
            subLabel="Includes T-Bills, T-Bonds, Sovereign Bonds, and SL Development Bonds"
          />
          {s.hasGovSec && (
            <G4>
              <AmountField
                label="T-Bill Face Value / Investment (LKR)"
                value={s.govTbill}
                onChange={(v) => patch({ govTbill: v })}
              />
              <AmountField
                label="Treasury Bond Investment (LKR)"
                value={s.govTbond}
                onChange={(v) => patch({ govTbond: v })}
              />
              <AmountField
                label="Total Interest / Yield Earned (LKR)"
                value={s.govInterest}
                onChange={(v) => patch({ govInterest: v })}
                required
              />
              <AmountField
                label="WHT Deducted (LKR)"
                value={s.govWht}
                onChange={(v) => patch({ govWht: v })}
              />
            </G4>
          )}
        </Stack>
      </Card>

      <Card
        title="Unit Trust Income Distributions"
        subtitle="Distributions from SEC-approved collective investment schemes"
        icon={Building2}
        accent={C.amber}
        optional
      >
        <Stack>
          <Toggle
            label="I received income distributions from unit trust or mutual funds"
            checked={s.hasUnitTrust}
            onChange={(v) => patch({ hasUnitTrust: v })}
          />
          {s.hasUnitTrust && (
            <G3>
              <Field
                label="Fund Manager / Trust Name"
                value={s.unitTrustFund}
                onChange={(v) => patch({ unitTrustFund: v })}
                placeholder="e.g. Comtrust Asset Management"
              />
              <AmountField
                label="Total Distribution Received (LKR)"
                value={s.unitTrustDistribution}
                onChange={(v) => patch({ unitTrustDistribution: v })}
                required
              />
              <AmountField
                label="WHT Deducted (LKR)"
                value={s.unitTrustWht}
                onChange={(v) => patch({ unitTrustWht: v })}
              />
            </G3>
          )}
        </Stack>
      </Card>

      <Card
        title="CSE Share Trading & Capital Gains"
        subtitle="Profits or losses from buying/selling shares on the Colombo Stock Exchange"
        icon={TrendingUp}
        accent={C.red}
        optional
      >
        <Stack>
          <Toggle
            label="I bought and sold shares on the CSE during the year"
            subLabel="Capital gains from listed shares are currently exempt — but declaration is mandatory"
            checked={s.hasCSE}
            onChange={(v) => patch({ hasCSE: v })}
          />
          {s.hasCSE && (
            <G3>
              <AmountField
                label="Total Sale Proceeds (LKR)"
                value={s.cseProceeds}
                onChange={(v) => patch({ cseProceeds: v })}
                required
              />
              <AmountField
                label="Total Cost of Acquisition (LKR)"
                value={s.cseCost}
                onChange={(v) => patch({ cseCost: v })}
              />
              <AmountField
                label="Net Capital Gain / (Loss) (LKR)"
                value={s.cseGain}
                onChange={(v) => patch({ cseGain: v })}
                hint="Proceeds minus acquisition cost"
              />
            </G3>
          )}
        </Stack>
      </Card>

      <Card
        title="REIT & Real Estate Investment Income"
        subtitle="Distributions from listed Real Estate Investment Trusts"
        icon={Home}
        accent={C.green}
        optional
      >
        <Stack>
          <Toggle
            label="I received income from a listed REIT"
            checked={s.hasREIT}
            onChange={(v) => patch({ hasREIT: v })}
          />
          {s.hasREIT && (
            <G2>
              <Field
                label="REIT Name"
                value={s.reitFund}
                onChange={(v) => patch({ reitFund: v })}
              />
              <AmountField
                label="Total Distribution (LKR)"
                value={s.reitIncome}
                onChange={(v) => patch({ reitIncome: v })}
                required
              />
            </G2>
          )}
        </Stack>
      </Card>
    </Stack>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// SECTION 4 — Business, Freelance & Secondary Trades
// ─────────────────────────────────────────────────────────────────────────────

function Sec4({ detail, onDetailChange, onComplete, onSave }: SecProps) {
  const s = detail.section4;
  const patch = (p: Partial<typeof s>) => patchDetail(detail, onDetailChange, "section4", p);
  const biz = s.businesses;

  return (
    <Stack gap={16}>
      <SectionHeader
        icon={Building2}
        color={C.purple}
        title="Business, Freelance & Secondary Trades"
        subtitle="Profits from sole proprietorships, partnerships, professional practices, freelance, and online platforms."
        sectionNum={4}
        totalSections={8}
        onSave={onSave}
        onComplete={onComplete}
      />

      <InfoBox color="purple">
        Business profits are computed after deducting{" "}
        <strong>allowable expenses only</strong>. Personal
        expenses, capital expenditure, and fines are not
        deductible. Maintain a separate business bank account to
        simplify expense tracking.
      </InfoBox>

      <Card
        title="Business / Sole Trade / Partnership"
        subtitle="Registered or unregistered businesses, shops, agencies, and trading operations"
        icon={Building2}
        accent={C.purple}
        defaultOpen
      >
        <Builder
          items={biz}
          onAdd={() => patch({ businesses: [...biz, blankBiz()] })}
          onRemove={(i) =>
            patch({ businesses: biz.filter((_, j) => j !== i) })
          }
          onChange={(i, k, v) =>
            patch({ businesses: biz.map((e, j) => (j === i ? { ...e, [k]: v } : e)) })
          }
          addLabel="Add Business / Trade"
          entryLabel="Business"
          render={(b, _i, u) => (
            <Stack>
              <G3>
                <Field
                  label="Business / Trade Name"
                  value={b.name}
                  onChange={(v) => u("name", v)}
                  required
                />
                <Field
                  label="BR / Registration Number"
                  value={b.regNo}
                  onChange={(v) => u("regNo", v)}
                  mono
                  placeholder="If formally registered"
                />
                <Select
                  label="Business Structure"
                  value={b.type}
                  onChange={(v) => u("type", v)}
                  options={[
                    { value: "sole", label: "Sole Proprietor" },
                    {
                      value: "partnership",
                      label: "Partnership",
                    },
                    {
                      value: "professional",
                      label: "Professional Practice",
                    },
                    {
                      value: "franchise",
                      label: "Franchise / Agency",
                    },
                    {
                      value: "trade",
                      label: "Trade / Commerce",
                    },
                  ]}
                />
              </G3>
              <G2>
                <Field
                  label="Nature of Business / Industry"
                  value={b.nature}
                  onChange={(v) => u("nature", v)}
                  placeholder="e.g. IT Consulting, Retail, Catering"
                />
                <DateField
                  label="Business Start Date"
                  value={b.start}
                  onChange={(v) => u("start", v)}
                />
              </G2>
              <Rule label="INCOME" />
              <G2>
                <AmountField
                  label="Gross Turnover / Revenue (LKR)"
                  value={b.revenue}
                  onChange={(v) => u("revenue", v)}
                  required
                />
                <AmountField
                  label="Cost of Goods Sold (LKR)"
                  value={b.cogs}
                  onChange={(v) => u("cogs", v)}
                />
              </G2>
              <Rule label="ALLOWABLE EXPENSES" />
              <G3>
                <AmountField
                  label="Staff Salaries & Wages (LKR)"
                  value={b.wages}
                  onChange={(v) => u("wages", v)}
                />
                <AmountField
                  label="Business Rent & Premises (LKR)"
                  value={b.rent}
                  onChange={(v) => u("rent", v)}
                />
                <AmountField
                  label="Utilities & Communications (LKR)"
                  value={b.utilities}
                  onChange={(v) => u("utilities", v)}
                />
                <AmountField
                  label="Depreciation on Business Assets (LKR)"
                  value={b.depreciation}
                  onChange={(v) => u("depreciation", v)}
                  hint="Using IRD-approved depreciation rates"
                />
                <AmountField
                  label="Professional & Legal Fees (LKR)"
                  value={b.professional}
                  onChange={(v) => u("professional", v)}
                />
                <AmountField
                  label="Advertising & Marketing (LKR)"
                  value={b.advertising}
                  onChange={(v) => u("advertising", v)}
                />
              </G3>
              <AmountField
                label="Other Allowable Expenses (LKR)"
                value={b.other}
                onChange={(v) => u("other", v)}
                hint="Insurance, subscriptions, business travel, stationery"
              />
            </Stack>
          )}
        />
      </Card>

      <Card
        title="Freelance & Online Platform Income"
        subtitle="Income from Upwork, Fiverr, Toptal, local consulting, tutoring, content creation"
        icon={Globe}
        accent={C.teal}
      >
        <Stack>
          <Toggle
            label="I earned freelance or online platform income this year"
            subLabel="Convert foreign currency at the CBSL buying rate on the date of receipt"
            checked={s.hasFreelance}
            onChange={(v) => patch({ hasFreelance: v })}
          />
          {s.hasFreelance && (
            <>
              <G3>
                <Select
                  label="Primary Platform"
                  value={s.freelancePlatform}
                  onChange={(v) => patch({ freelancePlatform: v })}
                  options={[
                    { value: "upwork", label: "Upwork" },
                    { value: "fiverr", label: "Fiverr" },
                    { value: "toptal", label: "Toptal" },
                    {
                      value: "freelancer",
                      label: "Freelancer.com",
                    },
                    { value: "99designs", label: "99designs" },
                    { value: "guru", label: "Guru" },
                    {
                      value: "direct",
                      label: "Direct / Local Clients",
                    },
                    {
                      value: "youtube",
                      label: "YouTube / Content",
                    },
                    { value: "other", label: "Other" },
                  ]}
                />
                <Select
                  label="Income Currency"
                  value={s.freelanceCurrency}
                  onChange={(v) => patch({ freelanceCurrency: v })}
                  options={[
                    { value: "lkr", label: "LKR" },
                    { value: "usd", label: "USD" },
                    { value: "gbp", label: "GBP" },
                    { value: "eur", label: "EUR" },
                    { value: "aud", label: "AUD" },
                    { value: "cad", label: "CAD" },
                    { value: "sgd", label: "SGD" },
                    { value: "aed", label: "AED" },
                  ]}
                />
                <Field
                  label="CBSL Exchange Rate (LKR per 1 unit)"
                  value={s.freelanceRate}
                  onChange={(v) => patch({ freelanceRate: v })}
                  mono
                  hint="Use annual average rate for the YA from CBSL.gov.lk"
                />
              </G3>
              <G3>
                <Field
                  label="Gross Revenue (Foreign Currency)"
                  value={s.freelanceRevenue}
                  onChange={(v) => patch({ freelanceRevenue: v })}
                  mono
                  required
                  prefix={s.freelanceCurrency.toUpperCase()}
                />
                <AmountField
                  label="LKR Equivalent Amount"
                  value={s.freelanceLkr}
                  onChange={(v) => patch({ freelanceLkr: v })}
                  required
                  hint="Revenue × CBSL rate"
                />
                <AmountField
                  label="Platform Commission / Fees (LKR)"
                  value={s.freelanceCommissions}
                  onChange={(v) => patch({ freelanceCommissions: v })}
                  hint="Deductible as a business expense"
                />
              </G3>
              <AmountField
                label="Other Business Expenses Related to Freelancing (LKR)"
                value={s.freelanceExpenses}
                onChange={(v) => patch({ freelanceExpenses: v })}
                hint="Internet, software licences, equipment used solely for freelance work"
              />
            </>
          )}
        </Stack>
      </Card>

      <Card
        title="Professional Practice Income"
        subtitle="Doctors, lawyers, accountants, architects, and other licensed professionals"
        icon={FileCheck}
        accent={C.blue}
        optional
      >
        <Stack>
          <Toggle
            label="I earn income from a registered professional practice"
            checked={s.hasProfessional}
            onChange={(v) => patch({ hasProfessional: v })}
          />
          {s.hasProfessional && (
            <G3>
              <Field
                label="Practice Name / Specialty"
                value={s.professionalPractice}
                onChange={(v) => patch({ professionalPractice: v })}
                placeholder="e.g. Dr. K. Perera — Dental Practice"
              />
              <AmountField
                label="Gross Professional Fees (LKR)"
                value={s.professionalRevenue}
                onChange={(v) => patch({ professionalRevenue: v })}
                required
              />
              <AmountField
                label="Practice Operating Expenses (LKR)"
                value={s.professionalExpenses}
                onChange={(v) => patch({ professionalExpenses: v })}
              />
            </G3>
          )}
        </Stack>
      </Card>

      <Card
        title="Agricultural Income"
        subtitle="Income from cultivation, livestock, poultry, aquaculture, and agri-processing"
        icon={Home}
        accent={C.green}
        optional
      >
        <Stack>
          <Toggle
            label="I have agricultural income to declare"
            subLabel="Agricultural income may qualify for specific exemptions or reduced rates"
            checked={s.hasAgri}
            onChange={(v) => patch({ hasAgri: v })}
          />
          {s.hasAgri && (
            <G3>
              <Field
                label="Type of Agricultural Activity"
                value={s.agriCrop}
                onChange={(v) => patch({ agriCrop: v })}
                placeholder="e.g. Paddy cultivation, Tea estate, Poultry"
              />
              <AmountField
                label="Gross Agricultural Revenue (LKR)"
                value={s.agriRevenue}
                onChange={(v) => patch({ agriRevenue: v })}
                required
              />
              <AmountField
                label="Agricultural Operating Expenses (LKR)"
                value={s.agriExpenses}
                onChange={(v) => patch({ agriExpenses: v })}
              />
            </G3>
          )}
        </Stack>
      </Card>
    </Stack>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// SECTION 5 — Real Estate & Rental Incomes
// ─────────────────────────────────────────────────────────────────────────────

function Sec5({ detail, onDetailChange, onComplete, onSave }: SecProps) {
  const s = detail.section5;
  const patch = (p: Partial<typeof s>) => patchDetail(detail, onDetailChange, "section5", p);
  const props = s.properties;

  return (
    <Stack gap={16}>
      <SectionHeader
        icon={Home}
        color={C.amber}
        title="Real Estate & Rental Incomes"
        subtitle="Declare gross rental income, allowable deductions, property disposals, and capital gains."
        sectionNum={5}
        totalSections={8}
        onSave={onSave}
        onComplete={onComplete}
      />

      <InfoBox color="amber">
        Net rental income = Gross rent − Allowable deductions.
        Only <strong>revenue expenditure</strong> is deductible
        (maintenance, insurance, interest) — capital
        improvements are not. Capital Gains Tax at 10% applies
        to disposals within 10 years of acquisition (assets
        acquired from Sep 1, 2022 onwards).
      </InfoBox>

      <Card
        title="Rental Properties"
        subtitle="Add each property separately — residential, commercial, industrial, or land leases"
        icon={Home}
        accent={C.amber}
        defaultOpen
        badge={`${props.length} propert${props.length !== 1 ? "ies" : "y"}`}
        badgeColor={C.amber}
      >
        <Builder
          items={props}
          onAdd={() => patch({ properties: [...props, blankProp()] })}
          onRemove={(i) =>
            patch({ properties: props.filter((_, j) => j !== i) })
          }
          onChange={(i, k, v) =>
            patch({ properties: props.map((e, j) => (j === i ? { ...e, [k]: v } : e)) })
          }
          addLabel="Add Rental Property"
          entryLabel="Property"
          render={(p, _i, u) => (
            <Stack>
              <G3>
                <Select
                  label="Property Type"
                  value={p.type}
                  onChange={(v) => u("type", v)}
                  options={[
                    {
                      value: "residential",
                      label: "Residential House",
                    },
                    {
                      value: "apartment",
                      label: "Apartment / Condo",
                    },
                    {
                      value: "commercial",
                      label: "Commercial Space",
                    },
                    {
                      value: "industrial",
                      label: "Industrial / Warehouse",
                    },
                    {
                      value: "land",
                      label: "Bare Land / Plot",
                    },
                  ]}
                />
                <Select
                  label="Usage / Occupancy Status"
                  value={p.usage}
                  onChange={(v) => u("usage", v)}
                  options={[
                    {
                      value: "rented",
                      label: "Fully Rented Out",
                    },
                    {
                      value: "partial",
                      label: "Partially Rented",
                    },
                    {
                      value: "seasonal",
                      label: "Seasonal / Airbnb / Short-stay",
                    },
                    {
                      value: "own",
                      label: "Owner-Occupied (no rental)",
                    },
                  ]}
                />
                <Field
                  label="Months Rented in the Year"
                  value={p.months}
                  onChange={(v) => u("months", v)}
                  type="number"
                  suffix="months"
                />
              </G3>
              <Field
                label="Full Property Address"
                value={p.addr}
                onChange={(v) => u("addr", v)}
                required
                placeholder="Include unit number, building, street, city"
              />
              <G3>
                <AmountField
                  label="Monthly Rent (LKR)"
                  value={p.rent}
                  onChange={(v) => u("rent", v)}
                  required
                />
                <AmountField
                  label="Gross Annual Rental Income (LKR)"
                  value={p.gross}
                  onChange={(v) => u("gross", v)}
                  required
                  hint="Monthly rent × months rented"
                />
                <Select
                  label="Jointly Owned?"
                  value={p.joint}
                  onChange={(v) => u("joint", v)}
                  options={[
                    { value: "no", label: "No — Solely Owned" },
                    {
                      value: "yes",
                      label: "Yes — Joint / Co-ownership",
                    },
                  ]}
                />
              </G3>
              {p.joint === "yes" && (
                <Field
                  label="Your Ownership Share (%)"
                  value={p.share}
                  onChange={(v) => u("share", v)}
                  type="number"
                  suffix="%"
                  hint="Your proportional share of rental income"
                />
              )}
              <Rule label="ALLOWABLE DEDUCTIONS" />
              <G3>
                <AmountField
                  label="Maintenance & Repairs (LKR)"
                  value={p.maintenance}
                  onChange={(v) => u("maintenance", v)}
                  hint="Revenue repairs only — not capital improvements"
                />
                <AmountField
                  label="Property Insurance Premium (LKR)"
                  value={p.insurance}
                  onChange={(v) => u("insurance", v)}
                />
                <AmountField
                  label="Mortgage Interest Paid (LKR)"
                  value={p.mortgage}
                  onChange={(v) => u("mortgage", v)}
                  hint="Interest component only, not principal"
                />
              </G3>
              <G2>
                <AmountField
                  label="Property Management Fees (LKR)"
                  value={p.mgmt}
                  onChange={(v) => u("mgmt", v)}
                  hint="Agent commissions, HOA fees"
                />
                <AmountField
                  label="Other Allowable Expenses (LKR)"
                  value={p.other}
                  onChange={(v) => u("other", v)}
                  hint="Ground rent, legal fees, utility bills paid by landlord"
                />
              </G2>
            </Stack>
          )}
        />
      </Card>

      <Card
        title="Property Disposals & Capital Gains Tax"
        subtitle="Sale, gift, or transfer of land or buildings during the year"
        icon={Building2}
        accent={C.red}
        optional
      >
        <Stack>
          <Toggle
            label="I sold, transferred, or otherwise disposed of a property this year"
            subLabel="Applies to land, houses, apartments, and commercial properties — CGT at 10% may apply"
            checked={s.hasDisposal}
            onChange={(v) => patch({ hasDisposal: v })}
          />
          {s.hasDisposal && (
            <>
              <InfoBox color="red">
                CGT applies to assets acquired from 1 September
                2022 and disposed within 10 years. The gain is
                calculated as: Sale Consideration − (Original
                Cost + Capital Improvement Costs + Disposal
                Expenses). A 10% flat rate applies.
              </InfoBox>
              <G3>
                <Field
                  label="Property Address"
                  value={s.disposalAddr}
                  onChange={(v) => patch({ disposalAddr: v })}
                  required
                />
                <DateField
                  label="Original Acquisition Date"
                  value={s.disposalAcquired}
                  onChange={(v) => patch({ disposalAcquired: v })}
                  required
                />
                <DateField
                  label="Date of Sale / Disposal"
                  value={s.disposalDisposed}
                  onChange={(v) => patch({ disposalDisposed: v })}
                  required
                />
              </G3>
              <G3>
                <AmountField
                  label="Original Acquisition Cost (LKR)"
                  value={s.disposalCost}
                  onChange={(v) => patch({ disposalCost: v })}
                  required
                />
                <AmountField
                  label="Sale Consideration / Price (LKR)"
                  value={s.disposalProceeds}
                  onChange={(v) => patch({ disposalProceeds: v })}
                  required
                />
                <AmountField
                  label="Incidental Disposal Costs (LKR)"
                  value={s.disposalExpenses}
                  onChange={(v) => patch({ disposalExpenses: v })}
                  hint="Legal fees, agent commission, stamp duty"
                />
              </G3>
            </>
          )}
        </Stack>
      </Card>

      <Card
        title="Land Subdivision & Development Income"
        subtitle="Income from subdividing, developing, or selling plots of land"
        icon={MapPin}
        accent={C.purple}
        optional
      >
        <Stack>
          <Toggle
            label="I earned income from land development, subdivision, or plot sales"
            checked={s.hasLand}
            onChange={(v) => patch({ hasLand: v })}
          />
          {s.hasLand && (
            <G3>
              <Field
                label="Location / District"
                value={s.landAddr}
                onChange={(v) => patch({ landAddr: v })}
              />
              <Select
                label="Activity Type"
                value={s.landType}
                onChange={(v) => patch({ landType: v })}
                options={[
                  {
                    value: "subdivision",
                    label: "Subdivision & Plot Sales",
                  },
                  {
                    value: "development",
                    label: "Property Development",
                  },
                  {
                    value: "construction",
                    label: "Construction for Sale",
                  },
                ]}
              />
              <AmountField
                label="Gross Income from Land Activity (LKR)"
                value={s.landRevenue}
                onChange={(v) => patch({ landRevenue: v })}
                required
              />
            </G3>
          )}
        </Stack>
      </Card>
    </Stack>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// SECTION 6 — Deductions, Insurances & Qualifying Reliefs
// ─────────────────────────────────────────────────────────────────────────────

function Sec6({ detail, onDetailChange, onComplete, onSave }: SecProps) {
  const s = detail.section6;
  const patch = (p: Partial<typeof s>) => patchDetail(detail, onDetailChange, "section6", p);

  return (
    <Stack gap={16}>
      <SectionHeader
        icon={Shield}
        color={C.green}
        title="Deductions, Insurances & Qualifying Reliefs"
        subtitle="Claim all eligible deductions and reliefs to legitimately reduce your taxable income."
        sectionNum={6}
        totalSections={8}
        onSave={onSave}
        onComplete={onComplete}
      />

      <InfoBox color="green">
        Total <strong>Qualifying Payment</strong> deductions are
        capped at the lower of: (a) 1/3 of assessable income, or
        (b) LKR 1,200,000. The personal relief of LKR 3,000,000
        is automatically applied. Keep receipts for all claimed
        amounts for at least 5 years.
      </InfoBox>

      {/* Auto-applied */}
      <Card
        title="Automatic Reliefs & Pre-filled Credits"
        subtitle="These are applied automatically — no action required"
        icon={CheckCircle}
        accent={C.teal}
        defaultOpen
      >
        <div className="trp-auto-relief-grid">
          {[
            {
              label: "Personal Relief",
              value: "LKR 3,000,000",
              note: "Auto-applied for all residents",
              color: C.teal,
            },
            {
              label: "EPF Employee Deduction",
              value: "LKR 162,000",
              note: "Pre-filled from Section 2",
              color: C.green,
            },
            {
              label: "APIT Tax Credit",
              value: "LKR 108,000",
              note: "Pre-filled from Section 2",
              color: C.blue,
            },
          ].map(({ label, value, note, color }) => (
            <div key={label} className="trp-auto-relief-card" style={{ border: `1px solid ${color}20` }}>
              <div className="trp-auto-relief-header">
                <CheckCircle size={12} style={{ color }} />
                <span className="trp-auto-relief-label">{label}</span>
              </div>
              <div className="trp-auto-relief-value" style={{ color }}>
                {value}
              </div>
              <div className="trp-auto-relief-note">{note}</div>
            </div>
          ))}
        </div>
      </Card>

      <Card
        title="Life Insurance Premiums"
        subtitle="Premiums paid on life, endowment, annuity, and whole-life policies"
        icon={Shield}
        accent={C.purple}
      >
        <Stack>
          <Toggle
            label="I paid life insurance premiums during the year"
            subLabel="Only policies from Sri Lankan-registered insurers qualify for the deduction"
            checked={s.hasLife}
            onChange={(v) => patch({ hasLife: v })}
          />
          {s.hasLife && (
            <G3>
              <AmountField
                label="Total Annual Premium Paid (LKR)"
                value={s.lifePremium}
                onChange={(v) => patch({ lifePremium: v })}
                required
                hint="Across all qualifying life policies"
              />
              <Field
                label="Insurance Company"
                value={s.lifeInsurer}
                onChange={(v) => patch({ lifeInsurer: v })}
                placeholder="e.g. AIA Life, Ceylinco, Union Assurance"
              />
              <Field
                label="Policy Number(s)"
                value={s.lifePolicy}
                onChange={(v) => patch({ lifePolicy: v })}
                mono
                placeholder="List all relevant policy numbers"
              />
            </G3>
          )}
        </Stack>
      </Card>

      <Card
        title="Medical & Health Insurance"
        subtitle="Private health insurance premiums for you and your family"
        icon={FileText}
        accent={C.blue}
        optional
      >
        <Stack>
          <Toggle
            label="I paid medical / health insurance premiums"
            checked={s.hasMedical}
            onChange={(v) => patch({ hasMedical: v })}
          />
          {s.hasMedical && (
            <G2>
              <AmountField
                label="Total Medical Insurance Premium (LKR)"
                value={s.medicalPremium}
                onChange={(v) => patch({ medicalPremium: v })}
                required
              />
              <Field
                label="Insurance Provider"
                value={s.medicalInsurer}
                onChange={(v) => patch({ medicalInsurer: v })}
              />
            </G2>
          )}
        </Stack>
      </Card>

      <Card
        title="Qualifying Payments — Donations & Charitable Contributions"
        subtitle="Donations to IRD-approved charities, religious bodies, and government relief funds"
        icon={Award}
        accent={C.amber}
        optional
      >
        <Stack>
          <Toggle
            label="I made donations to IRD-approved charitable or government institutions"
            subLabel="Maintain receipts and the donee's IRD approval letter"
            checked={s.hasCharitable}
            onChange={(v) => patch({ hasCharitable: v })}
          />
          {s.hasCharitable && (
            <>
              <G2>
                <AmountField
                  label="President's Fund / Disaster Relief Fund (LKR)"
                  value={s.charitablePresident}
                  onChange={(v) => patch({ charitablePresident: v })}
                  hint="Fully deductible"
                />
                <AmountField
                  label="Approved Charitable Institutions (LKR)"
                  value={s.charitableApproved}
                  onChange={(v) => patch({ charitableApproved: v })}
                  hint="Must hold current IRD approval"
                />
              </G2>
              <G2>
                <AmountField
                  label="Religious / Educational Institutions (LKR)"
                  value={s.charitableReligious}
                  onChange={(v) => patch({ charitableReligious: v })}
                  hint="Must hold current IRD approval"
                />
                <AmountField
                  label="Other Approved Donations (LKR)"
                  value={s.charitableOther}
                  onChange={(v) => patch({ charitableOther: v })}
                />
              </G2>
            </>
          )}
        </Stack>
      </Card>

      <Card
        title="Education Fees for Dependant Children"
        subtitle="School tuition fees paid for qualifying dependant children under 18"
        icon={FileCheck}
        accent={C.teal}
        optional
      >
        <Stack>
          <Toggle
            label="I paid school or tuition fees for qualifying dependant children"
            subLabel="Institution must be IRD-approved; fees for overseas institutions generally do not qualify"
            checked={s.hasEducation}
            onChange={(v) => patch({ hasEducation: v })}
          />
          {s.hasEducation && (
            <G3>
              <Field
                label="School / Institution Name"
                value={s.educationSchool}
                onChange={(v) => patch({ educationSchool: v })}
                required
              />
              <AmountField
                label="Annual Fees Paid (LKR)"
                value={s.educationFees}
                onChange={(v) => patch({ educationFees: v })}
                required
              />
              <Field
                label="Number of Qualifying Children"
                value={s.educationChildren}
                onChange={(v) => patch({ educationChildren: v })}
                type="number"
                hint="Only children under 18 enrolled full-time"
              />
            </G3>
          )}
        </Stack>
      </Card>

      <Card
        title="Approved Pension & Superannuation Fund Contributions"
        subtitle="Voluntary contributions beyond statutory EPF to approved retirement schemes"
        icon={PiggyBank}
        accent={C.green}
        optional
      >
        <Stack>
          <Toggle
            label="I made voluntary contributions to an approved pension or superannuation fund"
            checked={s.hasPension}
            onChange={(v) => patch({ hasPension: v })}
          />
          {s.hasPension && (
            <G3>
              <Field
                label="Fund Name"
                value={s.pensionFund}
                onChange={(v) => patch({ pensionFund: v })}
                placeholder="e.g. ETF, SLA Pension Fund"
              />
              <Select
                label="Fund Type"
                value={s.pensionType}
                onChange={(v) => patch({ pensionType: v })}
                options={[
                  { value: "etf", label: "ETF Voluntary" },
                  {
                    value: "epf-vol",
                    label: "EPF Voluntary Additional",
                  },
                  {
                    value: "super",
                    label: "Approved Superannuation Fund",
                  },
                  {
                    value: "pension",
                    label: "Registered Pension Scheme",
                  },
                ]}
              />
              <AmountField
                label="Annual Contribution (LKR)"
                value={s.pensionAmount}
                onChange={(v) => patch({ pensionAmount: v })}
                required
              />
            </G3>
          )}
        </Stack>
      </Card>

      <Card
        title="Housing Loan Interest Relief"
        subtitle="Interest on home loans from approved financial institutions for primary owner-occupied residence only"
        icon={Home}
        accent={C.amber}
        optional
      >
        <Stack>
          <Toggle
            label="I am repaying a housing loan for my primary owner-occupied home"
            subLabel="Only the interest portion qualifies — principal repayments are not deductible"
            checked={s.hasMortgage}
            onChange={(v) => patch({ hasMortgage: v })}
          />
          {s.hasMortgage && (
            <G3>
              <Select
                label="Lending Institution"
                value={s.mortgageBank}
                onChange={(v) => patch({ mortgageBank: v })}
                options={BANKS}
                required
              />
              <Field
                label="Loan Account Number"
                value={s.mortgageAccount}
                onChange={(v) => patch({ mortgageAccount: v })}
                mono
              />
              <AmountField
                label="Annual Mortgage Interest Paid (LKR)"
                value={s.mortgageInterest}
                onChange={(v) => patch({ mortgageInterest: v })}
                required
                hint="From your annual loan statement"
              />
            </G3>
          )}
        </Stack>
      </Card>

      <Card
        title="Research & Development Expenditure"
        subtitle="Qualifying R&D costs linked to your business — eligible for 3× deduction"
        icon={Zap}
        accent={C.red}
        optional
      >
        <Stack>
          <Toggle
            label="I incurred qualifying R&D expenditure linked to my business"
            subLabel="Approved R&D may be deductible at 3× the actual amount under IRA Schedule 1"
            checked={s.hasRD}
            onChange={(v) => patch({ hasRD: v })}
          />
          {s.hasRD && (
            <>
              <G2>
                <AmountField
                  label="Total R&D Expenditure (LKR)"
                  value={s.rdAmount}
                  onChange={(v) => patch({ rdAmount: v })}
                  required
                />
              </G2>
              <Textarea
                label="Description of R&D Activity"
                value={s.rdDescription}
                onChange={(v) => patch({ rdDescription: v })}
                placeholder="Describe the nature of research/development and its connection to your business"
              />
            </>
          )}
        </Stack>
      </Card>

      <Card
        title="Disability Relief"
        subtitle="Additional relief if you or a qualifying dependant has a certified disability"
        icon={User}
        accent={C.blue}
        optional
      >
        <Stack>
          <Toggle
            label="I or a certified dependant qualifies for disability relief"
            checked={s.hasDisability}
            onChange={(v) => patch({ hasDisability: v })}
            subLabel="Attach a certified medical certificate from a government hospital"
          />
          {s.hasDisability && (
            <G2>
              <Select
                label="Disability Category"
                value={s.disabilityCategory}
                onChange={(v) => patch({ disabilityCategory: v })}
                options={[
                  { value: "self", label: "Myself" },
                  { value: "child", label: "Dependant Child" },
                  { value: "spouse", label: "Spouse" },
                  {
                    value: "parent",
                    label: "Parent / Guardian",
                  },
                ]}
              />
              <AmountField
                label="Additional Relief Amount (LKR)"
                value={s.disabilityAmount}
                onChange={(v) => patch({ disabilityAmount: v })}
                hint="As per IRD disability relief schedule"
              />
            </G2>
          )}
        </Stack>
      </Card>
    </Stack>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// SECTION 7 — Foreign Income & Overseas Assets
// ─────────────────────────────────────────────────────────────────────────────

function Sec7({ detail, onDetailChange, onComplete, onSave }: SecProps) {
  const s = detail.section7;
  const patch = (p: Partial<typeof s>) => patchDetail(detail, onDetailChange, "section7", p);

  return (
    <Stack gap={16}>
      <SectionHeader
        icon={Globe}
        color={C.blue}
        title="Foreign Income & Overseas Assets"
        subtitle="As a resident, declare all worldwide income and claim DTA relief to avoid double taxation."
        sectionNum={7}
        totalSections={8}
        onSave={onSave}
        onComplete={onComplete}
      />

      <InfoBox color="blue">
        Sri Lanka has Double Taxation Agreements (DTAs) with 40+
        countries. If you paid tax abroad, you may claim a{" "}
        <strong>foreign tax credit</strong> limited to the lower
        of: (a) tax paid overseas, or (b) Sri Lanka tax
        attributable to that income. Always attach supporting
        documents (Form 16, tax receipts, CBSL conversion
        certificates).
      </InfoBox>

      <Card
        title="Foreign Employment Income"
        subtitle="Salary or professional fees from a non-Sri Lankan employer or while posted overseas"
        icon={Briefcase}
        accent={C.blue}
        optional
      >
        <Stack>
          <Toggle
            label="I received employment income from a foreign employer or while working abroad"
            checked={s.hasForEmp}
            onChange={(v) => patch({ hasForEmp: v })}
          />
          {s.hasForEmp && (
            <>
              <G3>
                <Field
                  label="Foreign Employer Name"
                  value={s.forEmpEmployer}
                  onChange={(v) => patch({ forEmpEmployer: v })}
                  required
                />
                <Select
                  label="Country of Employer"
                  value={s.forEmpCountry}
                  onChange={(v) => patch({ forEmpCountry: v })}
                  options={COUNTRIES}
                  required
                />
                <Select
                  label="Currency"
                  value={s.forEmpCurrency}
                  onChange={(v) => patch({ forEmpCurrency: v })}
                  options={CURRENCIES}
                />
              </G3>
              <G3>
                <Field
                  label="Gross Salary (Foreign Currency)"
                  value={s.forEmpFgross}
                  onChange={(v) => patch({ forEmpFgross: v })}
                  mono
                  required
                />
                <Field
                  label="CBSL Buying Rate (LKR per 1 unit)"
                  value={s.forEmpRate}
                  onChange={(v) => patch({ forEmpRate: v })}
                  mono
                  hint="Use rate on date of receipt — CBSL.gov.lk"
                />
                <AmountField
                  label="LKR Equivalent Amount"
                  value={s.forEmpLkr}
                  onChange={(v) => patch({ forEmpLkr: v })}
                  required
                />
              </G3>
              <G2>
                <AmountField
                  label="Foreign Tax Already Paid (LKR equivalent)"
                  value={s.forEmpFtax}
                  onChange={(v) => patch({ forEmpFtax: v })}
                  hint="Tax withheld or assessed in the source country"
                />
                <Select
                  label="DTA Treaty Available?"
                  value={s.forEmpDta}
                  onChange={(v) => patch({ forEmpDta: v })}
                  options={[
                    { value: "yes", label: "Yes — DTA Exists" },
                    { value: "no", label: "No — No DTA" },
                    {
                      value: "unsure",
                      label: "Unsure / Checking",
                    },
                  ]}
                  hint="Sri Lanka has DTAs with 40+ countries"
                />
              </G2>
            </>
          )}
        </Stack>
      </Card>

      <Card
        title="Foreign Business & Professional Income"
        subtitle="Consulting, freelance, or business income from overseas entities (not via online platforms)"
        icon={Building2}
        accent={C.purple}
        optional
      >
        <Stack>
          <Toggle
            label="I earned business or professional income from overseas clients / entities"
            checked={s.hasForBiz}
            onChange={(v) => patch({ hasForBiz: v })}
          />
          {s.hasForBiz && (
            <G4>
              <Field
                label="Nature of Business"
                value={s.forBizDescription}
                onChange={(v) => patch({ forBizDescription: v })}
              />
              <Select
                label="Primary Source Country"
                value={s.forBizCountry}
                onChange={(v) => patch({ forBizCountry: v })}
                options={COUNTRIES}
              />
              <AmountField
                label="Gross Revenue (LKR equivalent)"
                value={s.forBizRevenue}
                onChange={(v) => patch({ forBizRevenue: v })}
                required
              />
              <AmountField
                label="Foreign Tax Paid (LKR)"
                value={s.forBizFtax}
                onChange={(v) => patch({ forBizFtax: v })}
              />
            </G4>
          )}
        </Stack>
      </Card>

      <Card
        title="Foreign Dividends & Overseas Investment Income"
        subtitle="Dividends, interest, and returns from overseas companies or funds"
        icon={TrendingUp}
        accent={C.green}
        optional
      >
        <Stack>
          <Toggle
            label="I received dividends or investment returns from foreign sources"
            checked={s.hasForDiv}
            onChange={(v) => patch({ hasForDiv: v })}
          />
          {s.hasForDiv && (
            <G4>
              <Field
                label="Company / Fund Name"
                value={s.forDivCompany}
                onChange={(v) => patch({ forDivCompany: v })}
                required
              />
              <Select
                label="Country"
                value={s.forDivCountry}
                onChange={(v) => patch({ forDivCountry: v })}
                options={COUNTRIES}
              />
              <AmountField
                label="Gross Dividend / Income (LKR)"
                value={s.forDivTotal}
                onChange={(v) => patch({ forDivTotal: v })}
                required
              />
              <AmountField
                label="Foreign WHT Deducted (LKR)"
                value={s.forDivFtax}
                onChange={(v) => patch({ forDivFtax: v })}
              />
            </G4>
          )}
        </Stack>
      </Card>

      <Card
        title="Overseas Property Ownership"
        subtitle="Declaration of real estate assets held outside Sri Lanka"
        icon={Home}
        accent={C.amber}
        optional
      >
        <Stack>
          <Toggle
            label="I own real estate or property located outside Sri Lanka"
            subLabel="Mandatory disclosure — failure to declare is a tax offence under IRA 2017 Section 189"
            checked={s.hasForProp}
            onChange={(v) => patch({ hasForProp: v })}
          />
          {s.hasForProp && (
            <>
              <InfoBox color="amber">
                Rental income from overseas property is taxable
                at normal rates. Attach a copy of the title
                deed, lease agreement, and foreign tax receipts.
                CGT on overseas property disposals may also
                apply.
              </InfoBox>
              <G3>
                <Select
                  label="Country"
                  value={s.forPropCountry}
                  onChange={(v) => patch({ forPropCountry: v })}
                  options={COUNTRIES}
                  required
                />
                <Field
                  label="Property Address (Overseas)"
                  value={s.forPropAddr}
                  onChange={(v) => patch({ forPropAddr: v })}
                  required
                />
                <Select
                  label="Property Type"
                  value={s.forPropType}
                  onChange={(v) => patch({ forPropType: v })}
                  options={[
                    {
                      value: "residential",
                      label: "Residential",
                    },
                    {
                      value: "commercial",
                      label: "Commercial",
                    },
                    { value: "land", label: "Land" },
                  ]}
                />
              </G3>
              <G2>
                <AmountField
                  label="Rental Income (LKR equivalent)"
                  value={s.forPropRental}
                  onChange={(v) => patch({ forPropRental: v })}
                />
                <AmountField
                  label="Foreign Tax Paid on Rental (LKR)"
                  value={s.forPropFtax}
                  onChange={(v) => patch({ forPropFtax: v })}
                />
              </G2>
            </>
          )}
        </Stack>
      </Card>

      <Card
        title="Double Taxation Agreement (DTA) Relief Claim"
        subtitle="Claim foreign tax credit to eliminate double taxation on internationally-taxed income"
        icon={FileCheck}
        accent={C.teal}
        optional
      >
        <Stack>
          <Toggle
            label="I am formally claiming DTA relief / foreign tax credit on my return"
            subLabel="Requires supporting documents: foreign tax certificate, Form IT-2025-DTA"
            checked={s.hasDTA}
            onChange={(v) => patch({ hasDTA: v })}
          />
          {s.hasDTA && (
            <>
              <InfoBox color="teal">
                The credit is capped at the lower of: (i) actual
                foreign tax paid, or (ii) Sri Lanka tax
                attributable to the foreign income. Attach Form
                IT-DTA and the overseas tax authority's
                certificate confirming tax paid.
              </InfoBox>
              <G3>
                <Select
                  label="Treaty Country"
                  value={s.dtaCountry}
                  onChange={(v) => patch({ dtaCountry: v })}
                  options={COUNTRIES}
                  required
                />
                <AmountField
                  label="Foreign Tax Paid (LKR equivalent)"
                  value={s.dtaFtaxPaid}
                  onChange={(v) => patch({ dtaFtaxPaid: v })}
                  required
                />
                <AmountField
                  label="DTA Credit Claimed (LKR)"
                  value={s.dtaCreditClaimed}
                  onChange={(v) => patch({ dtaCreditClaimed: v })}
                  hint="Cannot exceed Sri Lanka tax on same income"
                />
              </G3>
            </>
          )}
        </Stack>
      </Card>
    </Stack>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// SECTION 8 — Review & Declaration
// ─────────────────────────────────────────────────────────────────────────────

function Sec8({
  detail,
  onDetailChange,
  completedSections,
}: {
  detail: TaxReturnDetail;
  onDetailChange: (d: TaxReturnDetail) => void;
  completedSections: Set<number>;
}) {
  const s = detail.section8;
  const patch = (p: Partial<typeof s>) => patchDetail(detail, onDetailChange, "section8", p);
  const agreed = s.agreed;

  const income = [
    {
      label: "Employment Income (Gross)",
      value: "LKR 1,800,000",
      color: C.primary,
    },
    {
      label: "Commission & Bonus",
      value: "LKR 150,000",
      color: C.primary,
    },
    {
      label: "Taxable Allowances & Perquisites",
      value: "LKR 60,000",
      color: C.primary,
    },
    {
      label: "Freelance / Business Income",
      value: "LKR 62,500",
      color: C.primary,
    },
    {
      label: "Rental Income (Gross)",
      value: "LKR 420,000",
      color: C.primary,
    },
    {
      label: "Dividend Income (Final Tax)",
      value: "LKR 0 *",
      color: C.muted,
    },
    {
      label: "FD Interest Income (Final Tax)",
      value: "LKR 0 *",
      color: C.muted,
    },
    { label: "Foreign Income", value: "LKR 0", color: C.muted },
  ];
  const deductions = [
    {
      label: "Less: Personal Relief",
      value: "− LKR 3,000,000",
      color: C.green,
    },
    {
      label: "Less: EPF Contribution (Employee)",
      value: "− LKR 162,000",
      color: C.green,
    },
    {
      label: "Less: Qualifying Payment Cap",
      value: "− LKR 72,000",
      color: C.green,
    },
    {
      label: "Less: Rental Allowable Expenses",
      value: "− LKR 21,000",
      color: C.green,
    },
  ];
  const tax = [
    {
      label: "Taxable Income",
      value: "LKR 0",
      color: C.teal,
      bold: true,
    },
    {
      label: "Gross Tax Payable",
      value: "LKR 285,000",
      color: C.red,
      bold: false,
    },
    {
      label: "Less: APIT Credit",
      value: "− LKR 108,000",
      color: C.green,
    },
    {
      label: "Less: WHT Credits (FD, Dividends)",
      value: "− LKR 4,812",
      color: C.green,
    },
    {
      label: "NET TAX PAYABLE",
      value: "LKR 172,188",
      color: C.amber,
      bold: true,
    },
  ];

  const SECTION_NAMES: Record<number, string> = {
    1: "Taxpayer Identity & Statutory Status",
    2: "Employment & Remuneration",
    3: "Fixed Deposits & Financial Investments",
    4: "Business, Freelance & Secondary Trades",
    5: "Real Estate & Rental Incomes",
    6: "Deductions, Insurances & Qualifying Reliefs",
    7: "Foreign Income & Overseas Assets",
  };

  const allComplete = [1, 2, 3, 4, 5, 6, 7].every((n) =>
    completedSections.has(n),
  );

  return (
    <Stack gap={16}>
      <div
      >
        <div
        >
          <div
          >
            <FileCheck size={22} />
          </div>
          <div>
            <div
            >
              SECTION 8 OF 8
            </div>
            <h2
            >
              Review & Declaration
            </h2>
            <p
            >
              Verify your income summary, confirm all sections
              are complete, and submit your return.
            </p>
          </div>
        </div>
      </div>

      {/* Summary stats */}
      <div
      >
        {[
          {
            label: "Gross Assessable Income",
            value: "LKR 2,492,500",
            color: C.primary,
          },
          {
            label: "Total Deductions",
            value: "LKR 3,255,000",
            color: C.green,
          },
          {
            label: "Estimated Tax Payable",
            value: "LKR 172,188",
            color: C.amber,
          },
          {
            label: "Compliance Score",
            value: "94 / 100",
            color: C.teal,
          },
        ].map(({ label, value, color }) => (
          <StatChip
            key={label}
            label={label}
            value={value}
            color={color}
          />
        ))}
      </div>

      <Card
        title="Income & Tax Computation Summary"
        subtitle="Auto-computed from all declared sections — verify before submission"
        icon={FileText}
        accent={C.teal}
        defaultOpen
      >
        <Stack gap={0}>
          <div className="trp-summary-section-label">INCOME ITEMS</div>
          {income.map(({ label, value, color }) => (
            <div key={label} className="trp-summary-row">
              <span className="trp-text-secondary">{label}</span>
              <span className="trp-font-mono trp-text-secondary" style={{ color }}>
                {value}
              </span>
            </div>
          ))}
          <div className="trp-spacer-sm" />
          <div className="trp-summary-section-label">DEDUCTIONS & RELIEFS</div>
          {deductions.map(({ label, value, color }) => (
            <div key={label} className="trp-summary-row">
              <span className="trp-text-secondary">{label}</span>
              <span className="trp-font-mono" style={{ color }}>
                {value}
              </span>
            </div>
          ))}
          <div className="trp-spacer-sm" />
          <div className="trp-summary-section-label">TAX COMPUTATION</div>
          {tax.map(({ label, value, color, bold }) => (
            <div
              key={label}
              className={cn("trp-summary-row", bold && "trp-summary-row--bold")}
              style={bold ? { borderBottomColor: `${color}30`, background: `${color}08` } : undefined}
            >
              <span className={bold ? "trp-text-primary font-bold" : "trp-text-secondary"}>
                {label}
              </span>
              <span
                className="trp-font-mono"
                style={{ color, fontSize: bold ? 16 : 13, fontWeight: bold ? 700 : 500 }}
              >
                {value}
              </span>
            </div>
          ))}
          <div className="trp-text-muted mt-2.5 text-[11px]">
            * Dividend and FD interest income are subject to
            final WHT — included above for disclosure only.
          </div>
        </Stack>
      </Card>

      <Card
        title="Section Completion Checklist"
        subtitle="All sections must be complete before filing"
        icon={CheckCircle}
        accent={C.green}
      >
        <Stack gap={10}>
          {Object.entries(SECTION_NAMES).map(([num, name]) => {
            const done = completedSections.has(Number(num));
            return (
              <div
                key={num}
              >
                {done ? (
                  <CheckCircle
                    size={15}
                  />
                ) : (
                  <AlertCircle
                    size={15}
                  />
                )}
                <span
                >
                  Section {num} — {name}
                </span>
                <span
                >
                  {done ? "Complete" : "Incomplete"}
                </span>
              </div>
            );
          })}
        </Stack>
      </Card>

      <Card
        title="Statutory Declaration"
        subtitle="This declaration is legally binding under IRA 2017 — read carefully"
        icon={FileCheck}
        accent={C.red}
      >
        <Stack>
          <div
          >
            <p
            >
              I, the undersigned, hereby solemnly declare that
              all the information furnished in this return —
              including all schedules, statements, and
              supporting documents annexed hereto — is true,
              correct, and complete to the best of my knowledge
              and belief. I confirm that no part of my income
              assessable to tax under the Inland Revenue Act No.
              24 of 2017 has been intentionally omitted or
              misrepresented.
              <br />
              <br />I am fully aware that making a false
              declaration, concealing income, or providing
              misleading information is a criminal offence under
              Section 189 of the IRA 2017 and may result in
              penalties, surcharge taxes, and prosecution.
            </p>
          </div>
          <Toggle
            label="I agree to the above statutory declaration and confirm all information is accurate"
            subLabel="This constitutes your legal signature and agreement under the Inland Revenue Act 2017"
            checked={s.agreed}
            onChange={(v) => patch({ agreed: v })}
          />
          {!allComplete && (
            <InfoBox color="amber">
              ⚠ Some sections are still incomplete. Please
              return to those sections and mark them complete
              before submitting your return.
            </InfoBox>
          )}
          <div>
            <button
              type="button"
              disabled={!agreed || !allComplete}
            >
              <Send size={14} /> Submit Tax Return to IRD
            </button>
            <button
              type="button"
            >
              <Save size={13} /> Save as Draft
            </button>
          </div>
        </Stack>
      </Card>
    </Stack>
  );
}

export { Sec1, Sec2, Sec3, Sec4, Sec5, Sec6, Sec7, Sec8 };
