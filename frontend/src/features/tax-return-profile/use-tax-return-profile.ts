import { useCallback, useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { getProfile, updateProfile } from "@/features/personalized-recommendation/api/profiles";

import { detailFromProfile, detailToUpdatePayload } from "./mappers";
import type { TaxReturnDetail } from "./types";
import {
  exportProfileEvidence,
  hasPublishedEvidenceSnapshot,
  importProfileEvidence,
} from "@/features/optimization-explainable-engine/relief-evidence";
import {
  exportIncomeDocs,
  hasPublishedIncomeDocsSnapshot,
  importIncomeDocs,
} from "@/features/optimization-explainable-engine/income-docs";

export function useTaxReturnProfile(profileId: string) {
  const queryClient = useQueryClient();
  const [detail, setDetail] = useState<TaxReturnDetail | null>(null);
  const [completed, setCompleted] = useState<Set<number>>(new Set());
  const [activeSection, setActiveSection] = useState(1);

  const profileQuery = useQuery({
    queryKey: ["profile", profileId],
    queryFn: () => getProfile(profileId),
  });

  useEffect(() => {
    if (!profileQuery.data) return;
    const next = detailFromProfile(profileQuery.data);
    setDetail(next);
    const stored = profileQuery.data.section_completion;
    setCompleted(new Set(Array.isArray(stored) ? stored : []));
    const storedDetail = profileQuery.data.tax_return_detail as
      | {
          section6?: { reliefEvidenceByYear?: TaxReturnDetail["section6"]["reliefEvidenceByYear"] };
          incomeDocumentsByYear?: TaxReturnDetail["incomeDocumentsByYear"];
        }
      | undefined;
    const published = storedDetail?.section6?.reliefEvidenceByYear;
    if (hasPublishedEvidenceSnapshot(published)) {
      importProfileEvidence(profileId, published);
    }
    if (hasPublishedIncomeDocsSnapshot(storedDetail?.incomeDocumentsByYear)) {
      importIncomeDocs(profileId, storedDetail?.incomeDocumentsByYear);
    }
  }, [profileId, profileQuery.data]);

  const saveMutation = useMutation({
    mutationFn: (payload: ReturnType<typeof detailToUpdatePayload>) =>
      updateProfile(profileId, payload),
    onSuccess: (data) => {
      queryClient.setQueryData(["profile", profileId], data);
    },
  });

  const persist = useCallback(
    async (nextDetail: TaxReturnDetail, nextCompleted: Set<number>) => {
      const snapshot = exportProfileEvidence(profileId);
      const incomeDocs = exportIncomeDocs(profileId);
      const withEvidence: TaxReturnDetail = {
        ...nextDetail,
        section6: {
          ...nextDetail.section6,
          reliefEvidenceByYear: snapshot,
        },
        incomeDocumentsByYear: incomeDocs,
      };
      importProfileEvidence(profileId, snapshot);
      importIncomeDocs(profileId, incomeDocs);
      setDetail(withEvidence);
      const payload = detailToUpdatePayload(withEvidence, [...nextCompleted]);
      await saveMutation.mutateAsync(payload);
    },
    [profileId, saveMutation],
  );

  const saveDraft = useCallback(async () => {
    if (!detail) return;
    await persist(detail, completed);
  }, [completed, detail, persist]);

  const markComplete = useCallback(
    async (sectionNum: number) => {
      if (!detail) return;
      const nextCompleted = new Set([...completed, sectionNum]);
      setCompleted(nextCompleted);
      await persist(detail, nextCompleted);
      if (sectionNum < 9) {
        setActiveSection(sectionNum + 1);
      }
    },
    [completed, detail, persist],
  );

  return {
    detail,
    setDetail,
    completed,
    setCompleted,
    activeSection,
    setActiveSection,
    saveDraft,
    markComplete,
    isSaving: saveMutation.isPending,
    isLoading: profileQuery.isLoading,
    loadError: profileQuery.error ?? null,
    saveError: saveMutation.error ?? null,
  };
}
