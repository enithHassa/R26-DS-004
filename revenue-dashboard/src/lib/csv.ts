import type {
  BookingPerformanceRow,
  CsvParseResult,
  InquiryRow,
  PropertyPerformanceRow,
} from "../types";

function normalizeHeader(h: string): string {
  return h
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_|_$/g, "");
}

function parseCsvText(text: string): string[][] {
  const rows: string[][] = [];
  let row: string[] = [];
  let cell = "";
  let inQuotes = false;

  for (let i = 0; i < text.length; i++) {
    const ch = text[i];
    const next = text[i + 1];

    if (inQuotes) {
      if (ch === '"' && next === '"') {
        cell += '"';
        i++;
      } else if (ch === '"') {
        inQuotes = false;
      } else {
        cell += ch;
      }
      continue;
    }

    if (ch === '"') {
      inQuotes = true;
    } else if (ch === ",") {
      row.push(cell);
      cell = "";
    } else if (ch === "\n" || (ch === "\r" && next === "\n")) {
      row.push(cell);
      cell = "";
      if (row.some((c) => c.trim() !== "")) rows.push(row);
      row = [];
      if (ch === "\r") i++;
    } else if (ch !== "\r") {
      cell += ch;
    }
  }

  if (cell.length > 0 || row.length > 0) {
    row.push(cell);
    if (row.some((c) => c.trim() !== "")) rows.push(row);
  }

  return rows;
}

function toNumber(raw: string): number | null {
  const s = raw.trim();
  if (!s || s === "-" || s.toLowerCase() === "na") return null;
  const n = Number(s.replace(/,/g, ""));
  return Number.isFinite(n) ? n : null;
}

function toMonth(raw: string): string | null {
  const s = raw.trim();
  if (!s) return null;
  if (/^\d{4}-\d{2}$/.test(s)) return s;
  const d = new Date(s);
  if (!Number.isNaN(d.getTime())) {
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, "0");
    return `${y}-${m}`;
  }
  return null;
}

function mapRow(headers: string[], values: string[]): Record<string, string> {
  const out: Record<string, string> = {};
  headers.forEach((h, i) => {
    out[h] = values[i]?.trim() ?? "";
  });
  return out;
}

function pick(row: Record<string, string>, aliases: string[]): string {
  for (const alias of aliases) {
    const v = row[alias];
    if (v !== undefined && v !== "") return v;
  }
  return "";
}

export function parsePropertyPerformanceCsv(text: string): CsvParseResult<PropertyPerformanceRow> {
  const grid = parseCsvText(text);
  if (grid.length < 2) return { ok: false, error: "CSV must include a header row and at least one data row." };

  const headers = grid[0].map(normalizeHeader);
  const warnings: string[] = [];
  const rows: PropertyPerformanceRow[] = [];

  for (let i = 1; i < grid.length; i++) {
    const raw = mapRow(headers, grid[i]);
    const property = pick(raw, ["property", "property_name", "hotel", "villa"]);
    const month = toMonth(pick(raw, ["month", "period", "date"]));
    if (!property || !month) continue;

    const brns = toNumber(pick(raw, ["booked_room_nights", "brns", "booked_room_night"]));
    const srn = toNumber(pick(raw, ["sellable_room_nights", "srns", "sellable_room_night"]));
    let occ = toNumber(pick(raw, ["occupancy", "occ", "occupancy_rate"]));
    if (occ == null && brns != null && srn != null && srn > 0) {
      occ = brns / srn;
    }

    rows.push({
      property,
      month,
      bookedRoomNights: brns,
      availableDays: toNumber(pick(raw, ["available_days", "avail_days", "available_days_in_month"])),
      sellableRoomNights: srn,
      occupancy: occ,
      roomRevenue: toNumber(pick(raw, ["room_revenue", "revenue"])),
      monthlyTarget: toNumber(pick(raw, ["monthly_target", "target"])),
      tonikShare: toNumber(pick(raw, ["tonik_share", "tonik_share_lkr", "share"])),
    });
  }

  if (rows.length === 0) {
    return {
      ok: false,
      error:
        "No valid property rows found. Required columns: property, month, and metrics (booked_room_nights, room_revenue, etc.).",
    };
  }

  if (warnings.length) return { ok: true, rows, warnings };
  return { ok: true, rows, warnings: [] };
}

export function parseBookingPerformanceCsv(text: string): CsvParseResult<BookingPerformanceRow> {
  const grid = parseCsvText(text);
  if (grid.length < 2) return { ok: false, error: "CSV must include a header row and at least one data row." };

  const headers = grid[0].map(normalizeHeader);
  const rows: BookingPerformanceRow[] = [];

  for (let i = 1; i < grid.length; i++) {
    const raw = mapRow(headers, grid[i]);
    const property = pick(raw, ["property", "property_name", "hotel"]);
    const country = pick(raw, ["country", "guest_country", "market"]);
    const channel = pick(raw, ["channel", "booking_channel", "source"]);
    const bookingDate =
      pick(raw, ["booking_date", "check_in", "date", "month"]) ||
      toMonth(pick(raw, ["period"])) ||
      "";

    if (!property || !country || !channel) continue;

    const roomNights = toNumber(pick(raw, ["room_nights", "nights", "brns"])) ?? 1;
    const roomRevenue =
      toNumber(pick(raw, ["room_revenue", "revenue", "booking_value", "amount"])) ?? 0;

    rows.push({
      bookingDate: bookingDate || "unknown",
      property,
      country,
      channel,
      roomNights,
      roomRevenue,
    });
  }

  if (rows.length === 0) {
    return {
      ok: false,
      error:
        "No valid booking rows found. Required columns: property, country, channel, and room_revenue or room_nights.",
    };
  }

  return { ok: true, rows, warnings: [] };
}

export function parseInquiriesCsv(text: string): CsvParseResult<InquiryRow> {
  const grid = parseCsvText(text);
  if (grid.length < 2) return { ok: false, error: "CSV must include a header row and at least one data row." };

  const headers = grid[0].map(normalizeHeader);
  const rows: InquiryRow[] = [];

  for (let i = 1; i < grid.length; i++) {
    const raw = mapRow(headers, grid[i]);
    const channel = pick(raw, ["channel", "booking_channel", "source"]);
    const inquiryDate = pick(raw, ["inquiry_date", "date", "created_at"]);
    const count =
      toNumber(pick(raw, ["inquiries", "inquiry_count", "count", "number_of_inquiries"])) ?? 0;

    if (!channel || !inquiryDate) continue;

    const property = pick(raw, ["property", "property_name"]);
    rows.push({
      inquiryDate,
      channel,
      inquiries: count,
      property: property || undefined,
    });
  }

  if (rows.length === 0) {
    return {
      ok: false,
      error: "No valid inquiry rows found. Required columns: inquiry_date, channel, inquiries.",
    };
  }

  return { ok: true, rows, warnings: [] };
}

export async function readFileAsText(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result ?? ""));
    reader.onerror = () => reject(new Error("Failed to read file."));
    reader.readAsText(file);
  });
}
