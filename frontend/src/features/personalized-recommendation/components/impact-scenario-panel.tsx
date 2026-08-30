import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";

import { useDashboardStore } from "../store/dashboard-store";

export function ImpactScenarioPanel() {
  const scenario = useDashboardStore((s) => s.impactScenario);
  const setImpactScenario = useDashboardStore((s) => s.setImpactScenario);

  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      <div className="space-y-1.5">
        <Label>Horizon (years)</Label>
        <Select
          value={String(scenario.horizonYears)}
          onChange={(e) => setImpactScenario({ horizonYears: Number(e.target.value) })}
        >
          {[5, 10, 15, 20].map((y) => (
            <option key={y} value={y}>
              {y}
            </option>
          ))}
        </Select>
      </div>
      <div className="space-y-1.5">
        <Label>Monte Carlo paths</Label>
        <Select
          value={String(scenario.nPaths)}
          onChange={(e) => setImpactScenario({ nPaths: Number(e.target.value) })}
        >
          {[500, 1000, 2000].map((n) => (
            <option key={n} value={n}>
              {n.toLocaleString()}
            </option>
          ))}
        </Select>
      </div>
      <div className="space-y-1.5">
        <Label>Salary growth (mean)</Label>
        <Select
          value={String(scenario.salaryGrowthMean)}
          onChange={(e) => setImpactScenario({ salaryGrowthMean: Number(e.target.value) })}
        >
          {[0.04, 0.06, 0.08, 0.1].map((g) => (
            <option key={g} value={g}>
              {(g * 100).toFixed(0)}%
            </option>
          ))}
        </Select>
      </div>
      <div className="space-y-1.5">
        <Label>Inflation (mean)</Label>
        <Select
          value={String(scenario.inflationMean)}
          onChange={(e) => setImpactScenario({ inflationMean: Number(e.target.value) })}
        >
          {[0.04, 0.06, 0.08].map((g) => (
            <option key={g} value={g}>
              {(g * 100).toFixed(0)}%
            </option>
          ))}
        </Select>
      </div>
      <div className="space-y-1.5">
        <Label>Investment return (mean)</Label>
        <Select
          value={String(scenario.investmentReturnMean)}
          onChange={(e) => setImpactScenario({ investmentReturnMean: Number(e.target.value) })}
        >
          {[0.06, 0.08, 0.1, 0.12].map((g) => (
            <option key={g} value={g}>
              {(g * 100).toFixed(0)}%
            </option>
          ))}
        </Select>
      </div>
      <div className="space-y-1.5">
        <Label>Adoption success probability</Label>
        <Select
          value={String(scenario.adoptionSuccessProb)}
          onChange={(e) => setImpactScenario({ adoptionSuccessProb: Number(e.target.value) })}
        >
          {[1, 0.85, 0.7, 0.5].map((p) => (
            <option key={p} value={p}>
              {(p * 100).toFixed(0)}%
            </option>
          ))}
        </Select>
      </div>
    </div>
  );
}
