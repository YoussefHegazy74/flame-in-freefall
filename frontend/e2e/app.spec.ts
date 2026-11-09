import { expect, test } from "@playwright/test";

const TELEMETRY_RUN = "PSI-100::PSI-100_Raw Data_Raw telemetry file";
const SMOKE_RUN = "PSI-101::PSI-101_Raw Data_HKPData_gmt211_2";

const OXYGEN_LEFT = "psi-10-gas-flame.oxygen_mole_fraction";
const OXYGEN_RIGHT = "psi-159-gas-flame.oxygen_mole_fraction";
const BLOCKED_LEFT = "psi-25-material.initial_o2_pct";
const BLOCKED_RIGHT = "psi-26-material.o2_pct";

const PROVENANCE_FILE = "PSI-10_Experimental table_Flame Design_Normal Flame.csv";

function encodedPair(left: string, right: string, extra = ""): string {
  return `/compare?left=${encodeURIComponent(left)}&right=${encodeURIComponent(right)}${extra}`;
}

test.describe("overview dashboard", () => {
  test("renders live registry metrics and the scientific warning", async ({ page }) => {
    await page.goto("/");

    await expect(
      page.getByRole("heading", {
        name: "NASA microgravity combustion, without invented certainty.",
      }),
    ).toBeVisible();
    await expect(
      page.getByText("This is an evidence explorer, not a measurement product."),
    ).toBeVisible();
    await expect(page.getByText("8,058,206")).toBeVisible();
    await expect(page.getByText("Canonical rows", { exact: true })).toBeVisible();
    await expect(page.getByText("93", { exact: true })).toBeVisible();
    await expect(page.getByText("60", { exact: true })).toBeVisible();
    await expect(
      page.getByRole("heading", { name: "Serving states across the nine curated datasets" }),
    ).toBeVisible();
    await expect(page.getByText("Metadata only").first()).toBeVisible();

    await page.getByRole("link", { name: /Browse curated datasets/i }).click();
    await expect(page).toHaveURL(/\/datasets$/);
    await expect(page.getByRole("heading", { name: "Curated datasets" })).toBeVisible();
  });
});

test.describe("investigation catalog", () => {
  test("searches the API and keeps the query in the URL", async ({ page }) => {
    await page.goto("/investigations");

    await expect(page.getByRole("heading", { name: "Investigation catalog" })).toBeVisible();
    await expect(page.getByText("24 investigations", { exact: true })).toBeVisible();

    await page.locator("#investigation-search").fill("PSI-159");
    await page.locator("#investigation-search").press("Enter");

    await expect(page).toHaveURL(/\/investigations\?q=PSI-159/);
    await expect(page.getByText("1 matching investigation")).toBeVisible();
    await expect(
      page.getByRole("link", {
        name: "Advanced Combustion via Microgravity Experiments / Cool Flames Investigation with Gases",
      }),
    ).toBeVisible();
  });

  test("filters by curated role on the backend", async ({ page }) => {
    await page.goto("/investigations?role=primary");

    await expect(page.getByText("4 investigations", { exact: true })).toBeVisible();
    await expect(page.getByRole("link", { name: /Flame Design/ })).toBeVisible();
    await expect(page.getByRole("link", { name: /SAFFIRE-I/ })).toHaveCount(0);
  });
});

test.describe("dataset serving states", () => {
  test("shows different decisions for different uses", async ({ page }) => {
    await page.goto("/datasets/psi-100-telemetry");

    await expect(
      page.getByRole("heading", { name: "PSI-100 SAFFIRE-III telemetry" }),
    ).toBeVisible();
    await expect(
      page.getByRole("heading", { name: "Serving decisions by use" }),
    ).toBeVisible();
    await expect(
      page.getByRole("article", { name: "Time series serving decision" }),
    ).toContainText("Available with warnings");
    await expect(
      page.getByRole("article", { name: "Quantitative comparison serving decision" }),
    ).toContainText("Blocked");
    await expect(
      page.getByText(
        "The same dataset can be available for one use and blocked for another.",
      ),
    ).toBeVisible();
  });
});

