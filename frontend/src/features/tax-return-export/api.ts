import { optimizationExplainableApi } from "@/features/optimization-explainable-engine/api";

export type TaxReturnExportPayload = {
  header: {
    full_name: string;
    tin: string;
    assessment_year_label: string;
    reference_code: string;
  };
  income_breakdown: {
    employment: number;
    interest: number;
    business: number;
    rents: number;
    other: number;
    investment: number;
  };
  calculate_result: Record<string, unknown>;
  interest_lines: Array<{
    bank: string;
    source_type: string;
    withholding_agent_tin: string;
    wht_certificate_no: string;
    date: string;
    account_or_fd_no: string;
    type: string;
    fd_amount: number | null;
    gross_interest: number;
    wht: number;
  }>;
  pension: {
    pensioner_name: string;
    status_note: string;
    pension_number: string;
    lines: Array<{
      pen_date: string;
      bpen: number;
      cla: number;
      ota: number;
      spa: number;
      dsa: number;
      maa: number;
      sur: number;
      tded: number;
      tpen: number;
      pnet: number;
    }>;
  } | null;
  taxable_summary: {
    total_taxable_lkr: number;
    covered_month_count: number;
    missing_month_count: number;
    lines: Array<{
      class_key: string;
      calendar_month: string;
      taxable_amount_lkr: number;
      transaction_count: number;
    }>;
  } | null;
};

function filenameFromDisposition(header: string | undefined, fallback: string): string {
  if (!header) return fallback;
  const match = /filename="?([^";]+)"?/i.exec(header);
  return match?.[1]?.trim() || fallback;
}

/** POST OE Engine export endpoint; returns workbook blob + suggested filename. */
export async function downloadTaxReturnWorkbook(
  payload: TaxReturnExportPayload,
): Promise<{ blob: Blob; filename: string }> {
  const response = await optimizationExplainableApi.post("/export/tax-return", payload, {
    responseType: "blob",
  });
  const filename = filenameFromDisposition(
    response.headers["content-disposition"] as string | undefined,
    "Tax_Computation.xlsx",
  );
  return { blob: response.data as Blob, filename };
}

export function triggerBlobDownload(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}
