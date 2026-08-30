import { Navigate, useSearchParams } from "react-router-dom";

import {
  TAXWISE_FINANCIAL_IMPACT,
  TAXWISE_PROFILE,
  TAXWISE_RECOMMENDATIONS,
} from "@/pages/user-view/paths";

/** Legacy `/portal/summary?tab=…` → TaxWise pages. */
export function PortalSummaryRedirect() {
  const [searchParams] = useSearchParams();
  const tab = searchParams.get("tab");

  if (tab === "profile") {
    return <Navigate to={TAXWISE_PROFILE} replace />;
  }
  if (tab === "impact") {
    return <Navigate to={TAXWISE_FINANCIAL_IMPACT} replace />;
  }
  return <Navigate to={TAXWISE_RECOMMENDATIONS} replace />;
}
