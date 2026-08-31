import { describe, expect, it } from "vitest";

import { reliefRequiresReceipt } from "./needs-receipt";

describe("reliefRequiresReceipt", () => {
  it("skips personal relief", () => {
    expect(
      reliefRequiresReceipt({
        compare_group_id: "personal_relief",
        display_name: "Personal Relief",
        auto_applied: true,
        input_kind: "notice",
      }),
    ).toBe(false);
  });

  it("requires a receipt for solar and similar claims", () => {
    expect(
      reliefRequiresReceipt({
        compare_group_id: "solar_panel_relief",
        display_name: "Solar Panel Expenditure",
        auto_applied: false,
        input_kind: "amount",
      }),
    ).toBe(true);
  });
});
