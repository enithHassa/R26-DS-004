import { useActiveAuditorProfile } from "@/hooks/use-active-auditor-profile";
import { profileToTaxpayerId } from "@/lib/profile-bridge/profile-to-taxpayer-id";

/**
 * Transaction-semantic `taxpayer_id` for the auditor's active profile.
 * Returns null when no profile is selected — callers must block classification.
 */
export function useAuditorTaxpayerId(): string | null {
  const profileQuery = useActiveAuditorProfile();
  if (!profileQuery.data) {
    return null;
  }
  return profileToTaxpayerId(profileQuery.data);
}
