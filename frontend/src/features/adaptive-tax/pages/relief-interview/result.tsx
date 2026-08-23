import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";

import {
  calculateCatalogTax,
  calculateTax,
  getReliefInterviewApproved,
  getReliefInterviewRates,
  type CalculateTaxResponse,
  type CatalogEngineResponse,
  type ReliefInterviewRatesYear,
} from "../../api";
import {
  buildCalculateRequestFromSession,
  buildCatalogEngineRequestFromSession,
} from "./build-calculate-request";
import { ActRulesPanel, CatalogEstimateCard } from "./catalog-estimate-card";
import { sortEntries, type ApprovedEntry } from "./catalog-types";
import { useReliefInterview } from "./session";
import { isFilingCatalogYa, yaDisplay } from "./types";

export function ReliefInterviewResultPage() {
  const navigate = useNavigate();
  const { session, setLastOfficialCalc } = useReliefInterview();
  const filingYa = isFilingCatalogYa(session.assessmentYear)
    ? session.assessmentYear
    : null;
  const engineYear = filingYa != null;

  const [catalogReady, setCatalogReady] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<CalculateTaxResponse | null>(null);
  const [catalogResult, setCatalogResult] = useState<CatalogEngineResponse | null>(
    null,
  );
  const [entries, setEntries] = useState<ApprovedEntry[]>([]);
  const [rates, setRates] = useState<ReliefInterviewRatesYear | null>(null);

  const [engineCatalogResult, setEngineCatalogResult] =
    useState<CatalogEngineResponse | null>(null);
  const [engineCatalogLoading, setEngineCatalogLoading] = useState(false);
  const [engineCatalogError, setEngineCatalogError] = useState<string | null>(null);
  const [engineCatalogRetry, setEngineCatalogRetry] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setCatalogReady(false);
    void Promise.all([
      getReliefInterviewApproved(session.assessmentYear),
      getReliefInterviewRates(session.assessmentYear).catch(() => null),
    ])
      .then(([data, ratesData]) => {
        if (cancelled) return;
        const rows = Array.isArray(data.entries) ? data.entries : [];
        setEntries(
          sortEntries(
            rows.filter((e): e is ApprovedEntry => {
              const row = e as Partial<ApprovedEntry>;
              return Boolean(row.entry_id && row.compare_group_id);
            }) as ApprovedEntry[],
          ),
        );
        setRates(ratesData);
      })
      .catch(() => {
        if (!cancelled) {
          setEntries([]);
          setRates(null);
        }
      })
      .finally(() => {
        if (!cancelled) setCatalogReady(true);
      });
    return () => {
      cancelled = true;
    };
  }, [session.assessmentYear]);

  useEffect(() => {
    if (!catalogReady) return;

    let cancelled = false;
    setLoading(true);
    setError(null);
    setResult(null);
    setCatalogResult(null);

    if (filingYa) {
      const body = buildCalculateRequestFromSession({
        assessmentYear: filingYa,
        income: session.income,
        answers: session.reliefAnswers,
        entries,
      });
      void calculateTax(body)
        .then((res) => {
          if (!cancelled) setResult(res);
        })
        .catch((err: unknown) => {
          if (!cancelled) {
            setError(err instanceof Error ? err.message : "Calculation failed.");
          }
        })
        .finally(() => {
          if (!cancelled) setLoading(false);
        });
    } else {
      const body = buildCatalogEngineRequestFromSession({
        assessmentYear: session.assessmentYear,
        income: session.income,
        answers: session.reliefAnswers,
        entries,
      });
      void calculateCatalogTax(body)
        .then((res) => {
          if (!cancelled) setCatalogResult(res);
        })
        .catch((err: unknown) => {
          if (!cancelled) {
            setError(
              err instanceof Error ? err.message : "Catalog calculation failed.",
            );
          }
        })
        .finally(() => {
          if (!cancelled) setLoading(false);
        });
    }

    return () => {
      cancelled = true;
    };
  }, [
    filingYa,
    catalogReady,
    session.assessmentYear,
    session.income,
    session.reliefAnswers,
    entries,
  ]);

  useEffect(() => {
    if (!result?.calc_id) return;
    setLastOfficialCalc(result.calc_id, result.final_tax_lkr);
  }, [result?.calc_id, result?.final_tax_lkr, setLastOfficialCalc]);

  useEffect(() => {
    if (!catalogReady || !filingYa) return;

    let cancelled = false;
    setEngineCatalogLoading(true);
    setEngineCatalogError(null);
    setEngineCatalogResult(null);

    const body = buildCatalogEngineRequestFromSession({
      assessmentYear: filingYa,
      income: session.income,
      answers: session.reliefAnswers,
      entries,
    });
    void calculateCatalogTax(body)
      .then((res) => {
        if (!cancelled) setEngineCatalogResult(res);
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setEngineCatalogError(
            err instanceof Error ? err.message : "Catalog calculation failed.",
          );
        }
      })
      .finally(() => {
        if (!cancelled) setEngineCatalogLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [
    filingYa,
    catalogReady,
    session.income,
    session.reliefAnswers,
    entries,
    engineCatalogRetry,
  ]);

  return (
    <div className="space-y-4">
      <div className="space-y-1">
        <h2 className="text-lg font-semibold">Result</h2>
        <p className="text-sm text-muted-foreground">
          As of YA {yaDisplay(session.assessmentYear)}
          {engineYear
            ? " — catalog estimate from extracted Act provisions."
            : " — tax from the Phase 8 catalog rate engine (rates/{ya}.json)."}
        </p>
      </div>

      {!engineYear && loading ? (
        <p className="flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
          Calculating tax…
        </p>
      ) : null}

      {!engineYear && error ? (
        <p className="text-sm text-destructive" role="alert">
          {error}
        </p>
      ) : null}

      {engineYear ? (
        <CatalogEstimateCard
          ya={session.assessmentYear}
          result={engineCatalogResult}
          loading={engineCatalogLoading}
          error={engineCatalogError}
          onRetry={() => setEngineCatalogRetry((n) => n + 1)}
          rates={rates}
          engineYearCompanion
          showInterviewReportLink
        />
      ) : null}

      {!engineYear && catalogResult ? (
        <CatalogEstimateCard
          ya={session.assessmentYear}
          result={catalogResult}
          rates={rates}
          showInterviewReportLink
        />
      ) : null}

      {!loading && !catalogResult && !engineYear ? (
        <ActRulesPanel ya={session.assessmentYear} rates={rates} />
      ) : null}

      <div className="flex flex-wrap gap-2">
        <Button
          type="button"
          variant="outline"
          onClick={() => void navigate("/adaptive-tax/relief-interview/reliefs")}
        >
          Back
        </Button>
        <Button
          type="button"
          variant="outline"
          onClick={() => void navigate("/adaptive-tax/relief-interview")}
        >
          Start over
        </Button>
      </div>
    </div>
  );
}
