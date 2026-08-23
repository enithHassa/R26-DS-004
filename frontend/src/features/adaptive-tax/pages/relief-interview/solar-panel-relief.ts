/**
 * Fifth Schedule 2(g) solar panel acquisition relief — resident individuals.
 * Cap Rs 600,000 per YA; claim limited to spend or bank loan repayments for panels.
 */

export const SOLAR_PANEL_RELIEF_GROUP = "solar_panel_relief";

export function isSolarPanelReliefGroup(compareGroupId: string): boolean {
  return compareGroupId === SOLAR_PANEL_RELIEF_GROUP;
}
