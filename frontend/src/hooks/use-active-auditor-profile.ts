import { useQuery } from "@tanstack/react-query";

import { getProfile } from "@/features/personalized-recommendation/api/profiles";
import { useAuditorWorkspaceStore } from "@/store/auditor-workspace-store";

export function useActiveAuditorProfile() {
  const activeProfileId = useAuditorWorkspaceStore((s) => s.activeProfileId);

  return useQuery({
    queryKey: ["auditor-workspace", "profile", activeProfileId],
    queryFn: () => getProfile(activeProfileId!),
    enabled: Boolean(activeProfileId),
  });
}
