/**
 * Fifth Schedule 2(c) rental income relief — 25% of included Sec 7 inv_rents.
 * Gross rents live on Income (inv_rents); relief claim = floor(0.25 × rents).
 */

export const RENTAL_INCOME_RELIEF_GROUP = "rental_income_relief";

export const INV_RENTS_COMPONENT_ID = "inv_rents";

export function isRentalIncomeReliefGroup(compareGroupId: string): boolean {
  return compareGroupId === RENTAL_INCOME_RELIEF_GROUP;
}

/** Match engine `_floor1(inv_rents × 0.25)` (whole LKR, round down). */
export function rentalIncomeReliefAmount(rentsLkr: number): number {
  if (!Number.isFinite(rentsLkr) || rentsLkr <= 0) return 0;
  return Math.floor(rentsLkr * 0.25);
}
