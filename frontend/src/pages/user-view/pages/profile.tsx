import { Navigate } from "react-router-dom";

import { TaxReturnProfile } from "@/features/tax-return-profile/tax-return-profile";
import { useUserSessionStore } from "@/features/personalized-recommendation/store/user-session-store";
import { UserViewShell } from "@/pages/user-view/components/user-view-shell";

export function UserProfilePage() {
  const profileId = useUserSessionStore((s) => s.profileId);

  if (!profileId) {
    return <Navigate to="/login" replace />;
  }

  return (
    <UserViewShell embedded>
      <TaxReturnProfile profileId={profileId} />
    </UserViewShell>
  );
}
