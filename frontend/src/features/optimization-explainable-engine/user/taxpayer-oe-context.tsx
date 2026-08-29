import {
  createContext,
  useContext,
  type ReactNode,
} from "react";

import { useTaxpayerOeScenario } from "./use-taxpayer-oe-scenario";

type TaxpayerOeContextValue = ReturnType<typeof useTaxpayerOeScenario>;

const TaxpayerOeContext = createContext<TaxpayerOeContextValue | null>(null);

export function TaxpayerOeProvider({
  profileId,
  children,
}: {
  profileId: string;
  children: ReactNode;
}) {
  const value = useTaxpayerOeScenario(profileId);
  return (
    <TaxpayerOeContext.Provider value={value}>{children}</TaxpayerOeContext.Provider>
  );
}

export function useTaxpayerOe(): TaxpayerOeContextValue {
  const ctx = useContext(TaxpayerOeContext);
  if (!ctx) {
    throw new Error("useTaxpayerOe must be used within TaxpayerOeProvider");
  }
  return ctx;
}
