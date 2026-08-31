/**
 * Fifth Schedule 1(a)(iia) — donations in money to Minister-approved charities
 * (institutionalized care for the sick or the needy). Individual cap Rs 75,000.
 */

export const APPROVED_CHARITY_DONATION_GROUP = "donations_approved_charitable";

/** Official IRD register of Minister-declared approved charities (updates over time). */
export const IRD_APPROVED_CHARITY_LIST_URL =
  "https://www.ird.gov.lk/en/publications/SitePages/Approved%20Charity.aspx?menuid=1408";

export function isApprovedCharityDonationGroup(compareGroupId: string): boolean {
  return compareGroupId === APPROVED_CHARITY_DONATION_GROUP;
}
