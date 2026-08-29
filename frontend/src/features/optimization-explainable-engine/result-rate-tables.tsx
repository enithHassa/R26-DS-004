import type { CalculateResponse, SlabLine, TerminalBenefitLine } from "./api";
import { formatLkr, formatMoneyInput } from "./format-lkr";
import { ordinaryTaxFromSlabs, slabKey, sortedSlabLines } from "./tax-buildup";
import { terminalBenefitLabel } from "./terminal-benefits";

export function ResultRateTables({ result }: { result: CalculateResponse }) {
  const slabLines = sortedSlabLines(result.slab_lines);
  const terminalLines = result.terminal_benefit_lines ?? [];
  const terminalTotal = result.terminal_benefit_tax ?? 0;
  const ordinaryTotal = ordinaryTaxFromSlabs(result.slab_lines);

  return (
    <>
      <section className="space-y-2">
        <h3 className="text-sm font-semibold">Rate bands (this YA)</h3>
        <p className="text-xs text-muted-foreground">
          Taxable income {formatLkr(result.taxable_income)} is taxed band by band. Ordinary tax
          is the sum of the Tax column.
        </p>
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
              {slabLines.map((band, i) => (
                <OrdinarySlabRow key={slabKey(band, i)} band={band} />
              ))}
            </tbody>
            <tfoot>
              <tr className="border-t bg-muted/20">
                <td className="px-3 py-2 font-medium" colSpan={3}>
                  Ordinary tax (sum of bands)
                </td>
                <td className="px-3 py-2 font-medium">{formatLkr(ordinaryTotal)}</td>
                <td className="px-3 py-2" />
              </tr>
              {terminalTotal > 0 ? (
                <tr className="border-t">
                  <td className="px-3 py-2" colSpan={3}>
                    + Terminal-benefit tax
                  </td>
                  <td className="px-3 py-2">{formatLkr(terminalTotal)}</td>
                  <td className="px-3 py-2" />
                </tr>
              ) : null}
              <tr className="border-t">
                <td className="px-3 py-2 font-semibold" colSpan={3}>
                  Tax payable
                </td>
                <td className="px-3 py-2 font-semibold">{formatLkr(result.tax_payable)}</td>
                <td className="px-3 py-2" />
              </tr>
              {(result.apit_credit ?? 0) > 0 || (result.wht_credit ?? 0) > 0 ? (
                <>
                  {(result.apit_credit ?? 0) > 0 ? (
                    <tr className="border-t">
                      <td className="px-3 py-2 text-muted-foreground" colSpan={3}>
                        − APIT credit
                      </td>
                      <td className="px-3 py-2">{formatLkr(result.apit_credit ?? 0)}</td>
                      <td className="px-3 py-2" />
                    </tr>
                  ) : null}
                  {(result.wht_credit ?? 0) > 0 ? (
                    <tr className="border-t">
                      <td className="px-3 py-2 text-muted-foreground" colSpan={3}>
                        − WHT credit
                      </td>
                      <td className="px-3 py-2">{formatLkr(result.wht_credit ?? 0)}</td>
                      <td className="px-3 py-2" />
                    </tr>
                  ) : null}
                  <tr className="border-t">
                    <td className="px-3 py-2 font-semibold" colSpan={3}>
                      {(result.tax_refund ?? 0) > 0 ? "Refund" : "Balance payable"}
                    </td>
                    <td className="px-3 py-2 font-semibold">
                      {formatLkr(
                        (result.tax_refund ?? 0) > 0
                          ? (result.tax_refund ?? 0)
                          : (result.balance_payable ?? result.tax_payable),
                      )}
                    </td>
                    <td className="px-3 py-2" />
                  </tr>
                </>
              ) : null}
            </tfoot>
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
