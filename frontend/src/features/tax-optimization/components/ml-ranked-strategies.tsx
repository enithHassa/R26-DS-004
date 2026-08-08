import { AlertCircle, CheckCircle, Zap } from "lucide-react";
import type { MLRankedStrategyV1, MLRankResponseV1 } from "../types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { formatLkrAmount } from "../format-lkr";

interface MLRankedStrategiesProps {
  response: MLRankResponseV1;
  onStrategySelect?: (strategy: MLRankedStrategyV1) => void;
}

function getRiskBadgeColor(level: "LOW" | "MEDIUM" | "HIGH"): string {
  switch (level) {
    case "LOW":
      return "bg-green-100 text-green-800 border-green-300";
    case "MEDIUM":
      return "bg-yellow-100 text-yellow-800 border-yellow-300";
    case "HIGH":
      return "bg-red-100 text-red-800 border-red-300";
  }
}

function getUtilityScoreColor(score: number): string {
  if (score >= 0.75) return "text-green-700";
  if (score >= 0.50) return "text-blue-700";
  return "text-amber-700";
}

export function MLRankedStrategies({ response, onStrategySelect }: MLRankedStrategiesProps) {
  const bestStrategy = response.ranked_strategies[response.best_strategy_index];

  return (
    <div className="space-y-6">
      {/* Header with baseline info */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center justify-between">
            <span>🤖 ML-Powered Strategy Ranking</span>
            <span className="text-sm font-normal text-gray-600">
              Gross Income: {formatLkrAmount(response.gross_income.toString())}
            </span>
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <p className="text-gray-600">Baseline (No Reliefs)</p>
              <p className="text-lg font-semibold">LKR {formatLkrAmount(response.baseline_tax_liability.toString())}</p>
            </div>
            <div>
              <p className="text-gray-600">Tax Year</p>
              <p className="text-lg font-semibold">{response.tax_year}</p>
            </div>
          </div>
          {response.personalization_note && (
            <div className="text-sm italic text-gray-700 bg-blue-50 p-2 rounded border border-blue-200">
              💡 {response.personalization_note}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Best Strategy Highlight */}
      {bestStrategy && (
        <Card className="border-2 border-green-400 bg-green-50">
          <CardHeader>
            <CardTitle className="text-green-900 flex items-center gap-2">
              <Zap className="w-5 h-5" />
              Recommended Strategy (Rank #{bestStrategy.rank})
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div>
              <h3 className="font-semibold text-lg">{bestStrategy.strategy_name}</h3>
              <p className="text-sm text-gray-600">{bestStrategy.legal_summary}</p>
            </div>

            <div className="grid grid-cols-3 gap-3">
              <div className="bg-white p-3 rounded border border-green-200">
                <p className="text-xs text-gray-600 mb-1">Utility Score</p>
                <p className={`text-xl font-bold ${getUtilityScoreColor(bestStrategy.utility_score)}`}>
                  {(bestStrategy.utility_score * 100).toFixed(1)}%
                </p>
              </div>

              <div className="bg-white p-3 rounded border border-green-200">
                <p className="text-xs text-gray-600 mb-1">Tax Savings</p>
                <p className="text-xl font-bold text-green-700">
                  LKR {formatLkrAmount(bestStrategy.estimated_tax_savings.toString())}
                </p>
              </div>

              <div className="bg-white p-3 rounded border border-green-200">
                <p className="text-xs text-gray-600 mb-1">Estimated Tax</p>
                <p className="text-xl font-bold">
                  LKR {formatLkrAmount(bestStrategy.estimated_tax_liability.toString())}
                </p>
              </div>
            </div>

            <div className="flex gap-2 flex-wrap">
              <span className={`inline-block px-2 py-1 rounded text-xs font-semibold border ${getRiskBadgeColor(bestStrategy.audit_risk_level)}`}>
                Audit Risk: {bestStrategy.audit_risk_level}
              </span>
              {bestStrategy.compliance_status === "COMPLIANT" && (
                <span className="inline-block px-2 py-1 rounded text-xs font-semibold bg-green-100 text-green-800 border border-green-300">
                  ✓ Fully Compliant
                </span>
              )}
              {bestStrategy.reliefs_claimed.length > 0 && (
                <span className="inline-block px-2 py-1 rounded text-xs font-semibold bg-blue-100 text-blue-800 border border-blue-300">
                  {bestStrategy.reliefs_claimed.length} Relief{bestStrategy.reliefs_claimed.length !== 1 ? "s" : ""}
                </span>
              )}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Top 10 Strategies Table */}
      <Card>
        <CardHeader>
          <CardTitle>Top 10 Ranked Strategies</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b bg-gray-50">
                  <th className="text-left py-2 px-3">Rank</th>
                  <th className="text-left py-2 px-3">Strategy</th>
                  <th className="text-center py-2 px-3">Utility Score</th>
                  <th className="text-right py-2 px-3">Est. Tax</th>
                  <th className="text-right py-2 px-3">Savings</th>
                  <th className="text-center py-2 px-3">Risk</th>
                  <th className="text-center py-2 px-3">Reliefs</th>
                </tr>
              </thead>
              <tbody>
                {response.ranked_strategies.map((strategy) => (
                  <tr
                    key={strategy.strategy_id}
                    className="border-b hover:bg-blue-50 cursor-pointer transition-colors"
                    onClick={() => onStrategySelect?.(strategy)}
                  >
                    <td className="py-3 px-3 font-semibold">{strategy.rank}</td>
                    <td className="py-3 px-3">
                      <div>
                        <p className="font-medium">{strategy.strategy_name}</p>
                        <p className="text-xs text-gray-600">{strategy.legal_summary.substring(0, 50)}...</p>
                      </div>
                    </td>
                    <td className={`py-3 px-3 text-center font-bold ${getUtilityScoreColor(strategy.utility_score)}`}>
                      {(strategy.utility_score * 100).toFixed(1)}%
                    </td>
                    <td className="py-3 px-3 text-right font-medium">
                      LKR {formatLkrAmount(strategy.estimated_tax_liability.toString())}
                    </td>
                    <td className="py-3 px-3 text-right font-medium text-green-700">
                      LKR {formatLkrAmount(strategy.estimated_tax_savings.toString())}
                    </td>
                    <td className="py-3 px-3 text-center">
                      <span className={`inline-block px-2 py-1 rounded text-xs font-semibold border ${getRiskBadgeColor(strategy.audit_risk_level)}`}>
                        {strategy.audit_risk_level[0]}
                      </span>
                    </td>
                    <td className="py-3 px-3 text-center">
                      <span className="inline-block px-2 py-1 rounded text-xs font-semibold bg-blue-100 text-blue-800">
                        {strategy.num_reliefs}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      {/* Legal Disclaimer */}
      <Card className="border-yellow-200 bg-yellow-50">
        <CardContent className="flex gap-3 pt-6">
          <AlertCircle className="w-5 h-5 text-yellow-700 flex-shrink-0 mt-0.5" />
          <div className="text-sm text-yellow-800">
            <p className="font-semibold mb-1">Legal Disclaimer</p>
            <p>
              These ML-generated rankings are for informational purposes only and do not constitute legal or tax advice.
              Consult with a qualified tax professional before implementing any strategy. All strategies must comply with
              applicable tax laws and regulations.
            </p>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
