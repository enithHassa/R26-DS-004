import { FileSpreadsheet } from "lucide-react";

import type { FeatureModule } from "@/features/types";

import { TransactionDocumentExtractionPage } from "./pages/document-extraction";

const transactionSemantic: FeatureModule = {
  id: "transaction-semantic",
  title: "Transaction Semantics",
  routes: [{ path: "transaction-documents", element: <TransactionDocumentExtractionPage /> }],
  nav: [{ to: "/transaction-documents", label: "Documents", icon: FileSpreadsheet }],
};

export default transactionSemantic;
