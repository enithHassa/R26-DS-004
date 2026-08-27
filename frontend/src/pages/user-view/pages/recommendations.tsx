import { Navigate } from "react-router-dom";

import { TaxpayerRecommendationsPanel } from "@/features/personalized-recommendation/components/taxpayer-recommendations-panel";
import { useUserSessionStore } from "@/features/personalized-recommendation/store/user-session-store";
import { UserViewShell } from "@/pages/user-view/components/user-view-shell";

export function UserRecommendationsPage() {
  const profileId = useUserSessionStore((s) => s.profileId);
  const fullName = useUserSessionStore((s) => s.fullName);

  if (!profileId) {
    return <Navigate to="/login" replace />;
  }

  const firstName = fullName?.split(/\s+/)[0] ?? "there";

  return (
    <UserViewShell
      title="Recommendations"
      subtitle={`Personalized strategies for ${firstName}`}
    >
      <div className="mx-auto max-w-4xl">
        <TaxpayerRecommendationsPanel profileId={profileId} />
      </div>
    </UserViewShell>
  );
}
