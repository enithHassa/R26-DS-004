import { Navigate } from "react-router-dom";

import { TaxpayerImpactPanel } from "@/features/personalized-recommendation/components/taxpayer-impact-panel";
import { useUserSessionStore } from "@/features/personalized-recommendation/store/user-session-store";
import { UserViewShell } from "@/pages/user-view/components/user-view-shell";

export function UserFinancialImpactPage() {
  const profileId = useUserSessionStore((s) => s.profileId);

  if (!profileId) {
    return <Navigate to="/login" replace />;
  }

  return (
    <UserViewShell title="Financial Impact" subtitle="Long-term projection from your top recommendation">
      <div className="mx-auto max-w-4xl">
        <TaxpayerImpactPanel profileId={profileId} />
      </div>
    </UserViewShell>
  );
}