test.describe("gas-flame explorer", () => {
  test("binds pressure filters to an explicit accession unit", async ({ page }) => {
    await page.goto("/experiments/gas-flame");

    await expect(
      page.getByRole("heading", { name: "PSI-10 and PSI-159 gas-flame tests" }),
    ).toBeVisible();
    await expect(page.getByLabel(/Pressure ≥/)).toBeDisabled();
    await expect(
      page.getByText("Mixed pressure units: choose an accession before pressure filtering"),
    ).toBeVisible();

    await page.getByLabel("Accession").selectOption("PSI-10");
    const pressureMin = page.getByLabel(/Pressure ≥ \(atm\)/);
    await expect(pressureMin).toBeEnabled();
    await pressureMin.fill("1.2");
    await page.getByRole("button", { name: "Apply filters" }).click();

    await expect(page).toHaveURL(/accession=PSI-10/);
    await expect(page).toHaveURL(/pressure_min=1\.2/);
    await expect(
      page.getByText("pressure filter field: pressure_initial_atm (atm)"),
    ).toBeVisible();

    await page.getByLabel("Accession").selectOption("PSI-159");
    const barPressure = page.getByLabel(/Pressure ≥ \(bar\)/);
    await expect(barPressure).toHaveValue("");
    await page.getByRole("button", { name: "Apply filters" }).click();

    await expect(page).toHaveURL(/accession=PSI-159/);
    await expect(page).not.toHaveURL(/pressure_min=/);
    await expect(
      page.getByText("pressure filter field: pressure_approx_bar (bar)"),
    ).toBeVisible();
  });
});

test.describe("telemetry explorer", () => {
  test("preserves run identity, time units, and channel units", async ({ page }) => {
    const url = `/telemetry?run=${encodeURIComponent(TELEMETRY_RUN)}&channels=pcm_air_temp_c&start=0&end=100000`;
    await page.goto(url);

    await expect(page.getByRole("heading", { name: "PSI-100 telemetry runs" })).toBeVisible();
    await expect(page.getByText("Runs are independent")).toBeVisible();
    await expect(page.getByText("time unit: ms").first()).toBeVisible();
    await expect(page.getByText(TELEMETRY_RUN).first()).toBeVisible();
    await expect(
      page.getByRole("heading", { name: "PSI-100 time series — °C" }),
    ).toBeVisible();
    await expect(page.getByText("y: °C")).toBeVisible();
    await expect(page.getByText("x: ms")).toBeVisible();
    await expect(
      page.getByText("1 channel · 54 returned points · standard signal"),
    ).toBeVisible();
    await expect(page.getByText(/No timeline is stitched across runs/)).toBeVisible();
  });

  test("shows backend 413 guidance without silently retrying", async ({ page }) => {
    const url = `/telemetry?run=${encodeURIComponent(TELEMETRY_RUN)}&channels=pcm_air_temp_c&start=0&end=100000&max_points=1`;
    await page.goto(url);

    await expect(
      page.getByRole("heading", { name: "The telemetry series could not be loaded" }),
    ).toBeVisible();
    await expect(page.getByText("code: range_too_large")).toBeVisible();
    await expect(page.getByText(/The request would return 54 points/)).toBeVisible();
    await expect(page.getByText(/The API reports 54 distinct timestamps/)).toBeVisible();
    await expect(
      page.getByRole("button", { name: /Use suggested end =/ }),
    ).toBeVisible();

    const current = new URL(page.url());
    expect(current.searchParams.get("max_points")).toBe("1");
    expect(current.searchParams.get("end")).toBe("100000");
  });
});

test.describe("smoke explorer", () => {
  test("preserves run identity, elapsed seconds, and detector warnings", async ({ page }) => {
    const url = `/smoke?run=${encodeURIComponent(SMOKE_RUN)}&channels=gas_plume_temp_c&start=79&end=400`;
    await page.goto(url);

    await expect(
      page.getByRole("heading", { name: "PSI-101 smoke and housekeeping runs" }),
    ).toBeVisible();
    await expect(page.getByText("Separate runs")).toBeVisible();
    await expect(page.getByText("time unit: s").first()).toBeVisible();
    await expect(page.locator("#smoke-run")).toHaveValue(SMOKE_RUN);
    await expect(page.getByText(/HKPData_gmt211_2\.csv/).first()).toBeVisible();
    await expect(page.getByText(/79–1,463 s/).first()).toBeVisible();
    await expect(
      page.getByRole("heading", { name: "PSI-101 time series — °C" }),
    ).toBeVisible();
    await expect(page.getByText("y: °C")).toBeVisible();
    await expect(page.getByText("x: s")).toBeVisible();
    await expect(
      page.getByText("1 channel · 318 returned points · standard signal"),
    ).toBeVisible();
    await expect(
      page.getByText("Detector signals are not calibrated smoke measurements."),
    ).toBeVisible();
  });
});

