import { useCallback, useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { getProfile, updateProfile } from "@/features/personalized-recommendation/api/profiles";

import { detailFromProfile, detailToUpdatePayload } from "./mappers";
import type { TaxReturnDetail } from "./types";

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
    setDetail(detailFromProfile(profileQuery.data));
    const stored = profileQuery.data.section_completion;
    setCompleted(new Set(Array.isArray(stored) ? stored : []));
  }, [profileQuery.data]);

  const saveMutation = useMutation({
    mutationFn: (payload: ReturnType<typeof detailToUpdatePayload>) =>
      updateProfile(profileId, payload),
    onSuccess: (data) => {
      queryClient.setQueryData(["profile", profileId], data);
    },
  });

  const persist = useCallback(
    async (nextDetail: TaxReturnDetail, nextCompleted: Set<number>) => {
      const payload = detailToUpdatePayload(nextDetail, [...nextCompleted]);
      await saveMutation.mutateAsync(payload);
    },
    [saveMutation],
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
      if (sectionNum < 8) {
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
    error: profileQuery.error ?? saveMutation.error ?? null,
  };
}
