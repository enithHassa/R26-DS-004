import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import type { ReliefAnswer } from "./catalog-types";
import {
  SESSION_STORAGE_KEY,
  createDefaultSession,
  type ReliefInterviewSession,
  type ReliefInterviewYa,
  type ReliefInterviewIncomeState,
} from "./types";

type IncomePatch =
  | Partial<ReliefInterviewIncomeState>
  | ((prev: ReliefInterviewIncomeState) => Partial<ReliefInterviewIncomeState>);

type ReliefInterviewContextValue = {
  session: ReliefInterviewSession;
  setYears: (assessmentYear: ReliefInterviewYa, compareYear: ReliefInterviewYa) => void;
  setIncome: (income: ReliefInterviewIncomeState) => void;
  patchIncome: (patch: IncomePatch) => void;
  upsertReliefAnswer: (answer: ReliefAnswer) => void;
  setReliefAnswers: (answers: ReliefAnswer[]) => void;
  setSelectedCompareGroupId: (id: string | null) => void;
  setLastOfficialCalc: (calcId: string | null, taxLkr: string | null) => void;
  resetSession: () => void;
};

const ReliefInterviewContext = createContext<ReliefInterviewContextValue | null>(
  null,
);

function loadSession(): ReliefInterviewSession {
  try {
    const raw = sessionStorage.getItem(SESSION_STORAGE_KEY);
    if (!raw) return createDefaultSession();
    const parsed = JSON.parse(raw) as ReliefInterviewSession;
    if (!parsed?.assessmentYear || !parsed?.compareYear || !parsed?.income) {
      return createDefaultSession();
    }
    return {
      ...createDefaultSession(),
      ...parsed,
      income: { ...createDefaultSession().income, ...parsed.income },
      reliefAnswers: Array.isArray(parsed.reliefAnswers) ? parsed.reliefAnswers : [],
      selectedCompareGroupId: parsed.selectedCompareGroupId ?? null,
      lastCalcId: parsed.lastCalcId ?? null,
      lastOfficialTaxLkr: parsed.lastOfficialTaxLkr ?? null,
    };
  } catch {
    return createDefaultSession();
  }
}

function persist(session: ReliefInterviewSession): void {
  try {
    sessionStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify(session));
  } catch {
    // ignore quota / private mode
  }
}

export function ReliefInterviewProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<ReliefInterviewSession>(() => loadSession());

  const setYears = useCallback(
    (assessmentYear: ReliefInterviewYa, compareYear: ReliefInterviewYa) => {
      setSession((prev) => {
        const asOfChanged = prev.assessmentYear !== assessmentYear;
        const next = {
          ...prev,
          assessmentYear,
          compareYear,
          // Stale answers make YoY rule changes look identical in the interview.
          ...(asOfChanged
            ? {
                reliefAnswers: [],
                selectedCompareGroupId: null,
                lastCalcId: null,
                lastOfficialTaxLkr: null,
              }
            : {}),
        };
        persist(next);
        return next;
      });
    },
    [],
  );

  const setIncome = useCallback((income: ReliefInterviewIncomeState) => {
    setSession((prev) => {
      const next = { ...prev, income };
      persist(next);
      return next;
    });
  }, []);

  const patchIncome = useCallback((patch: IncomePatch) => {
    setSession((prev) => {
      const partial = typeof patch === "function" ? patch(prev.income) : patch;
      const next = { ...prev, income: { ...prev.income, ...partial } };
      persist(next);
      return next;
    });
  }, []);

  const upsertReliefAnswer = useCallback((answer: ReliefAnswer) => {
    setSession((prev) => {
      const others = prev.reliefAnswers.filter((a) => a.entry_id !== answer.entry_id);
      const next = { ...prev, reliefAnswers: [...others, answer] };
      persist(next);
      return next;
    });
  }, []);

  const setReliefAnswers = useCallback((answers: ReliefAnswer[]) => {
    setSession((prev) => {
      const next = { ...prev, reliefAnswers: answers };
      persist(next);
      return next;
    });
  }, []);

  const setSelectedCompareGroupId = useCallback((id: string | null) => {
    setSession((prev) => {
      const next = { ...prev, selectedCompareGroupId: id };
      persist(next);
      return next;
    });
  }, []);

  const setLastOfficialCalc = useCallback((calcId: string | null, taxLkr: string | null) => {
    setSession((prev) => {
      const next = { ...prev, lastCalcId: calcId, lastOfficialTaxLkr: taxLkr };
      persist(next);
      return next;
    });
  }, []);

  const resetSession = useCallback(() => {
    const next = createDefaultSession();
    setSession(next);
    persist(next);
  }, []);

  const value = useMemo(
    () => ({
      session,
      setYears,
      setIncome,
      patchIncome,
      upsertReliefAnswer,
      setReliefAnswers,
      setSelectedCompareGroupId,
      setLastOfficialCalc,
      resetSession,
    }),
    [
      session,
      setYears,
      setIncome,
      patchIncome,
      upsertReliefAnswer,
      setReliefAnswers,
      setSelectedCompareGroupId,
      setLastOfficialCalc,
      resetSession,
    ],
  );

  return (
    <ReliefInterviewContext.Provider value={value}>
      {children}
    </ReliefInterviewContext.Provider>
  );
}

export function useReliefInterview(): ReliefInterviewContextValue {
  const ctx = useContext(ReliefInterviewContext);
  if (!ctx) {
    throw new Error("useReliefInterview must be used within ReliefInterviewProvider");
  }
  return ctx;
}