test.describe("comparison studio", () => {
  test("upgrades a conditional decision only after explicit conditions are verified", async ({
    page,
  }) => {
    await page.goto(encodedPair(OXYGEN_LEFT, OXYGEN_RIGHT));

    await expect(
      page.getByRole("heading", { name: "Backend-approved measurement comparisons" }),
    ).toBeVisible();
    await expect(
      page.locator('[data-status="conditionally_comparable"]').first(),
    ).toBeVisible();
    await expect(page.getByText("rule: psi10-psi159-oxygen")).toBeVisible();
    await expect(page.getByText("same_oxygen_basis").first()).toBeVisible();
    await expect(
      page.getByText("The comparison is not approved in its current state."),
    ).toBeVisible();

    const conditions = page.getByRole("checkbox");
    await expect(conditions).toHaveCount(2);
    await conditions.nth(0).check();
    await conditions.nth(1).check();
    await expect(page.getByText("Conditions changed but not applied")).toBeVisible();

    await page
      .getByRole("button", { name: "Re-evaluate with current conditions" })
      .click();

    await expect(page).toHaveURL(/cond_same_oxygen_basis=true/);
    await expect(page).toHaveURL(/cond_flame_configuration_documented=true/);
    await expect(page.locator('[data-status="comparable"]').first()).toBeVisible();
    await expect(page.getByText("Comparison approved by the backend.")).toBeVisible();
  });

  test("renders a blocked decision with warnings and no chart", async ({ page }) => {
    await page.goto(encodedPair(BLOCKED_LEFT, BLOCKED_RIGHT));

    await expect(page.locator('[data-status="blocked"]').first()).toBeVisible();
    await expect(page.getByText("rule: bass25-26-o2")).toBeVisible();
    await expect(page.getByText("No shared comparison chart is rendered.")).toBeVisible();
    await expect(
      page.getByText(/has an ambiguous or unstated unit/).first(),
    ).toBeVisible();
    await expect(page.locator("figure")).toHaveCount(0);
  });
});

test.describe("quality center", () => {
  test("keeps registry-wide and per-dataset warnings visible", async ({ page }) => {
    await page.goto("/quality");

    await expect(page.getByRole("heading", { name: "Quality center" })).toBeVisible();
    await expect(
      page.getByText("The report summary is registry-wide, not per dataset."),
    ).toBeVisible();
    await expect(
      page.getByRole("heading", { name: "Registry validation report summary" }),
    ).toBeVisible();
    await expect(
      page.getByRole("heading", { name: "Issue catalogue" }),
    ).toBeVisible();
    await expect(
      page
        .getByText(
          "The source header says percent but the observed values are around 0.22. The values are preserved as o2_pct and are not relabeled as initial/final O2.",
        )
        .first(),
    ).toBeVisible();

    await page.goto("/quality?dataset=psi-26-material");
    await expect(
      page.getByRole("heading", {
        name: "Focused dataset quality: PSI-26 BASS as-run material test matrix",
      }),
    ).toBeVisible();
    await expect(
      page.getByText("This is the un-collapsed issue list returned for this dataset."),
    ).toBeVisible();
  });
});

test.describe("provenance explorer", () => {
  test("resolves an exact file and row without fabricating details", async ({ page }) => {
    await page.goto("/provenance");

    await expect(
      page.getByRole("heading", { name: "Resolve a source file and row" }),
    ).toBeVisible();
    await page.locator("#provenance-accession").fill("PSI-10");
    await page.locator("#provenance-file").fill(PROVENANCE_FILE);
    await page.locator("#provenance-row").fill("2");
    await page.getByRole("button", { name: "Resolve provenance" }).click();

    await expect(page).toHaveURL(/accession=PSI-10/);
    await expect(page.getByText("Resolved source")).toBeVisible();
    await expect(page.getByRole("heading", { name: PROVENANCE_FILE })).toBeVisible();
    await expect(page.getByText("Row present in canonical tables")).toBeVisible();
    await expect(page.getByText("experimental_table", { exact: true })).toBeVisible();
    await expect(
      page
        .getByText(
          "4a663292bd3f65201943cc71bd661a70383639276a9176f64105b285bf0b6deb",
        )
        .first(),
    ).toBeVisible();
  });

  test("reports an unknown file as a 404 instead of substituting a match", async ({
    page,
  }) => {
    await page.goto("/provenance?accession=PSI-10&file=does-not-exist.csv");

    await expect(
      page.getByRole("heading", { name: "Provenance could not be resolved" }),
    ).toBeVisible();
    await expect(
      page.getByText("source file is not present in the canonical file metadata"),
    ).toBeVisible();
    await expect(page.getByText("code: not_found")).toBeVisible();
    await expect(page.getByText("http: 404")).toBeVisible();
  });
});
