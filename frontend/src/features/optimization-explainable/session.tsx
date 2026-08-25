import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import {
  SESSION_STORAGE_KEY,
  adjacentCompareYa,
  createDefaultSession,
  type InterviewIncomeState,
  type InterviewSession,
  type ReliefAnswer,
} from "./types";

type IncomePatch =
  | Partial<InterviewIncomeState>
  | ((prev: InterviewIncomeState) => Partial<InterviewIncomeState>);

type InterviewContextValue = {
  session: InterviewSession;
  setAssessmentYear: (assessmentYear: string, availableYears?: string[]) => void;
  setExcludeSourceDocId: (sourceDocId: string | null) => void;
  setSelectedCompareGroupId: (compareGroupId: string | null) => void;
  patchIncome: (patch: IncomePatch) => void;
  upsertReliefAnswer: (answer: ReliefAnswer) => void;
  resetSession: () => void;
};

const InterviewContext = createContext<InterviewContextValue | null>(null);

function loadSession(): InterviewSession {
  try {
    const raw = sessionStorage.getItem(SESSION_STORAGE_KEY);
    if (!raw) return createDefaultSession();
    const parsed = JSON.parse(raw) as InterviewSession;
    if (!parsed?.assessmentYear || !parsed?.income) {
      return createDefaultSession();
    }
    const defaults = createDefaultSession();
    return {
      ...defaults,
      ...parsed,
      compareYear:
        typeof parsed.compareYear === "string"
          ? parsed.compareYear
          : adjacentCompareYa(parsed.assessmentYear),
      excludeSourceDocId:
        typeof parsed.excludeSourceDocId === "string" ? parsed.excludeSourceDocId : null,
      selectedCompareGroupId:
        typeof parsed.selectedCompareGroupId === "string"
          ? parsed.selectedCompareGroupId
          : "personal_relief",
      income: {
        ...createDefaultSession().income,
        ...parsed.income,
        form: { ...createDefaultSession().income.form, ...parsed.income?.form },
        employmentAmounts: {
          ...createDefaultSession().income.employmentAmounts,
          ...parsed.income?.employmentAmounts,
        },
        businessAmounts: {
          ...createDefaultSession().income.businessAmounts,
          ...parsed.income?.businessAmounts,
        },
        investmentAmounts: {
          ...createDefaultSession().income.investmentAmounts,
          ...parsed.income?.investmentAmounts,
        },
        otherAmounts: {
          ...createDefaultSession().income.otherAmounts,
          ...parsed.income?.otherAmounts,
        },
        otherCustomRows: Array.isArray(parsed.income?.otherCustomRows)
          ? parsed.income.otherCustomRows
          : [],
      },
      reliefAnswers: Array.isArray(parsed.reliefAnswers) ? parsed.reliefAnswers : [],
    };
  } catch {
    return createDefaultSession();
  }
}

function persist(session: InterviewSession): void {
  try {
    sessionStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify(session));
  } catch {
    // ignore quota / private mode
  }
}

export function InterviewProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<InterviewSession>(() => loadSession());

  const setAssessmentYear = useCallback((assessmentYear: string, availableYears?: string[]) => {
    setSession((prev) => {
      const changed = prev.assessmentYear !== assessmentYear;
      const next: InterviewSession = {
        ...prev,
        assessmentYear,
        compareYear: changed
          ? adjacentCompareYa(assessmentYear, availableYears)
          : prev.compareYear,
        excludeSourceDocId: changed ? null : prev.excludeSourceDocId,
        ...(changed ? { reliefAnswers: [] } : {}),
      };
      persist(next);
      return next;
    });
  }, []);

  const setExcludeSourceDocId = useCallback((sourceDocId: string | null) => {
    setSession((prev) => {
      const next: InterviewSession = {
        ...prev,
        excludeSourceDocId: sourceDocId,
      };
      persist(next);
      return next;
    });
  }, []);

  const setSelectedCompareGroupId = useCallback((compareGroupId: string | null) => {
    setSession((prev) => {
      const next: InterviewSession = {
        ...prev,
        selectedCompareGroupId: compareGroupId,
      };
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

  const resetSession = useCallback(() => {
    const next = createDefaultSession();
    setSession(next);
    persist(next);
  }, []);

  const value = useMemo(
    () => ({
      session,
      setAssessmentYear,
      setExcludeSourceDocId,
      setSelectedCompareGroupId,
      patchIncome,
      upsertReliefAnswer,
      resetSession,
    }),
    [session, setAssessmentYear, setExcludeSourceDocId, setSelectedCompareGroupId, patchIncome, upsertReliefAnswer, resetSession],
  );

  return <InterviewContext.Provider value={value}>{children}</InterviewContext.Provider>;
}

// eslint-disable-next-line react-refresh/only-export-components -- hook colocated with provider
export function useInterview(): InterviewContextValue {
  const ctx = useContext(InterviewContext);
  if (!ctx) {
    throw new Error("useInterview must be used within InterviewProvider");
  }
  return ctx;
}
