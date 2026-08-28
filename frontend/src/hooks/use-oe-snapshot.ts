import { useCallback, useState } from "react";

import {
  getLatestTaxComputationSnapshot,
  saveTaxComputationSnapshot,
  type TaxComputationSnapshotUpsert,
} from "@/features/personalized-recommendation/api/profiles";
import type { InterviewSession } from "@/features/optimization-explainable-engine/types";
import {
  buildSnapshotPayload,
  sessionFromSnapshot,
  type SnapshotSaveOptions,
} from "@/lib/profile-bridge/oe-snapshot";

export function useOeSnapshotPersistence(profileId: string | null | undefined) {
  const [draftState, setDraftState] = useState<"idle" | "loading" | "done" | "error">("idle");
  const [saveState, setSaveState] = useState<"idle" | "loading" | "done" | "error">("idle");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const saveSnapshot = useCallback(
    async (session: InterviewSession, options: SnapshotSaveOptions) => {
      if (!profileId) return;
      setSaveState("loading");
      setErrorMessage(null);
      try {
        await saveTaxComputationSnapshot(
          profileId,
          buildSnapshotPayload(session, options) as TaxComputationSnapshotUpsert,
        );
        setSaveState("done");
      } catch (err) {
        setSaveState("error");
        setErrorMessage(err instanceof Error ? err.message : "Failed to save snapshot.");
      }
    },
    [profileId],
  );

  const saveDraft = useCallback(
    async (session: InterviewSession, source: SnapshotSaveOptions["source"] = "auditor_manual") => {
      await saveSnapshot(session, { status: "draft", source });
    },
    [saveSnapshot],
  );

  const loadLatestDraft = useCallback(
    async (assessmentYear: string) => {
      if (!profileId) return null;
      setDraftState("loading");
      setErrorMessage(null);
      try {
        const snapshot = await getLatestTaxComputationSnapshot(profileId, assessmentYear);
        setDraftState("done");
        return sessionFromSnapshot(snapshot);
      } catch {
        setDraftState("error");
        setErrorMessage("No saved draft found for this profile and year.");
        return null;
      }
    },
    [profileId],
  );

  return {
    saveDraft,
    saveSnapshot,
    loadLatestDraft,
    draftState,
    saveState,
    errorMessage,
    canPersist: Boolean(profileId),
  };
}
