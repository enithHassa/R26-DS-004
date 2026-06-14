import type { BookingPerformanceRow, InquiryRow, PropertyPerformanceRow } from "../types";

export type NamedValue = { name: string; value: number };

export function uniqueSorted(values: string[]): string[] {
  return [...new Set(values)].sort();
}

export function filterPropertyRows(
  rows: PropertyPerformanceRow[],
  opts: { property?: string; month?: string },
): PropertyPerformanceRow[] {
  return rows.filter((r) => {
    if (opts.property && opts.property !== "all" && r.property !== opts.property) return false;
    if (opts.month && opts.month !== "all" && r.month !== opts.month) return false;
    return true;
  });
}

export function propertyPerformanceSummary(rows: PropertyPerformanceRow[]) {
  const revenue = rows.reduce((s, r) => s + (r.roomRevenue ?? 0), 0);
  const target = rows.reduce((s, r) => s + (r.monthlyTarget ?? 0), 0);
  const brns = rows.reduce((s, r) => s + (r.bookedRoomNights ?? 0), 0);
  const srn = rows.reduce((s, r) => s + (r.sellableRoomNights ?? 0), 0);
  const occValues = rows.map((r) => r.occupancy).filter((v): v is number => v != null);
  const avgOcc = occValues.length
    ? occValues.reduce((a, b) => a + b, 0) / occValues.length
    : srn > 0
      ? brns / srn
      : null;

  return {
    totalRevenue: revenue,
    totalTarget: target,
    targetAchievement: target > 0 ? revenue / target : null,
    totalBrns: brns,
    avgOccupancy: avgOcc,
    propertyCount: new Set(rows.map((r) => r.property)).size,
  };
}

export function groupSum(rows: { key: string; value: number }[]): NamedValue[] {
  const map = new Map<string, number>();
  for (const r of rows) {
    map.set(r.key, (map.get(r.key) ?? 0) + r.value);
  }
  return [...map.entries()]
    .map(([name, value]) => ({ name, value }))
    .sort((a, b) => b.value - a.value);
}

export function bookingMonthKey(dateStr: string): string {
  const m = toMonthKey(dateStr);
  return m ?? "unknown";
}

function toMonthKey(raw: string): string | null {
  if (/^\d{4}-\d{2}$/.test(raw)) return raw;
  const d = new Date(raw);
  if (Number.isNaN(d.getTime())) return null;
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
}

export function filterBookingsByMonth(rows: BookingPerformanceRow[], month: string) {
  if (month === "all") return rows;
  return rows.filter((r) => bookingMonthKey(r.bookingDate) === month);
}

export function bookingAggregates(rows: BookingPerformanceRow[]) {
  return {
    byCountry: groupSum(rows.map((r) => ({ key: r.country, value: r.roomRevenue }))),
    byChannel: groupSum(rows.map((r) => ({ key: r.channel, value: r.roomRevenue }))),
    byProperty: groupSum(rows.map((r) => ({ key: r.property, value: r.roomRevenue }))),
    byCountryNights: groupSum(rows.map((r) => ({ key: r.country, value: r.roomNights }))),
    totalRevenue: rows.reduce((s, r) => s + r.roomRevenue, 0),
    totalNights: rows.reduce((s, r) => s + r.roomNights, 0),
  };
}

export function filterInquiries(
  rows: InquiryRow[],
  opts: { start?: string; end?: string; channel?: string },
): InquiryRow[] {
  return rows.filter((r) => {
    const d = new Date(r.inquiryDate);
    if (opts.start && d < new Date(opts.start)) return false;
    if (opts.end && d > new Date(`${opts.end}T23:59:59`)) return false;
    if (opts.channel && opts.channel !== "all" && r.channel !== opts.channel) return false;
    return true;
  });
}

export function inquiryAggregates(rows: InquiryRow[]) {
  const byChannel = groupSum(rows.map((r) => ({ key: r.channel, value: r.inquiries })));
  const total = rows.reduce((s, r) => s + r.inquiries, 0);
  const dates = rows.map((r) => r.inquiryDate).sort();
  return {
    byChannel,
    total,
    dateMin: dates[0] ?? null,
    dateMax: dates[dates.length - 1] ?? null,
  };
}

export function inquiriesByDate(rows: InquiryRow[]): { date: string; inquiries: number }[] {
  const map = new Map<string, number>();
  for (const r of rows) {
    const key = r.inquiryDate.slice(0, 10);
    map.set(key, (map.get(key) ?? 0) + r.inquiries);
  }
  return [...map.entries()]
    .map(([date, inquiries]) => ({ date, inquiries }))
    .sort((a, b) => a.date.localeCompare(b.date));
}
