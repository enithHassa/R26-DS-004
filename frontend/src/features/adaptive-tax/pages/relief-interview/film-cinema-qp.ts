/**
 * Fifth Schedule 1(f) film / cinema qualifying payments (from 1 Apr 2021).
 * Film 1(f)(i): Rs 5M is a minimum project-cost gate, not a maximum claim cap.
 * Cinema 1(f)(ii)/(iii): Rs 25M / Rs 10M are maximum cost ceilings.
 * Shared proviso: deduction ≤ 1/3 of taxable income; excess may carry forward.
 */

export const FILM_PRODUCTION_QP_GROUP = "qp_film_production";
export const CINEMA_UPGRADING_QP_GROUP = "qp_cinema_upgrading";
export const CINEMA_CONSTRUCTION_QP_GROUP = "qp_cinema_construction";

export function isFilmProductionQpGroup(compareGroupId: string): boolean {
  return compareGroupId === FILM_PRODUCTION_QP_GROUP;
}

export function isCinemaConstructionQpGroup(compareGroupId: string): boolean {
  return compareGroupId === CINEMA_CONSTRUCTION_QP_GROUP;
}

export function isCinemaUpgradingQpGroup(compareGroupId: string): boolean {
  return compareGroupId === CINEMA_UPGRADING_QP_GROUP;
}

export function isCinemaQpGroup(compareGroupId: string): boolean {
  return (
    isCinemaConstructionQpGroup(compareGroupId) ||
    isCinemaUpgradingQpGroup(compareGroupId)
  );
}

export function isFilmOrCinemaQpGroup(compareGroupId: string): boolean {
  return isFilmProductionQpGroup(compareGroupId) || isCinemaQpGroup(compareGroupId);
}
