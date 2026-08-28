/** Sri Lanka Year of Assessment options (YA runs 1 April – 31 March). */

function currentAssessmentYearStart(reference = new Date()): number {
  const year = reference.getFullYear();
  // Before April we are still in the YA that began the previous calendar year.
  return reference.getMonth() < 3 ? year - 1 : year;
}

/**
 * Dropdown options for Sec 1 — includes the upcoming YA plus recent history.
 *
 * @param pastCount - how many prior YAs to list below the current one
 * @param includeNext - include one YA ahead of the current period (early planning / filing)
 */
export function assessmentYearSelectOptions(
  pastCount = 3,
  includeNext = true,
): { value: string; label: string }[] {
  const currentStart = currentAssessmentYearStart();
  const starts: number[] = [];

  if (includeNext) {
    starts.push(currentStart + 1);
  }
  starts.push(currentStart);
  for (let i = 1; i <= pastCount; i++) {
    starts.push(currentStart - i);
  }

  return [...new Set(starts)]
    .sort((a, b) => b - a)
    .map((start) => {
      const value = `${start}-${start + 1}`;
      return { value, label: `YA ${value}` };
    });
}
