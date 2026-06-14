import { useMemo, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";

import {
  parseBookingPerformanceCsv,
  readFileAsText,
} from "../lib/csv";
import {
  bookingAggregates,
  bookingMonthKey,
  filterBookingsByMonth,
  uniqueSorted,
} from "../lib/compute";
import { formatLkr, formatMonthLabel } from "../lib/format";
import { useRevenueAnalyticsStore } from "../store";
import { ChartCard } from "./chart-card";
import { CsvUploadCard } from "./csv-upload-card";
import { EmptyState } from "./empty-state";
import { KpiStrip } from "./kpi-strip";

const PIE_COLORS = ["#0d6e6e", "#c9a227", "#3b82f6", "#f59e0b", "#8b5cf6", "#ec4899", "#14b8a6", "#f97316"];

function PieTooltip({
  active,
  payload,
}: {
  active?: boolean;
  payload?: { name: string; value: number; payload: { name: string; value: number } }[];
}) {
  if (!active || !payload?.length) return null;
  const p = payload[0];
  return (
    <div className="rounded-lg border bg-white px-3 py-2 text-xs shadow-md">
      <p className="font-medium">{p.name}</p>
      <p className="text-[var(--revenue-muted)]">{formatLkr(p.value)}</p>
    </div>
  );
}

export function BookingPerformanceView() {
  const { bookingRows, bookingMeta, setBookingData, clearBooking } = useRevenueAnalyticsStore();
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [filterMonth, setFilterMonth] = useState("all");

  const months = useMemo(() => {
    const keys = bookingRows.map((r) => bookingMonthKey(r.bookingDate)).filter((m) => m !== "unknown");
    return uniqueSorted(keys);
  }, [bookingRows]);

  const filtered = useMemo(
    () => filterBookingsByMonth(bookingRows, filterMonth),
    [bookingRows, filterMonth],
  );

  const agg = useMemo(() => bookingAggregates(filtered), [filtered]);

  const handleUpload = async (file: File) => {
    setUploadError(null);
    const text = await readFileAsText(file);
    const result = parseBookingPerformanceCsv(text);
    if (!result.ok) {
      setUploadError(result.error);
      return;
    }
    setBookingData(result.rows, { fileName: file.name, uploadedAt: new Date().toISOString() });
  };

  const renderPie = (data: { name: string; value: number }[], title: string) => (
    <ChartCard title={title}>
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          <Pie
            data={data}
            dataKey="value"
            nameKey="name"
            cx="50%"
            cy="50%"
            innerRadius={50}
            outerRadius={90}
            paddingAngle={2}
            label={({ name, percent }) =>
              percent > 0.06 ? `${name} ${(percent * 100).toFixed(0)}%` : ""
            }
          >
            {data.map((_, i) => (
              <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
            ))}
          </Pie>
          <Tooltip content={<PieTooltip />} />
          <Legend wrapperStyle={{ fontSize: 11 }} />
        </PieChart>
      </ResponsiveContainer>
    </ChartCard>
  );

  return (
    <div className="space-y-6">
      <CsvUploadCard
        title="Booking performance data"
        description="Upload booking-level rows to chart performance by country, channel, and property for the selected month."
        sampleHref="/revenue-analytics/samples/booking-performance-sample.csv"
        sampleFileName="booking-performance-sample.csv"
        acceptedHint="Columns: booking_date, property, country, channel, room_nights, room_revenue"
        fileName={bookingMeta?.fileName}
        uploadedAt={bookingMeta?.uploadedAt}
        error={uploadError}
        onUpload={handleUpload}
        onClear={bookingRows.length ? clearBooking : undefined}
      />

      {bookingRows.length === 0 ? (
        <EmptyState message="Upload booking performance CSV to see country, channel, and property breakdowns for the month." />
      ) : (
        <>
          <div className="max-w-xs">
            <Label htmlFor="booking-month">Reporting month</Label>
            <Select
              id="booking-month"
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

          <KpiStrip
            items={[
              {
                label: "Booking revenue",
                value: formatLkr(agg.totalRevenue),
                accent: "teal",
              },
              {
                label: "Room nights",
                value: agg.totalNights.toLocaleString(),
                accent: "gold",
              },
              {
                label: "Countries",
                value: String(agg.byCountry.length),
                accent: "slate",
              },
              {
                label: "Channels",
                value: String(agg.byChannel.length),
                accent: "teal",
              },
            ]}
          />

          <div className="grid gap-6 lg:grid-cols-3">
            {renderPie(agg.byCountry, "By country")}
            {renderPie(agg.byChannel, "By channel")}
            {renderPie(agg.byProperty, "By property")}
          </div>

          <ChartCard
            title="Revenue comparison"
            description="Side-by-side bars — top markets and channels"
            height={320}
          >
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={[
                  ...agg.byCountry.slice(0, 6).map((d) => ({ ...d, group: "Country" })),
                  ...agg.byChannel.slice(0, 6).map((d) => ({ ...d, group: "Channel" })),
                ]}
                margin={{ bottom: 60 }}
              >
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                <XAxis dataKey="name" tick={{ fontSize: 10 }} angle={-25} textAnchor="end" height={70} />
                <YAxis tickFormatter={(v) => `${(v / 1e6).toFixed(1)}M`} tick={{ fontSize: 11 }} />
                <Tooltip formatter={(v: number) => [formatLkr(v), "Revenue"]} />
                <Legend />
                <Bar dataKey="value" name="Revenue" fill="#0d6e6e" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </ChartCard>
        </>
      )}
    </div>
  );
}
