import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import {
  adjacentCompareYa,
  createDefaultSession,
  hydrateIncomeAmounts,
  sessionStorageKey,
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
  replaceIncome: (income: InterviewIncomeState, assessmentYear?: string) => void;
  replaceSession: (session: InterviewSession) => void;
  upsertReliefAnswer: (answer: ReliefAnswer) => void;
  setEvidenceCheck: (entryId: string, item: string, checked: boolean) => void;
  clearReliefAnswer: (entryId: string) => void;
  resetSession: () => void;
};

const InterviewContext = createContext<InterviewContextValue | null>(null);

function loadSession(storageKey: string): InterviewSession {
  try {
    const raw = sessionStorage.getItem(storageKey);
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
      income: hydrateIncomeAmounts({
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
        taxpayerName:
          typeof parsed.income?.taxpayerName === "string" ? parsed.income.taxpayerName : "",
        tin: typeof parsed.income?.tin === "string" ? parsed.income.tin : "",
        interestSchedule: Array.isArray(parsed.income?.interestSchedule)
          ? parsed.income.interestSchedule
          : createDefaultSession().income.interestSchedule,
      }),
      reliefAnswers: Array.isArray(parsed.reliefAnswers) ? parsed.reliefAnswers : [],
      evidenceChecks:
        parsed.evidenceChecks && typeof parsed.evidenceChecks === "object"
          ? parsed.evidenceChecks
          : {},
    };
  } catch {
    return createDefaultSession();
  }
}

function persist(session: InterviewSession, storageKey: string): void {
  try {
    sessionStorage.setItem(storageKey, JSON.stringify(session));
  } catch {
    // ignore quota / private mode
  }
}

export function InterviewProvider({
  children,
  profileId,
}: {
  children: ReactNode;
  profileId?: string | null;
}) {
  const storageKey = sessionStorageKey(profileId);
  const [session, setSession] = useState<InterviewSession>(() => loadSession(storageKey));

  useEffect(() => {
    setSession(loadSession(storageKey));
  }, [storageKey]);

  const setAssessmentYear = useCallback(
    (assessmentYear: string, availableYears?: string[]) => {
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
        persist(next, storageKey);
        return next;
      });
    },
    [storageKey],
  );

  const setExcludeSourceDocId = useCallback(
    (sourceDocId: string | null) => {
      setSession((prev) => {
        const next: InterviewSession = {
          ...prev,
          excludeSourceDocId: sourceDocId,
        };
        persist(next, storageKey);
        return next;
      });
    },
    [storageKey],
  );

  const setSelectedCompareGroupId = useCallback(
    (compareGroupId: string | null) => {
      setSession((prev) => {
        const next: InterviewSession = {
          ...prev,
          selectedCompareGroupId: compareGroupId,
        };
        persist(next, storageKey);
        return next;
      });
    },
    [storageKey],
  );

  const patchIncome = useCallback(
    (patch: IncomePatch) => {
      setSession((prev) => {
        const partial = typeof patch === "function" ? patch(prev.income) : patch;
        const next = { ...prev, income: { ...prev.income, ...partial } };
        persist(next, storageKey);
        return next;
      });
    },
    [storageKey],
  );

  const replaceIncome = useCallback(
    (income: InterviewIncomeState, assessmentYear?: string) => {
      setSession((prev) => {
        const next: InterviewSession = {
          ...prev,
          ...(assessmentYear ? { assessmentYear } : {}),
          income,
        };
        persist(next, storageKey);
        return next;
      });
    },
    [storageKey],
  );

  const replaceSession = useCallback(
    (next: InterviewSession) => {
      const hydrated: InterviewSession = {
        ...next,
        income: hydrateIncomeAmounts(next.income),
      };
      setSession(hydrated);
      persist(hydrated, storageKey);
    },
    [storageKey],
  );

  const upsertReliefAnswer = useCallback(
    (answer: ReliefAnswer) => {
      setSession((prev) => {
        const others = prev.reliefAnswers.filter((a) => a.entry_id !== answer.entry_id);
        const next = { ...prev, reliefAnswers: [...others, answer] };
        persist(next, storageKey);
        return next;
      });
    },
    [storageKey],
  );

  const clearReliefAnswer = useCallback(
    (entryId: string) => {
      setSession((prev) => {
        const next = {
          ...prev,
          reliefAnswers: prev.reliefAnswers.filter((row) => row.entry_id !== entryId),
        };
        persist(next, storageKey);
        return next;
      });
    },
    [storageKey],
  );

  const setEvidenceCheck = useCallback(
    (entryId: string, item: string, checked: boolean) => {
      setSession((prev) => {
        const current = prev.evidenceChecks[entryId] ?? {};
        const next: InterviewSession = {
          ...prev,
          evidenceChecks: {
            ...prev.evidenceChecks,
            [entryId]: { ...current, [item]: checked },
          },
        };
        persist(next, storageKey);
        return next;
      });
    },
    [storageKey],
  );

  const resetSession = useCallback(() => {
    const next = createDefaultSession();
    setSession(next);
    persist(next, storageKey);
  }, [storageKey]);

  const value = useMemo(
    () => ({
      session,
      setAssessmentYear,
      setExcludeSourceDocId,
      setSelectedCompareGroupId,
      patchIncome,
      replaceIncome,
      replaceSession,
      upsertReliefAnswer,
      clearReliefAnswer,
      setEvidenceCheck,
      resetSession,
    }),
    [
      session,
      setAssessmentYear,
      setExcludeSourceDocId,
      setSelectedCompareGroupId,
      patchIncome,
      replaceIncome,
      replaceSession,
      upsertReliefAnswer,
      clearReliefAnswer,
      setEvidenceCheck,
      resetSession,
    ],
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
