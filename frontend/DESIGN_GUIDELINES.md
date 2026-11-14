# FLAREX — Design Guidelines

**Scope:** The Next.js frontend under `frontend/`

**Goal:** A calm, credible, evidence-first product that looks like a serious scientific company built it.

This document is the single source of truth for visual decisions. New components should use the semantic tokens and primitives below, not raw colors or one-off gradients.

## 0. Brand

**Product name:** FLAREX

**Tagline:** Microgravity Combustion Intelligence

The FLAREX mark combines a flame, an orbital ring, and a small satellite point:
microgravity combustion inside a scientific system. The mark is rendered with
`currentColor` inside a blue gradient tile so it works in light and dark mode.
The wordmark is uppercase with wide tracking; the tagline is small, uppercase,
and muted. The repository slug and internal package identifiers remain
`flame-in-freefall` for continuity.

---

## 1. Design principles

1. **Evidence first.** Warnings, units, missingness, and provenance stay visible. The visual system never makes an uncertain value look certain.
2. **Calm authority.** Neutral surfaces, generous spacing, clear hierarchy, one blue accent. Avoid saturated blue backgrounds, neon status colors, and decorative noise.
3. **Readable density.** Scientific data can be dense, but body text must remain readable. Do not use 10px type for prose or primary labels.
4. **One system.** Every page uses the same header, sidebar, page header, cards, inputs, tables, and states.
5. **Motion is polish, not decoration.** 150–250ms transitions, no attention-seeking animation, and full `prefers-reduced-motion` support.
6. **Theme parity.** Light and dark mode are both first-class. Neither is an afterthought.

---

## 2. Color tokens

The exact base palette is defined in `src/app/globals.css` and consumed through Tailwind theme variables.

### Light mode

| Token | Value | Use |
|---|---|---|
| `--bg` | `#FFFFFF` | Page background |
| `--surface` | `#F6F7F9` | Cards, panels, sidebar |
| `--surface-2` | `#F7F8FA` | Secondary panels, table headers, inputs |
| `--surface-3` | `#E5E8ED` | Skeleton and inset fills |
| `--border` | `#E5E7EB` | Default border |
| `--border-strong` | `#D1D5DB` | Hover/strong border |
| `--text` | `#111827` | Primary text |
| `--text-soft` | `#374151` | Secondary headings/labels |
| `--muted` | `#6B7280` | Muted text |
| `--muted-2` | `#6B7280` | Small labels (kept at AA contrast) |
| `--accent` | `#2563EB` | Buttons, links, active states |
| `--accent-hover` | `#1D4ED8` | Accent hover |
| `--accent-strong` | `#1D4ED8` | Accent text on light surfaces |
| `--accent-soft` | `#F5F8FF` | Active nav, soft accent surfaces |

### Dark mode

| Token | Value | Use |
|---|---|---|
| `--bg` | `#0F1115` | Neutral charcoal background |
| `--surface` | `#171A21` | Cards, panels, sidebar |
| `--surface-2` | `#1D212A` | Secondary panels, table headers |
| `--surface-3` | `#232833` | Skeleton and inset fills |
| `--border` | `#262B35` | Default border |
| `--border-strong` | `#343A46` | Hover/strong border |
| `--text` | `#F5F7FA` | Primary text |
| `--text-soft` | `#D7DCE5` | Secondary headings/labels |
| `--muted` | `#9AA3B2` | Muted text |
| `--muted-2` | `#9AA3B2` | Small labels |
| `--accent` | `#2563EB` | Accent fill |
| `--accent-hover` | `#3B82F6` | Accent hover |
| `--accent-strong` | `#93C5FD` | Accent text on dark surfaces |
| `--accent-soft` | `rgba(37,99,235,0.14)` | Active nav, soft accent surfaces |

The dark mode base is **neutral charcoal**, not navy or saturated blue. Blue is reserved for actions, links, active states, focus rings, and small highlights.

### Status tokens

Status colors are derived from the base system and must remain readable in both modes.

| Token | Light | Dark | Use |
|---|---|---|---|
| `--success` | `#047857` | `#34D399` | Verified, available |
| `--warning` | `#92400E` | `#FBBF24` | Warnings, restrictions |
| `--danger` | `#B91C1C` | `#F87171` | Errors, blocked |
| `--info` | `#1D4ED8` | `#93C5FD` | Informational state |

Soft status surfaces (`--success-soft`, `--warning-soft`, `--danger-soft`, `--info-soft`) are for backgrounds only. Do not place small muted text on them without checking contrast.

### Semantic class names

Use Tailwind semantic utilities:

```text
bg-background  bg-surface  bg-surface-2  bg-surface-3
text-foreground  text-text-soft  text-muted  text-muted-2
border-border  border-border-strong
bg-accent  text-accent-strong  bg-accent-soft
text-success  text-warning  text-danger  text-info
```

