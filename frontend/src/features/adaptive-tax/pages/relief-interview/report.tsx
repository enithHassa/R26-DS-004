import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { Button } from "@/components/ui/button";

import {
  calculateCatalogTax,
  getReliefInterviewApproved,
  getReliefInterviewRates,
  type CatalogEngineResponse,
  type ReliefInterviewRatesYear,
} from "../../api";
import { formatLkr } from "../../format-lkr";
import { buildCatalogEngineRequestFromSession } from "./build-calculate-request";
import {
  CatalogEstimateCard,
  OfficialEngineWrap,
} from "./catalog-estimate-card";
import { sortEntries, type ApprovedEntry } from "./catalog-types";
import { useReliefInterview } from "./session";
import { isFilingCatalogYa, yaDisplay } from "./types";

export function ReliefInterviewReportPage() {
  const navigate = useNavigate();
  const { session } = useReliefInterview();
  const filingYa = isFilingCatalogYa(session.assessmentYear)
    ? session.assessmentYear
    : null;
  const engineYear = filingYa != null;

  const [entries, setEntries] = useState<ApprovedEntry[]>([]);
  const [rates, setRates] = useState<ReliefInterviewRatesYear | null>(null);
  const [catalogReady, setCatalogReady] = useState(false);
  const [catalogResult, setCatalogResult] = useState<CatalogEngineResponse | null>(
    null,
  );
  const [catalogLoading, setCatalogLoading] = useState(false);
  const [catalogError, setCatalogError] = useState<string | null>(null);
  const [retry, setRetry] = useState(0);

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
    setCatalogLoading(true);
    setCatalogError(null);
    setCatalogResult(null);
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
          setCatalogError(
            err instanceof Error ? err.message : "Catalog calculation failed.",
          );
        }
      })
      .finally(() => {
        if (!cancelled) setCatalogLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [
    catalogReady,
    session.assessmentYear,
    session.income,
    session.reliefAnswers,
    entries,
    retry,
  ]);

  return (
    <div className="space-y-6">
      <div className="space-y-1">
        <h2 className="text-lg font-semibold">Interview report</h2>
        <p className="text-sm text-muted-foreground">
          Catalog-sourced provenance for YA {yaDisplay(session.assessmentYear)}.
          {engineYear
            ? " Official engine figures stay on the calculate() report."
            : " No official calculate() path exists for this year."}
        </p>
      </div>

      <CatalogEstimateCard
        ya={session.assessmentYear}
        result={catalogResult}
        loading={catalogLoading}
        error={catalogError}
        onRetry={() => setRetry((n) => n + 1)}
        rates={rates}
        engineYearCompanion={engineYear}
      />

      {engineYear ? (
        <OfficialEngineWrap>
          <div className="space-y-3 rounded-md border p-4">
            <p className="text-sm text-muted-foreground">
              Verified tax from the Adaptive Tax calculate() engine.
            </p>
            {session.lastCalcId ? (
              <>
                {session.lastOfficialTaxLkr ? (
                  <p className="text-2xl font-semibold tracking-tight">
                    {formatLkr(session.lastOfficialTaxLkr)}
                  </p>
                ) : null}
                <Button type="button" asChild>
                  <Link to={`/adaptive-tax/report/${session.lastCalcId}`}>
                    Open official report
                  </Link>
                </Button>
                <p className="text-xs text-muted-foreground">
                  Full trace, RAG evidence, and legal narrative (unchanged Calculator
                  report).
                </p>
              </>
            ) : (
              <p className="text-sm text-muted-foreground">
                Run Result first to store an official calculate() id.{" "}
                <Link
                  className="underline underline-offset-2"
                  to="/adaptive-tax/relief-interview/result"
                >
                  Back to Result
                </Link>
              </p>
            )}
          </div>
        </OfficialEngineWrap>
      ) : null}

      <Button
        type="button"
        variant="outline"
        onClick={() => void navigate("/adaptive-tax/relief-interview/result")}
      >
        Back to Result
      </Button>
    </div>
  );
}
