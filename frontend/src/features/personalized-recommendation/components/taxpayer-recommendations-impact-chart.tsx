import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Expand, Layers, Loader2, User, X } from "lucide-react";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { cn } from "@/lib/utils";

import { simulateCombinedImpact, simulateImpact } from "../api/impact";
import { recommendationCodeToCatalog } from "../constants/strategies";
import {
  TAXPAYER_IMPACT_CHART_HORIZON_YEARS,
  TAXPAYER_IMPACT_N_PATHS,
} from "../constants/taxpayer-impact";
import type { ImpactSimulationResponse, RecommendationItem } from "../types";
import { formatLkr, parseLkr } from "../utils/format-lkr";

const CURRENT_COLOR = "#f87171";
const COMBINED_COLOR = "#34d399";
const STRATEGY_COLORS = ["#2dd4bf", "#fbbf24", "#a78bfa", "#38bdf8", "#fb7185"];

type ChartRow = {
  yearLabel: string;
  current: number;
  [key: string]: number | string;
};

type SeriesItem = { key: string; label: string; color: string; dashed?: boolean; bold?: boolean };

/** How to plot selected strategies on the chart. */
type ViewMode = "individual" | "together" | "both";

type ImpactChartBodyProps = {
  profileId: string;
  recommendations: RecommendationItem[];
  strategyCodes: string[];
  selectedIndices: Set<number>;
  viewMode: ViewMode;
  compact?: boolean;
  chartHeight: number;
  loadingHeight: number;
};

function formatBundleLabel(indices: number[]): string {
  const nums = [...indices].sort((a, b) => a - b).map((i) => i + 1);
  if (nums.length <= 3) return nums.join(" + ");
  return `${nums.length} strategies`;
}

