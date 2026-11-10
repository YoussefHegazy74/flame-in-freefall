import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

const PAGES = [
  { path: "/", name: "overview" },
  { path: "/experiments/gas-flame", name: "gas-flame explorer" },
  { path: "/quality", name: "quality center" },
  {
    path: "/compare?left=psi-10-gas-flame.oxygen_mole_fraction&right=psi-159-gas-flame.oxygen_mole_fraction",
    name: "comparison studio",
  },
  { path: "/datasets/psi-98-metadata", name: "dataset metadata" },
  { path: "/publications", name: "publications" },
  { path: "/assistant", name: "research assistant" },
];

for (const target of PAGES) {
  test(`${target.name} has no serious or critical accessibility violations`, async ({
    page,
  }) => {
    await page.goto(target.path);
    await page.waitForLoadState("networkidle");

    const results = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
      .analyze();

    const blocking = results.violations.filter(
      (violation) =>
        violation.impact === "serious" || violation.impact === "critical",
    );

    expect(
      blocking.map((violation) => ({
        id: violation.id,
        impact: violation.impact,
        help: violation.help,
        targets: violation.nodes.map((node) => node.target),
      })),
    ).toEqual([]);
  });
}
