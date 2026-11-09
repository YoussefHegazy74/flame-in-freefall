import { describe, expect, it } from "vitest";
import {
  formatBytes,
  formatCount,
  formatDate,
  formatNumber,
  formatUnit,
} from "@/lib/format";

describe("format helpers", () => {
  it("renders missing numbers as an em dash, never zero", () => {
    expect(formatNumber(null)).toBe("—");
    expect(formatNumber(undefined)).toBe("—");
    expect(formatNumber(Number.NaN)).toBe("—");
    expect(formatNumber(0)).toBe("0");
  });

  it("renders missing counts as an em dash", () => {
    expect(formatCount(null)).toBe("—");
    expect(formatCount(1234)).toBe("1,234");
  });

  it("renders unknown units explicitly", () => {
    expect(formatUnit(null)).toBe("not stated");
    expect(formatUnit("")).toBe("not stated");
    expect(formatUnit("mole fraction")).toBe("mole fraction");
  });

  it("renders missing dates and bytes as an em dash", () => {
    expect(formatDate(null)).toBe("—");
    expect(formatBytes(null)).toBe("—");
    expect(formatBytes(26933)).toBe("26.9 kB");
  });
});
