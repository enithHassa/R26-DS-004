import { FileSpreadsheet, Scale } from "lucide-react";

import type { FeatureModule } from "@/features/types";

import { TransactionDocumentExtractionPage } from "./pages/document-extraction";
import { TransactionTaxClassificationPage } from "./pages/tax-classification";

const transactionSemantic: FeatureModule = {
  id: "transaction-semantic",
  title: "Transaction Semantics",
  routes: [
    { path: "transaction-documents", element: <TransactionDocumentExtractionPage /> },
    { path: "transaction-tax", element: <TransactionTaxClassificationPage /> },
  ],
  nav: [
    { to: "/transaction-documents", label: "Documents", icon: FileSpreadsheet },
    { to: "/transaction-tax", label: "Tax classification", icon: Scale },
  ],
};

export default transactionSemantic;
