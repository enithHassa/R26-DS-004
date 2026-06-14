import { useMemo, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ComposedChart,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";

import {
  filterPropertyRows,
  propertyPerformanceSummary,
  uniqueSorted,
} from "../lib/compute";
import { formatLkr, formatMonthLabel, formatPercent } from "../lib/format";
import { useRevenueAnalyticsStore } from "../store";
import { ChartCard } from "./chart-card";
import { CsvUploadCard } from "./csv-upload-card";
import { EmptyState } from "./empty-state";
import { KpiStrip } from "./kpi-strip";

import {
  parsePropertyPerformanceCsv,
  readFileAsText,
} from "../lib/csv";

const CHART_COLORS = ["#0d6e6e", "#c9a227", "#3b82f6", "#f59e0b", "#8b5cf6", "#ec4899"];

export function PropertyPerformanceView() {
  const { propertyRows, propertyMeta, setPropertyData, clearProperty } = useRevenueAnalyticsStore();
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [filterProperty, setFilterProperty] = useState("all");
  const [filterMonth, setFilterMonth] = useState("all");

  const properties = useMemo(() => uniqueSorted(propertyRows.map((r) => r.property)), [propertyRows]);
  const months = useMemo(() => uniqueSorted(propertyRows.map((r) => r.month)), [propertyRows]);

  const filtered = useMemo(
    () => filterPropertyRows(propertyRows, { property: filterProperty, month: filterMonth }),
    [propertyRows, filterProperty, filterMonth],
  );

  const summary = useMemo(() => propertyPerformanceSummary(filtered), [filtered]);

  const revenueByProperty = useMemo(() => {
    const map = new Map<string, number>();
    for (const r of filtered) {
      map.set(r.property, (map.get(r.property) ?? 0) + (r.roomRevenue ?? 0));
    }
    return [...map.entries()]
      .map(([name, revenue]) => ({ name, revenue }))
      .sort((a, b) => b.revenue - a.revenue);
  }, [filtered]);

  const occTrend = useMemo(() => {
    const map = new Map<string, { month: string; occupancy: number; count: number }>();
    for (const r of filtered) {
      if (r.occupancy == null) continue;
      const cur = map.get(r.month) ?? { month: r.month, occupancy: 0, count: 0 };
      cur.occupancy += r.occupancy;
      cur.count += 1;
      map.set(r.month, cur);
    }
    return [...map.values()]
      .map((m) => ({
        month: formatMonthLabel(m.month),
        occupancy: m.count ? (m.occupancy / m.count) * 100 : 0,
      }))
      .sort((a, b) => a.month.localeCompare(b.month));
  }, [filtered]);

  const handleUpload = async (file: File) => {
    setUploadError(null);
    const text = await readFileAsText(file);
    const result = parsePropertyPerformanceCsv(text);
    if (!result.ok) {
      setUploadError(result.error);
      return;
    }
    setPropertyData(result.rows, { fileName: file.name, uploadedAt: new Date().toISOString() });
  };

  return (
    <div className="space-y-6">
      <CsvUploadCard
        title="Property performance data"
        description="Upload monthly property metrics: booked room nights, occupancy, room revenue, targets, and Tonik share."
        sampleHref="/revenue-analytics/samples/property-performance-sample.csv"
        sampleFileName="property-performance-sample.csv"
        acceptedHint="Columns: property, month, booked_room_nights, available_days, sellable_room_nights, occupancy, room_revenue, monthly_target, tonik_share"
        fileName={propertyMeta?.fileName}
        uploadedAt={propertyMeta?.uploadedAt}
        error={uploadError}
        onUpload={handleUpload}
        onClear={propertyRows.length ? clearProperty : undefined}
      />

      {propertyRows.length === 0 ? (
        <EmptyState message="Upload a property performance CSV to see occupancy, revenue vs target, and property-wise infographic tables." />
      ) : (
        <>
          <div className="flex flex-wrap items-end gap-4">
            <div className="min-w-[180px]">
              <Label htmlFor="prop-filter">Property</Label>
              <Select
                id="prop-filter"
                value={filterProperty}
                onChange={(e) => setFilterProperty(e.target.value)}
                className="mt-1"
              >
                <option value="all">All properties</option>
                {properties.map((p) => (
                  <option key={p} value={p}>
                    {p}
                  </option>
                ))}
              </Select>
            </div>
            <div className="min-w-[160px]">
              <Label htmlFor="month-filter">Month</Label>
              <Select
                id="month-filter"
                value={filterMonth}
                onChange={(e) => setFilterMonth(e.target.value)}
                className="mt-1"
              >
                <option value="all">All months</option>
                {months.map((m) => (
                  <option key={m} value={m}>
                    {formatMonthLabel(m)}
                  </option>
                ))}
              </Select>
            </div>
          </div>

          <KpiStrip
            items={[
              {
                label: "Room revenue",
                value: formatLkr(summary.totalRevenue),
                hint: `${summary.propertyCount} properties`,
                accent: "teal",
              },
              {
                label: "Target achievement",
                value: formatPercent(summary.targetAchievement),
                hint: formatLkr(summary.totalTarget) + " target",
                accent: "gold",
              },
              {
                label: "Booked room nights",
                value: summary.totalBrns.toLocaleString(),
                accent: "slate",
              },
              {
                label: "Avg occupancy",
                value: formatPercent(summary.avgOccupancy),
                accent: "teal",
              },
            ]}
          />

          <div className="grid gap-6 lg:grid-cols-2">
            <ChartCard title="Room revenue by property" description="Filtered period total">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={revenueByProperty} layout="vertical" margin={{ left: 8, right: 16 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                  <XAxis type="number" tick={{ fontSize: 11 }} tickFormatter={(v) => `${(v / 1e6).toFixed(1)}M`} />
                  <YAxis type="category" dataKey="name" width={120} tick={{ fontSize: 10 }} />
                  <Tooltip formatter={(v: number) => [formatLkr(v), "Revenue"]} />
                  <Bar dataKey="revenue" radius={[0, 4, 4, 0]}>
                    {revenueByProperty.map((_, i) => (
                      <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </ChartCard>

            <ChartCard title="Occupancy trend" description="Average occupancy % by month">
              <ResponsiveContainer width="100%" height="100%">
                <ComposedChart data={occTrend}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                  <XAxis dataKey="month" tick={{ fontSize: 11 }} />
                  <YAxis tick={{ fontSize: 11 }} unit="%" domain={[0, 100]} />
                  <Tooltip formatter={(v: number) => [`${v.toFixed(1)}%`, "Occupancy"]} />
                  <Line type="monotone" dataKey="occupancy" stroke="#0d6e6e" strokeWidth={2} dot={{ r: 4 }} />
                </ComposedChart>
              </ResponsiveContainer>
            </ChartCard>
          </div>

          <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
            <div className="border-b border-slate-100 bg-gradient-to-r from-[var(--revenue-teal)] to-[#0a5252] px-5 py-3">
              <h3 className="text-sm font-semibold text-white">Property-wise performance</h3>
              <p className="text-xs text-teal-100">Month · BRNs · occupancy · revenue · target · Tonik share</p>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[900px] text-left text-sm">
                <thead>
                  <tr className="border-b bg-slate-50 text-xs uppercase tracking-wide text-[var(--revenue-muted)]">
                    <th className="px-4 py-3 font-semibold">Property</th>
                    <th className="px-4 py-3 font-semibold">Month</th>
                    <th className="px-4 py-3 text-right font-semibold">BRNs</th>
                    <th className="px-4 py-3 text-right font-semibold">Avail. days</th>
                    <th className="px-4 py-3 text-right font-semibold">SRNs</th>
                    <th className="px-4 py-3 text-right font-semibold">Occ.</th>
                    <th className="px-4 py-3 text-right font-semibold">Room revenue</th>
                    <th className="px-4 py-3 text-right font-semibold">Target</th>
                    <th className="px-4 py-3 text-right font-semibold">vs Target</th>
                    <th className="px-4 py-3 text-right font-semibold">Tonik share</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((row, i) => {
                    const vsTarget =
                      row.roomRevenue != null && row.monthlyTarget != null && row.monthlyTarget > 0
                        ? row.roomRevenue / row.monthlyTarget
                        : null;
                    return (
                      <tr
                        key={`${row.property}-${row.month}-${i}`}
                        className="border-b border-slate-50 hover:bg-[var(--revenue-teal-light)]/30"
                      >
                        <td className="px-4 py-2.5 font-medium text-[var(--revenue-slate)]">
                          {row.property}
                        </td>
                        <td className="px-4 py-2.5 text-[var(--revenue-muted)]">
                          {formatMonthLabel(row.month)}
                        </td>
                        <td className="px-4 py-2.5 text-right tabular-nums">
                          {row.bookedRoomNights ?? "—"}
                        </td>
                        <td className="px-4 py-2.5 text-right tabular-nums">
                          {row.availableDays ?? "—"}
                        </td>
                        <td className="px-4 py-2.5 text-right tabular-nums">
                          {row.sellableRoomNights ?? "—"}
                        </td>
                        <td className="px-4 py-2.5 text-right tabular-nums">
                          {formatPercent(row.occupancy)}
                        </td>
                        <td className="px-4 py-2.5 text-right tabular-nums font-medium">
                          {formatLkr(row.roomRevenue)}
                        </td>
                        <td className="px-4 py-2.5 text-right tabular-nums text-[var(--revenue-muted)]">
                          {formatLkr(row.monthlyTarget)}
                        </td>
                        <td className="px-4 py-2.5 text-right">
                          <span
                            className={
                              vsTarget != null && vsTarget >= 1
                                ? "rounded-full bg-emerald-100 px-2 py-0.5 text-xs font-medium text-emerald-800"
                                : vsTarget != null && vsTarget >= 0.7
                                  ? "rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-800"
                                  : "rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-600"
                            }
                          >
                            {formatPercent(vsTarget)}
                          </span>
                        </td>
                        <td className="px-4 py-2.5 text-right tabular-nums">
                          {formatLkr(row.tonikShare)}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
