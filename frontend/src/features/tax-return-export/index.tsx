import { FileSpreadsheet } from "lucide-react";

import type { FeatureModule } from "@/features/types";

import { TaxReturnExportPage } from "./pages/export";

const taxReturnExport: FeatureModule = {
  id: "tax-return-export",
  title: "Tax Return Export",
  navRoot: "/tax-return-export",
  routes: [{ path: "tax-return-export", element: <TaxReturnExportPage /> }],
  nav: [{ to: "/tax-return-export", label: "Excel workbook", icon: FileSpreadsheet }],
};

export default taxReturnExport;
