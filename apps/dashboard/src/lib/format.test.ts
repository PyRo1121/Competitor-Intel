import { describe, expect, test } from "vitest";
import { formatUsd, formatSeniority } from "./format";

describe("formatUsd", () => {
  test("formats millions compactly", () => {
    expect(formatUsd(5_500_000)).toBe("$5.5M");
  });

  test("returns undisclosed for null", () => {
    expect(formatUsd(null)).toBe("Undisclosed");
  });
});

describe("formatSeniority", () => {
  test("maps known bands", () => {
    expect(formatSeniority("senior")).toBe("Senior");
  });
});
