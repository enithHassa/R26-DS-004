import { Navigate } from "react-router-dom";

import { TAXWISE_BASE } from "@/pages/user-view/paths";

/** Legacy route — open the habits questionnaire modal on the dashboard. */
export function UserAboutYouPage() {
  return <Navigate to={`${TAXWISE_BASE}?habits=open`} replace />;
}