Legacy `navy-*`, `ink-*`, `cyan-*`, `ember-*`, `emerald-*`, `amber-*`, `rose-*`, and `violet-*` classes are retained as compatibility aliases mapped to the semantic tokens. New code must use semantic names.

---

## 3. Gradients

Gradients are tokens, not ad-hoc classes.

| Token | Purpose |
|---|---|
| `--gradient-primary` | Primary buttons and key actions: `#2563EB → #1D4ED8` |
| `--gradient-primary-hover` | Primary hover: slightly deeper blue |
| `--gradient-surface` | Card surface: white to `--surface` in light, `#1A1E26` to `--surface` in dark |
| `--gradient-surface-strong` | Stronger panel gradient |
| `--gradient-hero` | Very subtle radial blue glow over the base background, 8–12% opacity |
| `--gradient-text` | Optional hero headline gradient |

Rules:

- Use `primary-gradient` only for primary actions and key highlights.
- Hero glow must stay faint. In dark mode the page must still read as charcoal, not blue.
- Do not put gradients on tables, body text, or status panels.
- Text on a gradient must be white or `--accent-contrast` and meet AA.
- No hard-coded gradient values inside components.

---

## 4. Typography

**Font stack:** Inter/system UI for text; system monospace for identifiers, checksums, and table numerics.

| Role | Size | Weight | Notes |
|---|---|---|---|
| Hero title | 30–48px | 600 | `tracking-[-0.02em]`, balanced |
| Page title | 24–36px | 600 | `tracking-tight` |
| Section title | 15–18px | 600 | Clear hierarchy |
| Body | 14–16px | 400 | 1.6–1.75 line height |
| UI label | 12–13px | 500–600 | Inputs, buttons, table headers |
| Micro label | 10–11px | 600 | Uppercase group labels only |
| Mono | 11–13px | 400 | IDs, hashes, chain-of-custody values |

Rules:

- Minimum body size: 14px. Minimum label size: 11px. Avoid 10px prose.
- Uppercase plus letter-spacing is reserved for short group labels and kickers.
- Do not use monospace for paragraphs.
- Do not use all-caps for long text.

---

## 5. Spacing and layout

- Base spacing unit: **4px**.
- Common rhythm: 8, 12, 16, 20, 24, 32, 40, 48, 64.
- Page max width: **1440px**.
- Sidebar width: **272px** on desktop.
- Header height: **64px**.
- Page padding: 16px mobile, 24px tablet, 32px desktop.
- Section gap: 24–32px.
- Card padding: 20–24px.
- Form grid: 1 column mobile, 2 columns tablet, 3–4 columns desktop.
- Hidden sidebar on mobile; drawer opens from the left with a backdrop.

Do not nest more than two card levels. Prefer a section header plus a flat table/panel over a card inside a card inside a card.

---

## 6. Radii, shadows, motion

| Token | Use |
|---|---|
| `--radius-sm` 8px | Inputs, small buttons |
| `--radius-md` 12px | Panels, alerts |
| `--radius-lg` 16px | Cards, tables |
| `--radius-xl` 20px | Hero, drawers |
| `--shadow-xs` | Subtle border-adjacent elevation |
| `--shadow-sm` | Default card |
| `--shadow-md` | Hover/elevated panel |
| `--shadow-glow` | Accent button hover / focus emphasis |
| `--shadow-lg` | Drawer |

Motion:

- 150ms for color/border transitions.
- 180–220ms for card lift and header glass.
- 240ms for page entrance.
- Respect `prefers-reduced-motion` globally.

---

## 7. Theme behavior

- Default to `prefers-color-scheme` when no stored preference exists.
- Persist the user choice in `localStorage` under `flame-theme`.
- Apply the theme before paint with the inline theme script in `src/app/layout.tsx`; no flash of the wrong theme.
- The toggle is a 36px icon button with an accessible label.
- `color-scheme` is set on the root element for native controls.
- Theme tokens are defined on `:root[data-theme="light"]` and `:root[data-theme="dark"]`.
- No component may assume dark mode.

---

## 8. Shell and navigation

### Header

- Sticky, full width, 64px tall.
- Transparent at the top of the page.
- After ~8px scroll: translucent theme background (80% opacity), `backdrop-filter: blur(16px)`, bottom border, soft shadow.
- Solid background fallback for browsers without backdrop-filter.
- Contains: mobile menu, brand, breadcrumbs (desktop), global search, API status, API docs link, theme toggle.
- Mobile search opens a compact full-width panel below the header, not a third header row.

### Sidebar

- 272px, fixed below the header on desktop.
- Group labels: Explore, Data, Analyze, Reference.
- Active item: accent-soft background, accent text, 2px left indicator.
- Mobile drawer: full-height, backdrop, close button, Escape to close.
- No dead controls. If a control is visible, it must work.

