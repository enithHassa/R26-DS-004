/**
 * Fifth Schedule 1(d) — Samurdhi beneficiary shop contribution (from 1 Apr 2021).
 * No separate rupee/% cap in the Act text; eligibility conditions are the gate.
 */

export const SAMURDHI_SHOP_QP_GROUP = "qp_samurdhi_shop";

export function isSamurdhiShopQpGroup(compareGroupId: string): boolean {
  return compareGroupId === SAMURDHI_SHOP_QP_GROUP;
}
