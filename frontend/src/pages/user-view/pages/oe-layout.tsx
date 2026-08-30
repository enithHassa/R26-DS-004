import { Navigate, Outlet } from "react-router-dom";

import { TaxpayerOeProvider } from "@/features/optimization-explainable-engine/user";
import { useUserSessionStore } from "@/features/personalized-recommendation/store/user-session-store";
import { UserViewShell } from "@/pages/user-view/components/user-view-shell";

/** Shared TaxWise shell + OE scenario provider for all OE user pages. */
export function UserOeLayout() {
  const profileId = useUserSessionStore((s) => s.profileId);
  const fullName = useUserSessionStore((s) => s.fullName);

  if (!profileId) {
    return <Navigate to="/login" replace />;
  }

  const firstName = fullName?.split(/\s+/)[0] ?? "there";

  return (
    <UserViewShell
      title="Optimization and Explainable"
      subtitle={`Personalized tax scenario for ${firstName}`}
    >
      <TaxpayerOeProvider profileId={profileId}>
        <Outlet />
      </TaxpayerOeProvider>
    </UserViewShell>
  );
}