function ImpactTooltip({
  active,
  payload,
  label,
  series,
  compact,
}: {
  active?: boolean;
  payload?: Array<{ dataKey: string; value: number; color: string }>;
  label?: string;
  series: SeriesItem[];
  compact?: boolean;
}) {
  if (!active || !payload?.length) return null;

  const byKey = Object.fromEntries(payload.map((p) => [p.dataKey, p.value]));

  return (
    <div
      className={cn(
        "rounded-lg border border-[var(--uv-border)] bg-[var(--uv-bg-card)] shadow-lg",
        compact ? "px-2.5 py-2 text-[10px]" : "px-3 py-2 text-xs",
      )}
    >
      <p className="mb-1.5 font-semibold text-[var(--uv-text)]">{label}</p>
      <ul className="space-y-0.5">
        {series.map((s) => (
          <li key={s.key} className="flex items-center justify-between gap-3">
            <span style={{ color: s.color }}>{s.label}</span>
            <span className="font-medium tabular-nums text-[var(--uv-text)]">
              {formatLkr(byKey[s.key] ?? 0)}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function ImpactChartBody({
  profileId,
  recommendations,
  strategyCodes,
  selectedIndices,
  viewMode,
  compact = false,
  chartHeight,
  loadingHeight,
}: ImpactChartBodyProps) {
  const selectedCodes = useMemo(
    () =>
      [...selectedIndices]
        .sort((a, b) => a - b)
        .map((index) => strategyCodes[index])
        .filter(Boolean),
    [selectedIndices, strategyCodes],
  );

  const selectedIndexList = useMemo(
    () => [...selectedIndices].sort((a, b) => a - b),
    [selectedIndices],
  );

  const impactQuery = useQuery({
    queryKey: ["taxpayer-rec-impact-chart", profileId, strategyCodes.join("|")],
    queryFn: async () => {
      const common = {
        profile_id: profileId,
        horizon_years: TAXPAYER_IMPACT_CHART_HORIZON_YEARS,
        n_paths: TAXPAYER_IMPACT_N_PATHS,
        random_seed: 42,
      };

      const [baselineResult, ...strategyResults] = await Promise.all([
        simulateImpact({ ...common, strategy_code: null }),
        ...strategyCodes.map((code) => simulateImpact({ ...common, strategy_code: code })),
      ]);

      return { baselineResult, strategyResults };
    },
    enabled: !!profileId && strategyCodes.length > 0,
    staleTime: 60_000,
  });

  const showTogether = viewMode === "together" || viewMode === "both";
  const showIndividual = viewMode === "individual" || viewMode === "both";

  const combinedQuery = useQuery({
    queryKey: ["taxpayer-rec-impact-combined", profileId, selectedCodes.join("|")],
    queryFn: () =>
      simulateCombinedImpact({
        profile_id: profileId,
        strategy_codes: selectedCodes,
        horizon_years: TAXPAYER_IMPACT_CHART_HORIZON_YEARS,
        n_paths: TAXPAYER_IMPACT_N_PATHS,
        random_seed: 42,
      }),
    enabled: !!profileId && selectedCodes.length >= 2 && showTogether,
    staleTime: 60_000,
  });

  const togetherLabel = useMemo(() => {
    const bundle = formatBundleLabel(selectedIndexList);
    return `Applied together (${bundle})`;
  }, [selectedIndexList]);

  const series = useMemo((): SeriesItem[] => {
    const items: SeriesItem[] = [{ key: "current", label: "Current (no change)", color: CURRENT_COLOR }];

    if (showIndividual) {
      recommendations.forEach((item, index) => {
        if (!selectedIndices.has(index)) return;
        items.push({
          key: `strategy${index + 1}`,
          label: `Strategy ${index + 1} alone — ${item.strategy.name}`,
          color: STRATEGY_COLORS[index % STRATEGY_COLORS.length] ?? "#94a3b8",
        });
      });
    }

    if (showTogether && selectedCodes.length >= 2) {
      items.push({
        key: "combined",
        label: togetherLabel,
        color: COMBINED_COLOR,
        dashed: true,
        bold: true,
      });
    }

    return items;
  }, [
    recommendations,
    selectedIndices,
    selectedCodes.length,
    togetherLabel,
    showIndividual,
    showTogether,
  ]);

  const chartData = useMemo((): ChartRow[] => {
    const baseline = impactQuery.data?.baselineResult.baseline ?? [];
    const strategyResults = impactQuery.data?.strategyResults ?? [];
    const combinedPath = combinedQuery.data?.strategy_path ?? [];
    const startYear = new Date().getFullYear();

    return baseline.map((row, index) => {
      const point: ChartRow = {
        yearLabel: String(startYear + row.year - 1),
        current: parseLkr(row.projected_tax_liability),
      };

      if (showIndividual) {
        strategyResults.forEach((result, strategyIndex) => {
          if (!selectedIndices.has(strategyIndex)) return;
          const path = result.strategy_path?.[index];
          if (path) {
            point[`strategy${strategyIndex + 1}`] = parseLkr(path.projected_tax_liability);
          }
        });
      }

      const combinedRow = combinedPath[index];
      if (combinedRow && showTogether && selectedCodes.length >= 2) {
        point.combined = parseLkr(combinedRow.projected_tax_liability);
      }

      return point;
    });
  }, [
    impactQuery.data,
    combinedQuery.data,
    selectedIndices,
    selectedCodes.length,
    showIndividual,
    showTogether,
  ]);

  const needsCombined = showTogether && selectedCodes.length >= 2;
  const isLoading =
    impactQuery.isLoading || (needsCombined && combinedQuery.isLoading);
  const tickSize = compact ? 9 : 11;

  if (isLoading) {
    return (
      <div
        className="flex items-center justify-center gap-2 text-[var(--uv-text-muted)]"
        style={{ height: loadingHeight }}
      >
        <Loader2 className="h-3.5 w-3.5 animate-spin" />
        <span className={compact ? "text-[10px]" : "text-sm"}>Loading chart…</span>
      </div>
    );
  }

  if (impactQuery.isError) {
    return (
      <div className="rounded-md border border-red-500/40 bg-red-500/10 p-2 text-[10px] text-red-300">
        {(impactQuery.error as Error).message}
      </div>
    );
  }

  if (combinedQuery.isError) {
    return (
      <div className="rounded-md border border-red-500/40 bg-red-500/10 p-2 text-[10px] text-red-300">
        {(combinedQuery.error as Error).message}
      </div>
    );
  }

  if (chartData.length === 0) return null;

  return (
    <div style={{ height: chartHeight }}>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart
          data={chartData}
          margin={
            compact
              ? { top: 4, right: 4, left: -18, bottom: 0 }
              : { top: 8, right: 12, left: 0, bottom: 0 }
          }
        >
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.12)" />
          <XAxis
            dataKey="yearLabel"
            tick={{ fill: "#94a3b8", fontSize: tickSize }}
            axisLine={{ stroke: "rgba(148,163,184,0.2)" }}
            tickLine={false}
            interval={compact ? "preserveStartEnd" : undefined}
          />
          <YAxis
            tick={{ fill: "#94a3b8", fontSize: tickSize }}
            tickFormatter={(v) => `${Math.round(Number(v) / 1000)}K`}
            axisLine={false}
            tickLine={false}
            width={compact ? 32 : 48}
          />
          <Tooltip
            content={<ImpactTooltip series={series} compact={compact} />}
            cursor={{ stroke: "rgba(148,163,184,0.35)", strokeWidth: 1 }}
          />
          <Legend
            wrapperStyle={{
              fontSize: compact ? 9 : 10,
              color: "#94a3b8",
              paddingTop: compact ? 4 : 8,
            }}
            iconSize={compact ? 8 : 10}
            formatter={(value) => (
              <span className="text-[var(--uv-text-muted)]">{value}</span>
            )}
          />
          {series.map((s) => (
            <Line
              key={s.key}
              type="monotone"
              dataKey={s.key}
              name={s.label}
              stroke={s.color}
              strokeWidth={s.bold ? 3 : compact ? 1.5 : 2}
              strokeDasharray={s.dashed ? "6 4" : undefined}
              dot={compact && !s.dashed ? { r: 2.5, strokeWidth: 0, fill: s.color } : false}
              activeDot={{ r: compact ? 3 : 5, strokeWidth: 0 }}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

type CombinedSummaryProps = {
  baseline: ImpactSimulationResponse | undefined;
  combined: ImpactSimulationResponse | undefined;
  selectedIndices: Set<number>;
  individualResults: ImpactSimulationResponse[] | undefined;
  loading: boolean;
};

function CombinedImpactSummary({
  baseline,
  combined,
  selectedIndices,
  individualResults,
  loading,
}: CombinedSummaryProps) {
  if (selectedIndices.size < 2) {
    return (
      <p className="rounded-md border border-[var(--uv-border)] bg-[var(--uv-bg)]/40 px-3 py-2 text-[10px] text-[var(--uv-text-muted)]">
        Select two or more strategies to see tax impact when you adopt them all at once.
      </p>
    );
  }

  if (loading) {
    return (
      <div className="flex items-center gap-2 rounded-md border border-[var(--uv-border)] px-3 py-2 text-[10px] text-[var(--uv-text-muted)]">
        <Loader2 className="h-3 w-3 animate-spin" />
        Calculating combined impact…
      </div>
    );
  }

  if (!baseline || !combined?.strategy_path?.length) return null;

  const bundle = formatBundleLabel([...selectedIndices]);
  const year1Current = parseLkr(baseline.baseline[0]?.projected_tax_liability ?? "0");
  const year1Combined = parseLkr(combined.strategy_path[0]?.projected_tax_liability ?? "0");
  const savingsTogether = year1Current - year1Combined;

  const individualTaxes = [...selectedIndices]
    .sort((a, b) => a - b)
    .map((index) => {
      const path = individualResults?.[index]?.strategy_path?.[0];
      return path ? parseLkr(path.projected_tax_liability) : null;
    })
    .filter((v): v is number => v !== null);

  const bestIndividual = individualTaxes.length ? Math.min(...individualTaxes) : null;
  const extraVsBestAlone =
    bestIndividual !== null ? bestIndividual - year1Combined : null;

  return (
    <div className="rounded-lg border border-teal-500/30 bg-teal-500/5 p-3">
      <p className="text-xs font-semibold text-teal-300">
        If you apply strategies {bundle} together
      </p>
      <dl className="mt-2 grid gap-2 sm:grid-cols-3">
        <div>
          <dt className="text-[10px] text-[var(--uv-text-muted)]">Year 1 tax (together)</dt>
          <dd className="text-sm font-semibold tabular-nums text-[var(--uv-text)]">
            {formatLkr(year1Combined)}
          </dd>
        </div>
        <div>
          <dt className="text-[10px] text-[var(--uv-text-muted)]">Savings vs current</dt>
          <dd className="text-sm font-semibold tabular-nums text-teal-300">
            {formatLkr(savingsTogether)}
          </dd>
        </div>
        {extraVsBestAlone !== null && extraVsBestAlone > 0 && (
          <div>
            <dt className="text-[10px] text-[var(--uv-text-muted)]">Extra vs best single strategy</dt>
            <dd className="text-sm font-semibold tabular-nums text-teal-300">
              +{formatLkr(extraVsBestAlone)}
            </dd>
          </div>
        )}
      </dl>
      <p className="mt-2 text-[10px] leading-relaxed text-[var(--uv-text-muted)]">
        &ldquo;Applied together&rdquo; merges all selected reliefs in one simulation — this is not
        the sum of adopting each strategy on its own.
      </p>
    </div>
  );
}

type ViewModeToggleProps = {
  viewMode: ViewMode;
  onChange: (mode: ViewMode) => void;
  canShowTogether: boolean;
};

function ViewModeToggle({ viewMode, onChange, canShowTogether }: ViewModeToggleProps) {
  const options: Array<{ id: ViewMode; label: string; icon: typeof User; hint: string }> = [
    {
      id: "individual",
      label: "Individual",
      icon: User,
      hint: "Each strategy applied alone",
    },
    {
      id: "together",
      label: "Applied together",
      icon: Layers,
      hint: "All selected strategies at once",
    },
    {
      id: "both",
      label: "Compare both",
      icon: Layers,
      hint: "Individual + combined on one chart",
    },
  ];

  return (
    <div className="space-y-1.5">
      <p className="text-xs font-medium text-[var(--uv-text)]">Comparison method</p>
      <div className="flex flex-col gap-1">
        {options.map(({ id, label, icon: Icon, hint }) => {
          const disabled = id !== "individual" && !canShowTogether;
          return (
            <button
              key={id}
              type="button"
              disabled={disabled}
              onClick={() => onChange(id)}
              className={cn(
                "flex items-start gap-2 rounded-md border px-2.5 py-2 text-left transition-colors",
                viewMode === id
                  ? "border-teal-500/50 bg-teal-500/10"
                  : "border-[var(--uv-border)] hover:bg-white/5",
                disabled && "cursor-not-allowed opacity-40",
              )}
            >
              <Icon className="mt-0.5 h-3.5 w-3.5 shrink-0 text-teal-400" />
              <span>
                <span className="block text-xs font-medium text-[var(--uv-text)]">{label}</span>
                <span className="block text-[10px] text-[var(--uv-text-muted)]">{hint}</span>
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}

type StrategySelectorProps = {
  recommendations: RecommendationItem[];
  selectedIndices: Set<number>;
  onToggle: (index: number) => void;
  onSelectBundle: (count: number) => void;
};

function StrategySelector({
  recommendations,
  selectedIndices,
  onToggle,
  onSelectBundle,
}: StrategySelectorProps) {
  const bundlePresets = [2, 3].filter((n) => n <= recommendations.length);
  if (recommendations.length >= 2 && !bundlePresets.includes(recommendations.length)) {
    bundlePresets.push(recommendations.length);
  }

  return (
    <div className="space-y-3">
      <div className="rounded-lg border border-[var(--uv-border)] bg-[var(--uv-bg)]/40 p-3">
        <p className="mb-2 text-xs font-medium text-[var(--uv-text)]">Quick bundles</p>
        <p className="mb-2 text-[10px] text-[var(--uv-text-muted)]">
          See impact when adopting multiple top recommendations at the same time.
        </p>
        <div className="flex flex-wrap gap-1.5">
          {bundlePresets.map((count) => (
            <button
              key={count}
              type="button"
              onClick={() => onSelectBundle(count)}
              className="rounded-md border border-teal-500/40 bg-teal-500/10 px-2 py-1 text-[10px] font-medium text-teal-300 hover:bg-teal-500/20"
            >
              Top {count} together
            </button>
          ))}
        </div>
      </div>

      <div className="rounded-lg border border-[var(--uv-border)] bg-[var(--uv-bg)]/40 p-3">
        <p className="mb-2 text-xs font-medium text-[var(--uv-text)]">Pick strategies</p>
        <p className="mb-2 text-[10px] text-[var(--uv-text-muted)]">
          Choose which recommendations to include in the bundle (2+ for combined impact).
        </p>
        <ul className="space-y-2">
          {recommendations.map((item, index) => {
            const color = STRATEGY_COLORS[index % STRATEGY_COLORS.length] ?? "#94a3b8";
            const checked = selectedIndices.has(index);
            return (
              <li key={item.id}>
                <label className="flex cursor-pointer items-start gap-2.5 rounded-md px-1 py-0.5 hover:bg-white/5">
                  <Checkbox
                    checked={checked}
                    onChange={() => onToggle(index)}
                    className="mt-0.5 border-[var(--uv-border)] accent-teal-600"
                  />
                  <span className="min-w-0 flex-1">
                    <span className="flex items-center gap-1.5 text-xs font-medium text-[var(--uv-text)]">
                      <span
                        className="inline-block h-2 w-2 shrink-0 rounded-full"
                        style={{ backgroundColor: color }}
                      />
                      Strategy {index + 1}
                    </span>
                    <span className="line-clamp-2 text-[10px] text-[var(--uv-text-muted)]">
                      {item.strategy.name}
                    </span>
                  </span>
                </label>
              </li>
            );
          })}
        </ul>
      </div>
    </div>
  );
}

type ImpactModalContentProps = {
  profileId: string;
  recommendations: RecommendationItem[];
  strategyCodes: string[];
  selectedIndices: Set<number>;
  viewMode: ViewMode;
  onSelectBundle: (count: number) => void;
  onToggle: (index: number) => void;
  onViewModeChange: (mode: ViewMode) => void;
};

function ImpactModalContent({
  profileId,
  recommendations,
  strategyCodes,
  selectedIndices,
  viewMode,
  onSelectBundle,
  onToggle,
  onViewModeChange,
}: ImpactModalContentProps) {
  const [combinedResult, setCombinedResult] = useState<ImpactSimulationResponse | undefined>();
  const canShowTogether = selectedIndices.size >= 2;

  const impactQuery = useQuery({
    queryKey: ["taxpayer-rec-impact-chart", profileId, strategyCodes.join("|")],
    queryFn: async () => {
      const common = {
        profile_id: profileId,
        horizon_years: TAXPAYER_IMPACT_CHART_HORIZON_YEARS,
        n_paths: TAXPAYER_IMPACT_N_PATHS,
        random_seed: 42,
      };
      const [baselineResult, ...strategyResults] = await Promise.all([
        simulateImpact({ ...common, strategy_code: null }),
        ...strategyCodes.map((code) => simulateImpact({ ...common, strategy_code: code })),
      ]);
      return { baselineResult, strategyResults };
    },
    enabled: !!profileId && strategyCodes.length > 0,
    staleTime: 60_000,
  });

  const selectedCodes = useMemo(
    () =>
      [...selectedIndices]
        .sort((a, b) => a - b)
        .map((index) => strategyCodes[index])
        .filter(Boolean),
    [selectedIndices, strategyCodes],
  );

  const showTogether = viewMode === "together" || viewMode === "both";
  const combinedQuery = useQuery({
    queryKey: ["taxpayer-rec-impact-combined", profileId, selectedCodes.join("|")],
    queryFn: () =>
      simulateCombinedImpact({
        profile_id: profileId,
        strategy_codes: selectedCodes,
        horizon_years: TAXPAYER_IMPACT_CHART_HORIZON_YEARS,
        n_paths: TAXPAYER_IMPACT_N_PATHS,
        random_seed: 42,
      }),
    enabled: !!profileId && selectedCodes.length >= 2 && showTogether,
    staleTime: 60_000,
  });

  useEffect(() => {
    setCombinedResult(combinedQuery.data);
  }, [combinedQuery.data]);

  return (
    <div className="grid min-h-0 flex-1 gap-4 overflow-y-auto p-5 lg:grid-cols-[240px_1fr]">
      <div className="space-y-3">
        <ViewModeToggle
          viewMode={viewMode}
          onChange={onViewModeChange}
          canShowTogether={canShowTogether}
        />
        <StrategySelector
          recommendations={recommendations}
          selectedIndices={selectedIndices}
          onToggle={onToggle}
          onSelectBundle={onSelectBundle}
        />
      </div>

      <div className="flex min-h-[320px] flex-col gap-3">
        <CombinedImpactSummary
          baseline={impactQuery.data?.baselineResult}
          combined={combinedResult}
          selectedIndices={selectedIndices}
          individualResults={impactQuery.data?.strategyResults}
          loading={canShowTogether && showTogether && combinedQuery.isLoading}
        />
        <div className="min-h-[280px] flex-1">
          <ImpactChartBody
            profileId={profileId}
            recommendations={recommendations}
            strategyCodes={strategyCodes}
            selectedIndices={selectedIndices}
            viewMode={viewMode}
            compact={false}
            chartHeight={280}
            loadingHeight={260}
          />
        </div>
      </div>
    </div>
  );
}

type TaxpayerRecommendationsImpactChartProps = {
  profileId: string;
  recommendations: RecommendationItem[];
  /** Sidebar widget — smaller chart matching TaxWise mock; click to expand. */
  compact?: boolean;
};

export function TaxpayerRecommendationsImpactChart({
  profileId,
  recommendations,
  compact = false,
}: TaxpayerRecommendationsImpactChartProps) {
  const [modalOpen, setModalOpen] = useState(false);
  const [viewMode, setViewMode] = useState<ViewMode>("both");
  const [selectedIndices, setSelectedIndices] = useState<Set<number>>(() =>
    new Set(recommendations.map((_, index) => index)),
  );

  const strategyCodes = useMemo(
    () => recommendations.map((item) => recommendationCodeToCatalog(item.strategy.code)),
    [recommendations],
  );

  const toggleStrategy = (index: number) => {
    setSelectedIndices((prev) => {
      const next = new Set(prev);
      if (next.has(index)) {
        next.delete(index);
      } else {
        next.add(index);
      }
      return next;
    });
  };

  const selectBundle = (count: number) => {
    setSelectedIndices(new Set(recommendations.slice(0, count).map((_, index) => index)));
    setViewMode(count >= 2 ? "together" : "individual");
  };

  const previewSelected = useMemo(
    () => new Set(recommendations.map((_, index) => index)),
    [recommendations],
  );

  if (recommendations.length === 0) return null;

  const chartHeight = compact ? 200 : 340;
  const loadingHeight = compact ? 200 : 300;

  const chartBlock = (
    <ImpactChartBody
      profileId={profileId}
      recommendations={recommendations}
      strategyCodes={strategyCodes}
      selectedIndices={compact && !modalOpen ? previewSelected : selectedIndices}
      viewMode={compact && !modalOpen ? "both" : viewMode}
      compact={compact && !modalOpen}
      chartHeight={chartHeight}
      loadingHeight={loadingHeight}
    />
  );

  return (
    <>
      <div
        role={compact ? "button" : undefined}
        tabIndex={compact ? 0 : undefined}
        onClick={compact ? () => setModalOpen(true) : undefined}
        onKeyDown={
          compact
            ? (event) => {
                if (event.key === "Enter" || event.key === " ") {
                  event.preventDefault();
                  setModalOpen(true);
                }
              }
            : undefined
        }
        className={cn(
          "rounded-xl border border-[var(--uv-border)] bg-[var(--uv-bg-card)]",
          compact ? "cursor-pointer p-3 transition-colors hover:border-teal-500/40 hover:bg-white/[0.02]" : "p-4",
        )}
      >
        <div className={compact ? "mb-2 flex items-start justify-between gap-2" : "mb-4"}>
          <div>
            <h3
              className={cn(
                "font-semibold text-[var(--uv-text)]",
                compact ? "text-sm leading-tight" : "text-base",
              )}
            >
              {TAXPAYER_IMPACT_CHART_HORIZON_YEARS}-Year Financial Impact
            </h3>
            <p
              className={cn(
                "text-[var(--uv-text-muted)]",
                compact ? "mt-0.5 text-[10px]" : "mt-1 text-xs",
              )}
            >
              Individual strategies vs applied together — click to explore
            </p>
          </div>
          {compact && (
            <span className="inline-flex shrink-0 items-center gap-1 rounded-md border border-[var(--uv-border)] px-1.5 py-0.5 text-[9px] font-medium text-[var(--uv-text-muted)]">
              <Expand className="h-3 w-3" />
              Expand
            </span>
          )}
        </div>
        {chartBlock}
      </div>

      {modalOpen && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 backdrop-blur-sm"
          onClick={() => setModalOpen(false)}
        >
          <Card
            className="flex max-h-[92vh] w-full max-w-4xl flex-col overflow-hidden border-[var(--uv-border)] bg-[var(--uv-bg-card)] p-0 shadow-xl"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="flex shrink-0 items-start justify-between gap-4 border-b border-[var(--uv-border)] px-5 py-4">
              <div>
                <h2 className="text-lg font-semibold text-[var(--uv-text)]">
                  {TAXPAYER_IMPACT_CHART_HORIZON_YEARS}-Year Financial Impact
                </h2>
                <p className="mt-0.5 text-xs text-[var(--uv-text-muted)]">
                  Two ways to compare: each strategy on its own, or several adopted at the same time.
                </p>
              </div>
              <Button
                size="icon"
                variant="ghost"
                onClick={() => setModalOpen(false)}
                className="shrink-0 text-[var(--uv-text-muted)] hover:bg-white/10 hover:text-[var(--uv-text)]"
              >
                <X className="h-4 w-4" />
              </Button>
            </div>

            <ImpactModalContent
              profileId={profileId}
              recommendations={recommendations}
              strategyCodes={strategyCodes}
              selectedIndices={selectedIndices}
              viewMode={viewMode}
              onSelectBundle={selectBundle}
              onToggle={toggleStrategy}
              onViewModeChange={setViewMode}
            />
          </Card>
        </div>
      )}
    </>
  );
}
