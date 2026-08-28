import type { CalculateResponse, SlabLine, TerminalBenefitLine } from "./api";
import { formatLkr, formatMoneyInput } from "./format-lkr";
import { terminalBenefitLabel } from "./terminal-benefits";

export function ResultRateTables({ result }: { result: CalculateResponse }) {
  const slabLines = result.slab_lines ?? [];
  const terminalLines = result.terminal_benefit_lines ?? [];
  const terminalTotal = result.terminal_benefit_tax ?? 0;

  return (
    <>
      <section className="space-y-2">
        <h3 className="text-sm font-semibold">Rate bands (this YA)</h3>
        <div className="overflow-x-auto rounded-md border">
          <table className="w-full text-left text-xs">
            <thead className="bg-muted/40 text-muted-foreground">
              <tr>
                <th className="px-3 py-2 font-medium">Band</th>
                <th className="px-3 py-2 font-medium">Rate</th>
                <th className="px-3 py-2 font-medium">Slice</th>
                <th className="px-3 py-2 font-medium">Tax</th>
                <th className="px-3 py-2 font-medium">Source</th>
              </tr>
            </thead>
            <tbody>
              {slabLines.map((band) => (
                <OrdinarySlabRow key={band.band_index} band={band} />
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {terminalLines.length > 0 ? (
        <TerminalBenefitTaxTable lines={terminalLines} total={terminalTotal} />
      ) : null}
    </>
  );
}

export function TerminalBenefitTaxTable({
  lines,
  total,
}: {
  lines: TerminalBenefitLine[];
  total: number;
}) {
  const combinedAmount = lines.reduce((sum, line) => sum + (line.amount ?? 0), 0);
  return (
    <section className="space-y-2">
      <h3 className="text-sm font-semibold">Terminal-benefit tax</h3>
      <p className="text-xs text-muted-foreground">
        Qualifying terminal benefits are taxed once on their combined amount using the
        concessionary First Schedule ladder — not a fresh ladder for each benefit, and not the
        ordinary income-tax bands above.
      </p>
      <div className="overflow-x-auto rounded-md border">
        <table className="w-full text-left text-xs">
          <thead className="bg-muted/40 text-muted-foreground">
            <tr>
              <th className="px-3 py-2 font-medium">Benefit</th>
              <th className="px-3 py-2 font-medium">Amount</th>
            </tr>
          </thead>
          <tbody>
            {lines.map((line) => (
              <tr key={`${line.type}-${line.amount}`} className="border-t">
                <td className="px-3 py-2">{terminalBenefitLabel(line.type)}</td>
                <td className="px-3 py-2">{formatLkr(line.amount)}</td>
              </tr>
            ))}
            <tr className="border-t">
              <td className="px-3 py-2 font-medium">Total terminal benefits</td>
              <td className="px-3 py-2 font-medium">{formatLkr(combinedAmount)}</td>
            </tr>
            <tr className="border-t">
              <td className="px-3 py-2 font-medium">Terminal-benefit tax</td>
              <td className="px-3 py-2 font-medium">{formatLkr(total)}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  );
}

function OrdinarySlabRow({ band }: { band: SlabLine }) {
  return (
    <tr className="border-t">
      <td className="px-3 py-2">{band.band_label || `#${band.band_index}`}</td>
      <td className="px-3 py-2">{band.rate_percent}%</td>
      <td className="px-3 py-2">{formatMoneyInput(String(band.slice))}</td>
      <td className="px-3 py-2">{formatLkr(band.tax)}</td>
      <td className="px-3 py-2 text-muted-foreground">{band.source_doc_id}</td>
    </tr>
  );
}
