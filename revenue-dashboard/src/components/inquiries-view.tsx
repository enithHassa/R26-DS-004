import { useMemo, useState } from "react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";

import { parseInquiriesCsv, readFileAsText } from "../lib/csv";
import { filterInquiries, inquiriesByDate, inquiryAggregates, uniqueSorted } from "../lib/compute";
import { useRevenueAnalyticsStore } from "../store";
import { ChartCard } from "./chart-card";
import { CsvUploadCard } from "./csv-upload-card";
import { EmptyState } from "./empty-state";
import { KpiStrip } from "./kpi-strip";

const BAR_COLORS = ["#0d6e6e", "#c9a227", "#3b82f6", "#f59e0b", "#8b5cf6"];

export function InquiriesView() {
  const { inquiryRows, inquiryMeta, setInquiryData, clearInquiry } = useRevenueAnalyticsStore();
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [channelFilter, setChannelFilter] = useState("all");

  const channels = useMemo(() => uniqueSorted(inquiryRows.map((r) => r.channel)), [inquiryRows]);

  const filtered = useMemo(
    () =>
      filterInquiries(inquiryRows, {
        start: startDate || undefined,
        end: endDate || undefined,
        channel: channelFilter,
      }),
    [inquiryRows, startDate, endDate, channelFilter],
  );

  const agg = useMemo(() => inquiryAggregates(filtered), [filtered]);
  const timeline = useMemo(() => inquiriesByDate(filtered), [filtered]);

  const handleUpload = async (file: File) => {
    setUploadError(null);
    const text = await readFileAsText(file);
    const result = parseInquiriesCsv(text);
    if (!result.ok) {
      setUploadError(result.error);
      return;
    }
    setInquiryData(result.rows, { fileName: file.name, uploadedAt: new Date().toISOString() });
    const dates = result.rows.map((r) => r.inquiryDate).sort();
    if (dates.length && !startDate) setStartDate(dates[0].slice(0, 10));
    if (dates.length && !endDate) setEndDate(dates[dates.length - 1].slice(0, 10));
  };

  return (
    <div className="space-y-6">
      <CsvUploadCard
        title="Inquiries data"
        description="Upload daily or aggregated inquiry counts by channel. Use the date range filter to focus your reporting period."
        sampleHref="/revenue-analytics/samples/inquiries-sample.csv"
        sampleFileName="inquiries-sample.csv"
        acceptedHint="Columns: inquiry_date, channel, inquiries (optional: property)"
        fileName={inquiryMeta?.fileName}
        uploadedAt={inquiryMeta?.uploadedAt}
        error={uploadError}
        onUpload={handleUpload}
        onClear={inquiryRows.length ? clearInquiry : undefined}
      />

      {inquiryRows.length === 0 ? (
        <EmptyState message="Upload an inquiries CSV to see channel-wise counts and trends with date range filtering." />
      ) : (
        <>
          <div className="flex flex-wrap items-end gap-4 rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
            <div>
              <Label htmlFor="inq-start">From</Label>
              <Input
                id="inq-start"
                type="date"
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
                className="mt-1 w-40"
              />
            </div>
            <div>
              <Label htmlFor="inq-end">To</Label>
              <Input
                id="inq-end"
                type="date"
                value={endDate}
                onChange={(e) => setEndDate(e.target.value)}
                className="mt-1 w-40"
              />
            </div>
            <div className="min-w-[180px]">
              <Label htmlFor="inq-channel">Channel</Label>
              <Select
                id="inq-channel"
                value={channelFilter}
                onChange={(e) => setChannelFilter(e.target.value)}
                className="mt-1"
              >
                <option value="all">All channels</option>
                {channels.map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </Select>
            </div>
          </div>

          <KpiStrip
            items={[
              {
                label: "Total inquiries",
                value: agg.total.toLocaleString(),
                hint: agg.dateMin && agg.dateMax ? `${agg.dateMin} – ${agg.dateMax}` : undefined,
                accent: "teal",
              },
              {
                label: "Channels",
                value: String(agg.byChannel.length),
                accent: "gold",
              },
              {
                label: "Top channel",
                value: agg.byChannel[0]?.name ?? "—",
                hint: agg.byChannel[0] ? `${agg.byChannel[0].value} inquiries` : undefined,
                accent: "slate",
              },
              {
                label: "Daily average",
                value:
                  timeline.length > 0
                    ? Math.round(agg.total / timeline.length).toLocaleString()
                    : "—",
                accent: "teal",
              },
            ]}
          />

          <div className="grid gap-6 lg:grid-cols-2">
            <ChartCard title="Inquiries by channel" description="Filtered period">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={agg.byChannel} margin={{ bottom: 8 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                  <XAxis dataKey="name" tick={{ fontSize: 10 }} angle={-20} textAnchor="end" height={60} />
                  <YAxis tick={{ fontSize: 11 }} />
                  <Tooltip />
                  <Bar dataKey="value" name="Inquiries" radius={[6, 6, 0, 0]}>
                    {agg.byChannel.map((_, i) => (
                      <Cell key={i} fill={BAR_COLORS[i % BAR_COLORS.length]} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </ChartCard>

            <ChartCard title="Inquiry trend" description="Daily volume over selected range">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={timeline}>
                  <defs>
                    <linearGradient id="inqGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#0d6e6e" stopOpacity={0.35} />
                      <stop offset="100%" stopColor="#0d6e6e" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                  <XAxis dataKey="date" tick={{ fontSize: 10 }} />
                  <YAxis tick={{ fontSize: 11 }} />
                  <Tooltip />
                  <Area
                    type="monotone"
                    dataKey="inquiries"
                    stroke="#0d6e6e"
                    fill="url(#inqGrad)"
                    strokeWidth={2}
                  />
                </AreaChart>
              </ResponsiveContainer>
            </ChartCard>
          </div>

          <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
            <div className="border-b bg-slate-50 px-5 py-3">
              <h3 className="text-sm font-semibold text-[var(--revenue-slate)]">Channel breakdown</h3>
            </div>
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-left text-xs uppercase text-[var(--revenue-muted)]">
                  <th className="px-5 py-3">Channel</th>
                  <th className="px-5 py-3 text-right">Inquiries</th>
                  <th className="px-5 py-3 text-right">Share</th>
                </tr>
              </thead>
              <tbody>
                {agg.byChannel.map((row) => (
                  <tr key={row.name} className="border-b border-slate-50 hover:bg-slate-50/80">
                    <td className="px-5 py-2.5 font-medium">{row.name}</td>
                    <td className="px-5 py-2.5 text-right tabular-nums">{row.value.toLocaleString()}</td>
                    <td className="px-5 py-2.5 text-right tabular-nums text-[var(--revenue-muted)]">
                      {agg.total > 0 ? `${((row.value / agg.total) * 100).toFixed(1)}%` : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
