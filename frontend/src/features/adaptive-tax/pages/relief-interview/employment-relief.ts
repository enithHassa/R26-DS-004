/**
 * Fifth Schedule ¶2(b) employment income relief.
 * Consolidated Act text: Rs 700,000 “…for each year of assessment, but prior
 * to January 1, 2020…”. Not available from YA 2020/21 onward.
 * Interview binding is ``none`` (informational); do not invent an engine path.
 */

export const EMPLOYMENT_INCOME_RELIEF_GROUP = "employment_income_relief";

export function isEmploymentIncomeReliefGroup(compareGroupId: string): boolean {
  return compareGroupId === EMPLOYMENT_INCOME_RELIEF_GROUP;
}

/** Last YA where ¶2(b) still applied (YA ending before / spanning only pre-2020). */
export function isEmploymentIncomeReliefAvailableForYa(
  assessmentYear: string,
): boolean {
  return assessmentYear <= "2019_20";
}