### Footer

- Brand + short read-only description.
- Explore / Analyze / Reference link columns.
- Dataset version, registry snapshot, API v1, read-only badge.
- NASA non-endorsement note.

---

## 9. Components

### Buttons

| Variant | Style |
|---|---|
| Primary | Blue gradient, white text, shadow, hover glow |
| Secondary | Surface fill, border, foreground text |
| Ghost | Transparent, muted text, surface hover |
| Danger | Soft red surface, red text |

Sizes: `sm` 36px, `md` 40px, `icon` 36px. Always use `buttonStyles()`.

### Inputs and filters

- 40px height, 1px border, 8px radius.
- Background `--background`; focus border accent + 2px ring.
- Labels 12px medium; hints 11px muted.
- Error text uses danger token.
- Selects keep native behavior; no custom dropdown unless keyboard-tested.

### Cards

- `surface` for the base card.
- `card-interactive` for clickable cards: 2px lift, accent-tinted border, shadow.
- One primary action per card; avoid competing links.

### Badges

- Rounded full, 11px medium, 20px line height.
- Tones: neutral, accent, success, warning, danger, info, outline.
- Do not use color alone to carry meaning; include text or icon.

### Alerts

- Info: accent-soft.
- Warning: warning-soft.
- Danger: danger-soft.
- Success: success-soft.
- Icon + title + message. Never hide a limitation in a tooltip.

### Tables

- `TableShell` with horizontal scroll.
- Sticky header using `surface-2`.
- 12px body, 10px uppercase header, numeric cells right-aligned and mono.
- No client-side scientific aggregation.
- Keep empty/blocked states explicit.

### Drawers and modals

- Right-side drawer for record/citation detail.
- Backdrop with blur; Escape closes; focus moves to close button; body scroll locks.
- Glass treatment only where readability is preserved.

### Charts

- Use `--chart-*`, `--chart-grid`, `--chart-axis`, and `--chart-tooltip-*`.
- No hard-coded chart colors.
- No dual axes; no interpolation; missing values are gaps.
- Chart frame includes title, unit, source, warnings, and accessible description.

---

## 10. Accessibility

- WCAG 2.1 AA minimum in both themes.
- Visible focus ring on every interactive element.
- Semantic landmarks: header, nav, main, footer.
- `aria-current="page"` for active navigation.
- Skip link is always available.
- Keyboard: `/` focuses global search; Escape closes drawers/search; focus is trapped/returned where appropriate.
- All icon-only buttons have `aria-label`.
- Do not remove the focus outline.
- Body text at least 14px; labels at least 11px.
- Test with axe in light and dark mode.

---

## 11. File map

| File | Responsibility |
|---|---|
| `src/app/globals.css` | Tokens, light/dark themes, surfaces, header glass, hero, prose |
| `src/components/theme-provider.tsx` | Theme store, system preference, persistence |
| `src/components/theme-toggle.tsx` | Accessible light/dark toggle |
| `src/components/brand/flarex-mark.tsx` | Custom orbit-and-flame brand mark |
| `src/components/brand/flarex-brand.tsx` | FLAREX wordmark, tagline, and mark lockup |
| `public/flarex-mark.svg` | Public brand mark asset |
| `public/flarex-logo.svg` | Public horizontal logo asset |
| `src/app/layout.tsx` | Metadata, pre-paint theme script, providers |
| `src/components/layout/app-shell.tsx` | Shell and page container |
| `src/components/layout/topbar.tsx` | Sticky header, search, status, theme, mobile search |
| `src/components/layout/sidebar.tsx` | Desktop navigation and mobile drawer |
| `src/components/layout/footer.tsx` | Footer and data version anchors |
| `src/components/layout/page-header.tsx` | Default and hero page headers |
| `src/components/ui/button.tsx` | Button variants |
| `src/components/ui/card.tsx` | Card, section card, metric card |
| `src/components/ui/filter.tsx` | Filter bar, text/select/checkbox, actions |
| `src/components/ui/states.tsx` | Loading, empty, error, inline alert |
| `src/components/ui/badge.tsx` | Badge tones |
| `src/components/ui/table-shell.tsx` | Table container and cell classes |
| `src/components/scientific/record-drawer.tsx` | Accessible side drawer |
| `src/lib/navigation.ts` | Navigation groups and route labels |

---

## 12. Definition of done for a UI change

- Light and dark screenshots look intentional.
- No raw hex/gradient values in components.
- No new one-off button/input/card styles.
- Keyboard navigation and focus are visible.
- `npm run lint`, `npm run typecheck`, `npm test`, and `npm run build` pass.
- Axe reports no violations on the changed page in both themes.
- Mobile at 390px, tablet at 768px, and desktop at 1440px are checked.
- Scientific warnings, units, missingness, and comparison states remain visible.
