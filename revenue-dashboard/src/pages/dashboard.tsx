import { useState } from "react";
import { Building2, CalendarRange, LineChart, MessageSquareQuote } from "lucide-react";

import { cn } from "@/lib/utils";

import { BookingPerformanceView } from "../components/booking-performance-view";
import { InquiriesView } from "../components/inquiries-view";
import { PropertyPerformanceView } from "../components/property-performance-view";

type TabId = "property" | "booking" | "inquiries";

const TABS: { id: TabId; label: string; icon: typeof Building2; subtitle: string }[] = [
  {
    id: "property",
    label: "Property performance",
    icon: Building2,
    subtitle: "Occupancy, revenue & targets",
  },
  {
    id: "booking",
    label: "Booking performance",
    icon: LineChart,
    subtitle: "Country · channel · property",
  },
  {
    id: "inquiries",
    label: "Inquiries",
    icon: MessageSquareQuote,
    subtitle: "Channel dashboard & date range",
  },
];

export function RevenueDashboardPage() {
  const [tab, setTab] = useState<TabId>("property");

  return (
    <div className="space-y-8 pb-12">
      <header className="relative overflow-hidden rounded-3xl bg-gradient-to-br from-[var(--revenue-teal)] via-[#0a5252] to-slate-900 px-6 py-8 text-white shadow-lg md:px-10 md:py-10">
        <div className="pointer-events-none absolute -right-16 -top-16 h-48 w-48 rounded-full bg-[var(--revenue-gold)]/20 blur-2xl" />
        <div className="pointer-events-none absolute -bottom-20 left-1/3 h-56 w-56 rounded-full bg-white/5 blur-3xl" />
        <div className="relative">
          <div className="mb-2 inline-flex items-center gap-2 rounded-full bg-white/10 px-3 py-1 text-xs font-medium backdrop-blur">
            <CalendarRange className="h-3.5 w-3.5" />
            Weekly revenue reporting
          </div>
          <h1 className="text-2xl font-bold tracking-tight md:text-3xl">Revenue analytics dashboard</h1>
          <p className="mt-2 max-w-2xl text-sm text-teal-100/90 md:text-base">
            Infographic-style views for property performance, booking mix, and inquiry channels.
            Upload a CSV per section to compute and visualize your meeting pack.
          </p>
        </div>
      </header>

      <nav
        className="flex flex-wrap gap-2 rounded-2xl border border-slate-200 bg-white p-2 shadow-sm"
        aria-label="Dashboard sections"
      >
        {TABS.map(({ id, label, icon: Icon, subtitle }) => (
          <button
            key={id}
            type="button"
            onClick={() => setTab(id)}
            className={cn(
              "flex min-w-[200px] flex-1 flex-col items-start rounded-xl px-4 py-3 text-left transition",
              tab === id
                ? "bg-[var(--revenue-teal)] text-white shadow-md"
                : "text-[var(--revenue-slate)] hover:bg-[var(--revenue-teal-light)]",
            )}
          >
            <span className="flex items-center gap-2 text-sm font-semibold">
              <Icon className="h-4 w-4" />
              {label}
            </span>
            <span
              className={cn(
                "mt-0.5 text-xs",
                tab === id ? "text-teal-100" : "text-[var(--revenue-muted)]",
              )}
            >
              {subtitle}
            </span>
          </button>
        ))}
      </nav>

      <section>
        {tab === "property" ? <PropertyPerformanceView /> : null}
        {tab === "booking" ? <BookingPerformanceView /> : null}
        {tab === "inquiries" ? <InquiriesView /> : null}
      </section>
    </div>
  );
}
