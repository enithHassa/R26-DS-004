import { describe, expect, it } from "vitest";

import {
  canonicalEvidenceGroupId,
  evidenceGroupsMatch,
  evidenceYearKeys,
} from "./canonical-group";

describe("canonicalEvidenceGroupId", () => {
  it("maps fallback film / cinema / samurdhi ids onto year-view ids", () => {
    expect(canonicalEvidenceGroupId("film_production_expenditure")).toBe("qp_film_production");
    expect(canonicalEvidenceGroupId("cinema_upgrade_expenditure")).toBe("qp_cinema_upgrading");
    expect(canonicalEvidenceGroupId("samurdhi_shop_contribution")).toBe("qp_samurdhi_shop");
  });

  it("maps donation aliases onto the interview group", () => {
    expect(canonicalEvidenceGroupId("donation_to_approved_charitable_institution")).toBe(
      "donation_to_charitable_institution",
    );
    expect(canonicalEvidenceGroupId("Donation to approved charitable institution")).toBe(
      "donation_to_charitable_institution",
    );
  });
});

describe("evidenceGroupsMatch", () => {
  it("matches taxpayer fallback keys to auditor RAG keys", () => {
    expect(
      evidenceGroupsMatch(
        "donation_to_approved_charitable_institution",
        "donation_to_charitable_institution",
        "Donation to approved charitable institution",
      ),
    ).toBe(true);
  });

  it("does not attach another relief's files via a loose display-name match", () => {
    expect(
      evidenceGroupsMatch(
        "donation_to_approved_charitable_institution",
        "qualifying_payment_carry_forward",
        "Qualifying payment carry forward",
      ),
    ).toBe(false);
    expect(
      evidenceGroupsMatch(
        "qp_film_production",
        "rental_income_relief",
        "Rental income relief",
      ),
    ).toBe(false);
  });
});

describe("evidenceYearKeys", () => {
  it("treats 2025-2026 and 2025_26 as the same year", () => {
    expect(evidenceYearKeys("2025-2026")).toEqual(["2025_26", "2025-2026"]);
    expect(evidenceYearKeys("2025_26")).toEqual(["2025_26"]);
  });
});
