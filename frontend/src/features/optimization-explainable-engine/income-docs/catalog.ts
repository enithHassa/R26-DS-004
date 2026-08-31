/** Additional income supporting documents — aligned to OE Income heads. */

export type IncomeDocCategoryId =
  | "employment"
  | "business"
  | "investment"
  | "other_income"
  | "terminal_benefits";

export type IncomeDocSlot = {
  slot_id: string;
  label: string;
  hint: string;
};

export type IncomeDocCategory = {
  category_id: IncomeDocCategoryId;
  display_name: string;
  section_badge: string;
  description: string;
  slots: IncomeDocSlot[];
};

/** Same four heads as Income + retirement/terminal, with typical invoice names. */
export const INCOME_DOC_CATEGORIES: IncomeDocCategory[] = [
  {
    category_id: "employment",
    display_name: "Employment Income",
    section_badge: "Sec 5",
    description: "Payslips and employer certificates that support employment amounts.",
    slots: [
      {
        slot_id: "emp_payslip",
        label: "Monthly payslip / salary slip",
        hint: "Latest YA payslips showing gross pay and deductions",
      },
      {
        slot_id: "emp_apit_t10",
        label: "APIT / T10 certificate",
        hint: "Employer withholding tax certificate for the year",
      },
      {
        slot_id: "emp_epf_statement",
        label: "EPF contribution statement",
        hint: "Employee EPF deductions for the year of assessment",
      },
      {
        slot_id: "emp_bonus_letter",
        label: "Bonus / commission letter",
        hint: "Employer letter or slip for bonus and commissions",
      },
      {
        slot_id: "emp_appointment",
        label: "Appointment / contract letter",
        hint: "Optional — confirms employment relationship",
      },
    ],
  },
  {
    category_id: "business",
    display_name: "Business Income",
    section_badge: "Sec 6",
    description: "Invoices and accounts that support business or freelance income.",
    slots: [
      {
        slot_id: "biz_sales_invoices",
        label: "Sales invoices / tax invoices",
        hint: "Customer invoices for the YA (sample or summary pack)",
      },
      {
        slot_id: "biz_expense_receipts",
        label: "Expense receipts",
        hint: "Material costs, rent, utilities, and other deductions",
      },
      {
        slot_id: "biz_bank_statement",
        label: "Business bank statement",
        hint: "Account statement covering the year of assessment",
      },
      {
        slot_id: "biz_trade_license",
        label: "Trade licence / BR registration",
        hint: "Business registration or municipal trade licence",
      },
    ],
  },
  {
    category_id: "investment",
    display_name: "Investment Income",
    section_badge: "Sec 7",
    description: "Certificates for interest, dividends, and other investment income.",
    slots: [
      {
        slot_id: "inv_fd_interest",
        label: "FD interest certificate",
        hint: "Bank certificate of interest credited in the YA",
      },
      {
        slot_id: "inv_wht_certificate",
        label: "WHT certificate",
        hint: "Withholding tax already deducted on interest or dividends",
      },
      {
        slot_id: "inv_dividend_warrant",
        label: "Dividend warrant / statement",
        hint: "Company dividend advice or CDS statement",
      },
      {
        slot_id: "inv_unit_trust",
        label: "Unit trust / fund statement",
        hint: "Distribution statement from the fund manager",
      },
      {
        slot_id: "inv_broker_note",
        label: "Broker contract note",
        hint: "CSE or broker notes for share disposals (if any)",
      },
    ],
  },
  {
    category_id: "other_income",
    display_name: "Other Income",
    section_badge: "Sec 8",
    description: "Receipts for royalties, prizes, and other miscellaneous income.",
    slots: [
      {
        slot_id: "oth_invoice",
        label: "Other income invoice / receipt",
        hint: "Invoice or receipt for the other-income amount claimed",
      },
      {
        slot_id: "oth_royalty",
        label: "Royalty / licence statement",
        hint: "If you received royalties or similar payments",
      },
      {
        slot_id: "oth_prize",
        label: "Prize / award letter",
        hint: "Letter confirming prize, award, or similar receipt",
      },
    ],
  },
  {
    category_id: "terminal_benefits",
    display_name: "Retirement & terminal benefits",
    section_badge: "IRA Act 24/2017",
    description:
      "Commuted pension, retiring gratuity, loss of office, or ETF at retirement — taxed on a special ladder.",
    slots: [
      {
        slot_id: "term_commuted_pension",
        label: "Commuted pension statement",
        hint: "Fund or employer statement of commuted pension paid",
      },
      {
        slot_id: "term_gratuity",
        label: "Retiring gratuity calculation",
        hint: "Employer gratuity letter with amount and service years",
      },
      {
        slot_id: "term_etf_withdrawal",
        label: "ETF withdrawal statement",
        hint: "ETF balance paid at retirement or cessation",
      },
      {
        slot_id: "term_loss_of_office",
        label: "Loss of office / compensation letter",
        hint: "Approved scheme letter if compensation for loss of office",
      },
    ],
  },
];

export function incomeDocCategory(id: IncomeDocCategoryId): IncomeDocCategory | undefined {
  return INCOME_DOC_CATEGORIES.find((c) => c.category_id === id);
}
