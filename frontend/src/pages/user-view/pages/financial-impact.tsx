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
    <UserViewShell title="Financial Impact" subtitle="Simple charts for each recommendation — see how your money could change">
      <div className="mx-auto max-w-5xl">
        <TaxpayerImpactPanel profileId={profileId} />
      </div>
    </UserViewShell>
  );
}
