import { test, expect } from "@playwright/test";

test.describe("dashboard smoke", () => {
  test("home dashboard loads", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible();
  });

  test("companies list links to dossier", async ({ page }) => {
    await page.goto("/companies");
    await expect(page.getByRole("heading", { name: "Companies" })).toBeVisible();
    const rowLink = page.locator("table tbody tr a.ci-link").first();
    await expect(rowLink).toBeVisible();
    await rowLink.click();
    await expect(page).toHaveURL(/\/companies\//);
  });

  test("company dossier opens funding tab", async ({ page }) => {
    const detailResponse = page.waitForResponse(
      (res) =>
        res.url().includes("/api/companies/e2e-smoke-co") &&
        res.request().method() === "GET" &&
        res.ok(),
    );
    await page.goto("/companies/e2e-smoke-co");
    await detailResponse;
    await expect(page.getByRole("heading", { name: "E2E Smoke Co" })).toBeVisible();
    await page.getByRole("button", { name: "Funding" }).click();
    await expect(page.getByText("No funding rounds")).toBeVisible();
  });
});
