---
version: alpha
name: Blinka
description: >-
  Warm paper, precise financial typography, one cobalt action color, and
  hairline rules. Reconstructed from the public blinka.co homepage and adapted
  for the Blinka payments-agent console (inbox, review queue, payment rules).
colors:
  # Brand action color. Implemented as --color-accent in src/app/globals.css.
  primary: "#2a4bd0"
  primary-hover: "#2342bd"
  primary-wash: "#f3f5fd"
  # Site value is rgba(42, 75, 208, 0.047); this is that wash composited on canvas.
  route-wash: "#edeff2"
  on-primary: "#ffffff"
  # Light surfaces
  canvas: "#f7f7f4"
  panel: "#ffffff"
  sheet: "#fdfdfd"
  sunken: "#f0f2f4"
  sunken-hover: "#e9ecf2"
  line: "#dedfdc"
  link-underline: "#bdc0c7"
  # Text
  ink: "#1c253a"
  ink-hover: "#334360"
  nav-ink: "#505563"
  muted: "#656975"
  product-ink: "#191c1f"
  product-slate: "#47525d"
  # Status (console). warning is darkened from the code's L 0.55 to pass AA on warning-soft.
  success: "#007456"
  success-soft: "oklch(0.96 0.04 165)"
  warning: "oklch(0.52 0.13 70)"
  warning-soft: "oklch(0.96 0.05 85)"
  danger: "oklch(0.52 0.19 27)"
  danger-soft: "oklch(0.96 0.03 27)"
  # Dark scene (marketing conversion section and footer)
  night: "#111720"
  night-raised: "#171e29"
  night-ink: "#e9edf1"
  night-muted: "#b2bbc7"
  night-rule: "rgba(185, 199, 218, 0.17)"
  glass: "rgba(15, 20, 28, 0.84)"
  glass-ink: "#e9ecef"
  glass-muted: "#b7bdc7"
  dark-focus: "#b9c8ff"
typography:
  headline-display:
    fontFamily: Inter
    fontSize: 63px
    fontWeight: 450
    lineHeight: 1.07
    letterSpacing: -0.047em
  headline-invitation:
    fontFamily: Inter
    fontSize: 63px
    fontWeight: 430
    lineHeight: 1.05
    letterSpacing: -0.055em
  headline-lg:
    fontFamily: Inter
    fontSize: 46px
    fontWeight: 450
    lineHeight: 1.08
    letterSpacing: -0.035em
  headline-md:
    fontFamily: Inter
    fontSize: 28px
    fontWeight: 450
    lineHeight: 1.16
    letterSpacing: -0.035em
  title-lg:
    fontFamily: Inter
    fontSize: 18px
    fontWeight: 450
    lineHeight: 1.4
    letterSpacing: -0.02em
  title-md:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: 450
    lineHeight: 1.4
    letterSpacing: -0.02em
  title:
    fontFamily: Inter
    fontSize: 15px
    fontWeight: 450
    lineHeight: 1.4
    letterSpacing: -0.02em
  body-lg:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: 400
    lineHeight: 1.65
  body-md:
    fontFamily: Inter
    fontSize: 15px
    fontWeight: 400
    lineHeight: 1.6
  body-sm:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: 400
    lineHeight: 1.6
  label-md:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: 500
    lineHeight: 1.2
  label-sm:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: 500
    lineHeight: 1.2
  nav:
    fontFamily: Inter
    fontSize: 13px
    fontWeight: 400
    lineHeight: 1.2
  caption:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: 400
    lineHeight: 1.5
  eyebrow:
    fontFamily: Inter
    fontSize: 11px
    fontWeight: 500
    lineHeight: 1.5
    letterSpacing: 0.1em
  fine-print:
    fontFamily: Inter
    fontSize: 11px
    fontWeight: 400
    lineHeight: 1.7
  amount-display:
    fontFamily: Inter
    fontSize: 49px
    fontWeight: 500
    lineHeight: 1.08
    letterSpacing: -0.045em
    fontFeature: '"tnum" 1'
  amount-md:
    fontFamily: Inter
    fontSize: 30px
    fontWeight: 400
    lineHeight: 1.1
    letterSpacing: -0.045em
    fontFeature: '"tnum" 1'
  amount-row:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: 400
    lineHeight: 1.4
    fontFeature: '"tnum" 1'
rounded:
  none: 0px
  xs: 2px
  sm: 6px
  md: 8px
  lg: 12px
  xl: 16px
  2xl: 20px
  full: 9999px
spacing:
  base: 4px
  xs: 4px
  sm: 8px
  md: 12px
  lg: 16px
  xl: 20px
  2xl: 24px
  3xl: 32px
  4xl: 48px
  5xl: 64px
  section: 90px
  section-sm: 54px
  gutter: 48px
  gutter-tablet: 24px
  gutter-mobile: 20px
  container: 1180px
  container-inbox: 1152px
  container-settings: 1024px
  container-queue: 768px
  container-auth: 384px
  inbox-list-column: 352px
  header-height: 88px
  header-height-mobile: 70px
components:
  # ---- Marketing (blinka.co) ----
  site-header:
    backgroundColor: "{colors.canvas}"
    textColor: "{colors.nav-ink}"
    typography: "{typography.nav}"
    height: 88px
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.on-primary}"
    typography: "{typography.label-md}"
    rounded: "{rounded.full}"
    padding: 25px
    height: 48px
  button-primary-hover:
    backgroundColor: "{colors.primary-hover}"
  button-primary-small:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.on-primary}"
    typography: "{typography.label-sm}"
    rounded: "{rounded.full}"
    padding: 18px
    height: 38px
  button-ink:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.on-primary}"
    typography: "{typography.label-md}"
    rounded: "{rounded.full}"
    padding: 25px
    height: 48px
  button-ink-hover:
    backgroundColor: "{colors.ink-hover}"
  eyebrow:
    textColor: "{colors.muted}"
    typography: "{typography.eyebrow}"
  legal-link:
    textColor: "{colors.ink}"
    typography: "{typography.body-sm}"
  legal-link-underline:
    backgroundColor: "{colors.link-underline}"
  product-sheet:
    backgroundColor: "{colors.sheet}"
    textColor: "{colors.product-ink}"
    rounded: "{rounded.2xl}"
    padding: 23px
  product-meta:
    backgroundColor: "{colors.sheet}"
    textColor: "{colors.product-slate}"
  choice-row:
    backgroundColor: "{colors.sunken}"
    textColor: "{colors.product-ink}"
    rounded: "{rounded.lg}"
    padding: 12px
    height: 59px
  choice-row-hover:
    backgroundColor: "{colors.sunken-hover}"
  choice-row-selected:
    backgroundColor: "{colors.primary-wash}"
    textColor: "{colors.product-ink}"
  route-row:
    textColor: "{colors.ink}"
    rounded: "{rounded.sm}"
    padding: 8px
  route-row-active:
    backgroundColor: "{colors.route-wash}"
    textColor: "{colors.primary}"
  dark-scene:
    backgroundColor: "{colors.night}"
    textColor: "{colors.night-ink}"
  dark-scene-muted:
    backgroundColor: "{colors.night}"
    textColor: "{colors.night-muted}"
  dark-divider:
    backgroundColor: "{colors.night-rule}"
  focus-ring-dark:
    backgroundColor: "{colors.night}"
    textColor: "{colors.dark-focus}"
  glass-panel:
    backgroundColor: "{colors.glass}"
    textColor: "{colors.glass-ink}"
    rounded: "{rounded.2xl}"
    padding: 24px
  glass-panel-muted:
    backgroundColor: "{colors.night-raised}"
    textColor: "{colors.glass-muted}"
    rounded: "{rounded.lg}"
  # ---- Console (this frontend) ----
  app-header:
    backgroundColor: "{colors.panel}"
    textColor: "{colors.ink}"
    typography: "{typography.title-md}"
  app-header-link:
    textColor: "{colors.muted}"
    typography: "{typography.body-sm}"
    rounded: "{rounded.sm}"
    padding: 12px
    height: 36px
  app-tab:
    textColor: "{colors.muted}"
    typography: "{typography.body-sm}"
    padding: 12px
  app-tab-active:
    textColor: "{colors.ink}"
    typography: "{typography.label-md}"
  divider:
    backgroundColor: "{colors.line}"
  app-button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.on-primary}"
    typography: "{typography.label-md}"
    rounded: "{rounded.sm}"
    padding: 16px
    height: 40px
  app-button-primary-hover:
    backgroundColor: "{colors.primary-hover}"
  app-button-secondary:
    backgroundColor: "{colors.panel}"
    textColor: "{colors.ink}"
    typography: "{typography.label-md}"
    rounded: "{rounded.sm}"
    padding: 16px
    height: 40px
  app-button-secondary-hover:
    backgroundColor: "{colors.sunken}"
  app-button-danger:
    backgroundColor: "{colors.panel}"
    textColor: "{colors.danger}"
    typography: "{typography.label-md}"
    rounded: "{rounded.sm}"
    padding: 16px
    height: 40px
  app-button-danger-hover:
    backgroundColor: "{colors.danger-soft}"
  app-input:
    backgroundColor: "{colors.panel}"
    textColor: "{colors.ink}"
    typography: "{typography.body-sm}"
    rounded: "{rounded.sm}"
    padding: 12px
    height: 40px
  app-card:
    backgroundColor: "{colors.panel}"
    textColor: "{colors.ink}"
    rounded: "{rounded.md}"
    padding: 20px
  app-hint:
    backgroundColor: "{colors.canvas}"
    textColor: "{colors.muted}"
    typography: "{typography.caption}"
  filter-pill:
    textColor: "{colors.muted}"
    typography: "{typography.label-sm}"
    rounded: "{rounded.full}"
    padding: 12px
    height: 32px
  filter-pill-active:
    backgroundColor: "{colors.primary-wash}"
    textColor: "{colors.primary}"
  list-row:
    backgroundColor: "{colors.panel}"
    textColor: "{colors.ink}"
    typography: "{typography.body-sm}"
    padding: 20px
  list-row-selected:
    backgroundColor: "{colors.sunken}"
    textColor: "{colors.ink}"
  menu:
    backgroundColor: "{colors.panel}"
    textColor: "{colors.ink}"
    typography: "{typography.body-sm}"
    rounded: "{rounded.sm}"
    width: 288px
  dialog:
    backgroundColor: "{colors.panel}"
    textColor: "{colors.ink}"
    rounded: "{rounded.md}"
    padding: 20px
  token-chip:
    backgroundColor: "{colors.sunken}"
    textColor: "{colors.ink}"
    typography: "{typography.body-sm}"
    rounded: "{rounded.full}"
    height: 32px
  progress-track:
    backgroundColor: "{colors.sunken}"
    rounded: "{rounded.full}"
    height: 6px
  progress-fill:
    backgroundColor: "{colors.primary}"
    rounded: "{rounded.full}"
  error-banner:
    backgroundColor: "{colors.danger-soft}"
    textColor: "{colors.danger}"
    typography: "{typography.body-sm}"
  status-pay:
    backgroundColor: "{colors.success-soft}"
    textColor: "{colors.success}"
    typography: "{typography.label-sm}"
    rounded: "{rounded.full}"
    padding: 8px
  status-review:
    backgroundColor: "{colors.warning-soft}"
    textColor: "{colors.warning}"
    typography: "{typography.label-sm}"
    rounded: "{rounded.full}"
    padding: 8px
  status-hold:
    backgroundColor: "{colors.danger-soft}"
    textColor: "{colors.danger}"
    typography: "{typography.label-sm}"
    rounded: "{rounded.full}"
    padding: 8px
  status-neutral:
    backgroundColor: "{colors.sunken}"
    textColor: "{colors.muted}"
    typography: "{typography.label-sm}"
    rounded: "{rounded.full}"
    padding: 8px
  rule-row:
    backgroundColor: "{colors.sunken}"
    textColor: "{colors.ink}"
    typography: "{typography.body-sm}"
    rounded: "{rounded.xs}"
    padding: 12px
  money-value:
    textColor: "{colors.ink}"
    typography: "{typography.amount-row}"
---

# Blinka Design System

> Warm paper, precise financial typography, cobalt actions, and engraved ribbon forms. Show global banking through tangible product scenes, then close with a quiet, atmospheric dark invitation.

This file follows the [DESIGN.md format](https://github.com/google-labs-code/design.md) (version `alpha`). The YAML front matter holds the normative tokens. The sections below explain how to use them. Validate changes with:

```bash
npx @google/design.md lint frontend/DESIGN.md
```

## Overview

**Sources.** [blinka.co](https://blinka.co/), inspected October 16–17, 2026 at 1440 × 1000 (desktop) and 397 × 883 (mobile): screenshots, computed styles, and the site's published CSS. Console conventions come from reading every file in `frontend/src`. Values called *observed* are measured. Semantic token names, the 4px spacing scale, and prescriptive guidance are interpreted. This is an independently reconstructed reference, not an official brand manual. The signed-in Blinka product was not inspected.

**Two surfaces, one system.**

| Surface | What it is | Density |
|---------|------------|---------|
| Marketing (blinka.co) | Editorial homepage selling global banking to US companies with LatAm teams | Airy: 63px headlines, 48px pill CTAs, ~90px section rhythm |
| Console (this repo) | Operator tool where finance staff watch an agent decide to **pay**, **hold**, or **escalate** each bill, and edit the rules it follows | Compact: 14px body, 36–40px controls, 6–8px radii, 768–1152px columns |

The console takes the site's palette, type voice, hairline structure, and restraint. It does not take the marketing scale. Pill CTAs, display headlines, material gradients, and tilted product sheets stay on marketing pages. At most, the console uses them on the login screen or an empty state.

**Brand personality.** Financial publishing meets a modern banking interface. Calm, exact, trustworthy. Nothing shouts, and money is the most precise thing on the page.

**Audience.** Finance and operations teams at US-incorporated companies paying vendors and contractors across Latin America and other regions. They are busy and accountable for every payment. They need to trust that the agent stays inside its limits and explains each decision.

**Emotional response.** Confidence and control. The interface should feel like a well-kept ledger on good paper: warm, quiet, and legible, with one blue that always means "this is the action".

**Marketing composition, top to bottom (observed).**

1. Sticky translucent header: wordmark left, four section links centered, "Sign in" text link and a small cobalt pill ("Get started ↗") right, a 1px rule beneath.
2. Hero on paper with grain: uppercase eyebrow, two-line headline ending in a period, a muted lead with footnote superscripts, a cobalt pill CTA ("Get started →") next to a two-line secondary link ("Have more questions?" / "Talk to our team ↗"), a short rule, "Backed by Y Combinator", and a fine-print insurance line. A large navy line-engraved ribbon fills the right half and bleeds off the edge.
3. "Trusted by" grayscale logo marquee with a pause button.
4. Product gallery: a heading and copy column beside a product study (account balance with activity rows), then two side-by-side studies (card plus receipt, Treasury fund picker), each with a 28px title, a one-line description, and fine print.
5. "Global payments." A dense two-column route directory (flag, country, currency code, rail), with a dotted globe and a single cobalt route arc on the right.
6. "Your financial back office." Heading on the left, a hairline accordion with outline icons on the right, then "Works with" partner logos.
7. Near-black invitation: eyebrow, a large light headline, a glass form with radio tiles, and a full-width cobalt "Continue →".
8. Dark footer: wordmark and tagline, numbered legal disclosures in a two-column grid, copyright, and legal links.

## Colors

The palette is warm neutrals plus **one** chromatic accent. Cobalt is the only color that signals interaction. Everything else is ink on paper.

### Core palette

Declared as homepage CSS variables (`--launch-*`) and mirrored in `src/app/globals.css`.

| Token | Value | Site variable | Console variable | Role |
|-------|-------|---------------|------------------|------|
| `canvas` | `#f7f7f4` | `--launch-paper` | `--color-canvas` | Page background; warm, softer than white |
| `ink` | `#1c253a` | `--launch-ink` | `--color-ink` | Headlines, primary text, ink buttons |
| `muted` | `#656975` | `--launch-muted` | `--color-muted` | Descriptions, captions, metadata, eyebrows |
| `primary` | `#2a4bd0` | `--launch-accent` | `--color-accent` | CTAs, selection, hover on links, focus outlines |
| `line` | `#dedfdc` | `--launch-line` | `--color-line` | Header rule, section rules, dividers, card borders |

### Supporting palette (observed)

| Token | Value | Role |
|-------|-------|------|
| `primary-hover` | `#2342bd` | Hover for every cobalt button |
| `primary-wash` | `#f3f5fd` | Selected choice, active filter pill |
| `route-wash` | `#edeff2` (site: `rgba(42, 75, 208, 0.047)`) | Active row in a dense list |
| `on-primary` | `#ffffff` | Text on cobalt and ink buttons |
| `panel` | `#ffffff` | Console cards, header, inputs, menus, dialogs |
| `sheet` | `#fdfdfd` | Floating product sheets and receipts |
| `sunken` | `#f0f2f4` | Unselected choices, neutral chips, rule rows, skeletons, selected list row, secondary hover |
| `sunken-hover` | `#e9ecf2` | Hover on a sunken choice or icon button |
| `link-underline` | `#bdc0c7` | 1px underline of legal and inline links before hover |
| `ink-hover` | `#334360` | Hover on an ink button |
| `nav-ink` | `#505563` | Header navigation links |
| `product-ink` | `#191c1f` | Amounts and text inside product studies |
| `product-slate` | `#47525d` | Labels and secondary data inside product studies |

### Status colors (console)

The marketing site shows one status, a green "✓ Completed". The console needs the three agent verdicts plus a neutral state. They are muted so they never compete with cobalt.

| Strong | Soft | Meaning |
|--------|------|---------|
| `success` `#007456` | `success-soft` `oklch(0.96 0.04 165)` | **Pay**: paid, rule passed, payee allowed, mailbox connected |
| `warning` `oklch(0.52 0.13 70)` | `warning-soft` `oklch(0.96 0.05 85)` | **Escalate**: in review, agent evaluating |
| `danger` `oklch(0.52 0.19 27)` | `danger-soft` `oklch(0.96 0.03 27)` | **Hold**: held, blocked, rule failed, error, budget near its limit |
| `muted` | `sunken` | Neutral: received, processing, duplicate, no invoice |

- Pair the strong color (text, glyph, 2px stripe, 6px dot) with its soft background. Never fill a large area with a strong status color.
- Pair color with a word or glyph (`✓`, `!`, `✕`). Color alone never carries meaning.
- Cobalt is never a status. Selected and active items use `primary-wash`, not a status color.
- Budget bars switch from `primary` to `danger` near the limit. That is the only place a status color replaces cobalt.

### Dark scene

Only for the marketing conversion section and footer. The console has no dark mode. If one is added, derive it from these values.

| Token | Value | Role |
|-------|-------|------|
| `night` | `#111720` | Section and footer base |
| `night-raised` | `#171e29` | Loading and raised areas inside the glass panel |
| `night-ink` | `#e9edf1` | Footer and dark-header foreground |
| `night-muted` | `#b2bbc7` | Footer captions, legal text |
| `night-rule` | `rgba(185, 199, 218, 0.17)` | Dividers on dark |
| `glass` | `rgba(15, 20, 28, 0.84)` | Form panel, with `backdrop-filter: blur(28px) saturate(0.45)` |
| `glass-ink` | `#e9ecef` | Text on glass |
| `glass-muted` | `#b7bdc7` | Supporting text on glass |
| `dark-focus` | `#b9c8ff` | Focus outline on any dark surface |

Dark scopes re-point the same variables instead of adding classes (`--launch-ink: #e9ecef; --launch-muted: #b7bdc7; --launch-line: #b7c3d326`). Components keep reading `ink`, `muted`, and `line`. The sticky header switches to `data-theme="dark"` while it sits over the dark section.

### Material backgrounds (marketing only)

Gradients simulate paper and light behind product studies. They are never bright or multicolor, and never sit behind text-heavy content.

| Surface | Observed treatment |
|---------|--------------------|
| USD account stage | `radial-gradient(at 8% 5%, #f9f9f5 0, transparent 60%), linear-gradient(130deg, #e4e8e7, #e5e8ef 80%, #dce1e9)` |
| Card stage | `radial-gradient(at 15% 90%, #e5e4df, transparent 75%), linear-gradient(135deg, #e9e9e6, #eef0f2 60%, #dfe3e6)` |
| Treasury stage | `radial-gradient(at 12% 0, #fcfdf9 0%, transparent 66%), linear-gradient(128deg, #eaf0ea 14%, #e0e9e4 63%, #cbdad3 100%)` |
| Transfer source sheet | `linear-gradient(130deg, #fdfdfd, #f0f2f4)` |
| Dark conversion scene | `radial-gradient(at 68% 28%, #232b35 0%, #171e28 38%, #111720 76%)` plus a faint engraved arc |
| Footer fade | `linear-gradient(rgb(17 23 32 / 0), rgb(17 23 32 / 0.7) 64px, #111720 160px)` |

Country flags, payment-network and rail marks (SEPA, Pix, SPEI, Bre-B), partner logos, and the orange Y Combinator mark keep their own colors. They are assets, not palette.

## Typography

One family: **Inter**, variable. The site self-hosts it as `Blinka Inter` (Latin WOFF2, weights 100–900). The console loads it with `next/font/google` as `--font-inter`.

- **Stack:** `Inter, ui-sans-serif, system-ui, sans-serif` (`--font-sans`).
- **Weights:** 400 body; **450** headings and titles; 500 controls, labels, emphasized names, and eyebrows; 430 for the dark invitation headline only. 600 and 700 are not part of the voice.
- **Tracking:** large headings are tight (`-0.035em` to `-0.055em`). 15–18px titles use `-0.02em`. Body text uses normal tracking. Eyebrows open to `+0.1em` and are uppercase.
- **Numbers:** every amount, count, limit, ID, and date column uses tabular numerals (`tabular-nums`). Large amounts tighten tracking (`-0.03em` to `-0.045em`). Product studies render decimals at `0.68em` and 60% opacity ("$25,000.00" with faded cents). Do that in marketing illustrations only, never in console data.
- **Footnotes:** superscript numerals at ~9.75px in `muted`, with 2–4px leading space, linking to the numbered legal rows in the footer.
- **Monospace:** the site bundles Geist Mono but doesn't use it on the homepage. The console's `--font-mono` is only for machine codes (guardrail violation codes). Email bodies render in `font-sans` inside a `<pre>`. Mono is never a brand voice.

### Type scale

Desktop measured at 1440px; mobile from the site's rules at ≤600px.

| Token | Role | Weight | Desktop size / line height | Tracking | Mobile |
|-------|------|--------|----------------------------|----------|--------|
| `headline-display` | Hero headline, `clamp(48px, 4.4vw, 63px)` | 450 | 63px / 1.07 | -0.047em | `clamp(31px, 8.9vw, 49px)` / 1.08, -0.045em |
| `headline-invitation` | Dark invitation headline, light text | 430 | 63.36px / 1.05 | -0.055em | Scales with the section |
| `headline-lg` | Section heading (accounts) | 450 | 46px / 1.08 | -0.035em | 37px; 33px at ≤360px |
| (variant) | "Global payments." | 450 | 48px / 1.1 | -0.04em | 36px |
| (variant) | "Your financial back office." | 450 | 44px / 1.1 | -0.035em | 38px at ≤1100px, 36px at ≤600px |
| `headline-md` | Product feature title | 450 | 28px / 1.16 | -0.035em | 27px |
| `amount-display` | Large balance in a study | 500 | 49px / 1.08 | -0.045em, tabular | Scales with the study |
| `amount-md` | Secondary balance | 400 | 30px / 1.1 | -0.045em, tabular | Same |
| `title-lg` | Console detail title (email subject) | 450 | 18px / 1.4 | -0.02em | Same |
| `title-md` | Console app-header title | 450 | 16px / 1.4 | -0.02em | Same |
| `title` | Group heading; console card and section title | 450 | 15px / 1.4 | -0.02em | Same |
| `body-lg` | Section description | 400 | 16px / 1.65 | normal | 15px |
| `body-md` | Hero lead, feature description, console decision explanation | 400 | 15px / 1.6–1.65 | normal | 14px |
| `body-sm` | Intro paragraphs; console body text | 400 | 14px / 1.6 | normal | Same |
| `label-md` | Primary CTA; console button | 500 | 14px | normal | 13px |
| `nav` | Header links, back-office row labels at 16px | 400 | 13px | normal | 12px at ≤600px; section links hidden at ≤900px |
| `label-sm` | Small CTA, chips, filter pills | 500 | 12px | normal | 11px |
| `caption` | Backing line, footer links, hints, timestamps | 400 | 12px / 1.5 | normal | 10–12px |
| `eyebrow` | Section kicker, uppercase | 500 | 11px / 1.5 | 0.1em | 10px |
| `fine-print` | Disclosures (max 1030px), "Trusted by" | 400 | 11px / 1.7 | normal | Same |

### Console mapping

Tailwind defaults cover the small end; brand values use arbitrary classes.

| Need | Classes |
|------|---------|
| Body text | `text-sm text-ink` (14px) |
| Hint, metadata, timestamp | `text-xs text-muted` (`HINT_CLASS`) |
| Field label | `text-sm font-medium text-ink` (`LABEL_CLASS`); compact forms use `text-xs font-medium` |
| Card or section title | `text-[15px] font-[450] tracking-[-0.02em] text-ink` (`SECTION_HEADING_CLASS`) |
| App header title | `text-base font-[450] tracking-[-0.02em] text-ink` |
| Detail title | `text-lg font-[450] tracking-[-0.02em] text-ink` |
| Eyebrow | `text-[11px] font-medium tracking-[0.1em] uppercase text-muted` (`EYEBROW_CLASS`) |
| Decision explanation | `text-[15px] leading-relaxed text-ink` |
| Emphasized name in a list | `text-sm font-medium text-ink` |
| Money, limits, IDs | add `tabular-nums`; amounts right-aligned in lists and inputs (`text-right tabular-nums`) |

Reuse the constants in `src/components/settings/styles.ts` rather than retyping class strings.

## Layout

### Spacing scale

The site uses hand-tuned values (5, 7, 8, 12, 15, 18, 22, 23, 25, 28, 36px…). This file normalizes them to a 4px scale that matches Tailwind's (`1` = 4px). New work uses the scale. Odd observed values are only for reproducing a marketing component exactly.

| Token | Value | Tailwind | Typical use |
|-------|-------|----------|-------------|
| `xs` | 4px | `1` | Label to value, chip inner gap |
| `sm` | 8px | `2` | Button groups, tight stacks |
| `md` | 12px | `3` | List-row padding, field grid gap, card header gap |
| `lg` | 16px | `4` | Form field stacks, mobile card padding, mobile gutter |
| `xl` | 20px | `5` | Card padding, gap between decision blocks |
| `2xl` | 24px | `6` | Desktop gutter, gap between cards and columns, page padding |
| `3xl` | 32px | `8` | Between major blocks |
| `4xl` | 48px | `12` | Empty-state padding, marketing heading to content |
| `5xl` | 64px | `16` | Large marketing separation |
| `section` | 90px | — | Marketing section block padding (observed 82–110px) |
| `section-sm` | 54px | — | Marketing section padding on mobile |

### Containers

| Context | Width | Notes |
|---------|-------|-------|
| Marketing | `min(1180px, 100% - 96px)` (`.launch-width`) | `calc(100% - 48px)` at ≤1100px, `calc(100% - 40px)` at ≤600px; body `min-width: 320px` |
| Marketing wide | `min(1480px, 100% - 112px)` | Dark booking grid `minmax(280px, 0.75fr) minmax(0, 1.6fr)`, `gap: clamp(52px, 6vw, 96px)`, one column at ≤1100px |
| Inbox | `max-w-6xl` (1152px) | List/detail split `md:grid-cols-[minmax(0,22rem)_minmax(0,1fr)] md:gap-6` |
| Settings | `max-w-5xl` (1024px) | Policy form plus a 20rem budget aside (`h-fit`) at `lg` |
| Review queue | `max-w-3xl` (768px) | One column of decision cards |
| Login, callback | `max-w-sm` (384px) | Centered vertically and horizontally |

Console pages use `px-4 md:px-6` gutters and `py-6` main padding. Reading widths: hero copy max 680px, hero lead max 440px (340px mobile), hint paragraphs `max-w-xl`.

### Grids and patterns

- **Two-column feature (marketing):** `1fr 1fr`, `gap: 100px`, stepping to 65px, 45px, then one column with `gap: 32px`.
- **Legal rows:** `grid-template-columns: 180px minmax(0, 1fr)`, `gap: 44px`, `padding-block: 25px`, 1px rule on top, 13px/500 label.
- **Facts:** `dl` grid `grid-cols-2 sm:grid-cols-4`, `gap-x-6 gap-y-3`, label above value.
- **Key/value evidence:** `sm:grid-cols-[9rem_minmax(0,1fr)]` rows inside a bordered, divided list.
- **Inline add form:** `md:grid-cols-[12rem_1fr_1fr_auto] md:items-end` so the submit button aligns with the inputs.
- **Card grid:** `grid gap-3 md:grid-cols-2`.

### Headers

- **Marketing:** sticky, `top: 0`, `z-index: 10`, `rgb(247 247 244 / 0.93)` with `backdrop-filter: blur(14px)` and a 1px `line` bottom border inside the container (it does not run full bleed). Height 88px, 76px at ≤1100px, 70px at ≤600px. `html { scroll-padding-top: 100px; scroll-behavior: smooth }`.
- **Console:** `border-b border-line bg-panel`, not sticky, `py-3`. Title on the left; on the right, 36px controls (`h-9`) in `gap-2`: one cobalt action, then quiet header links (`hover:bg-sunken`). Settings adds a tab row underneath.

### Breakpoints

| Marketing (observed) | Change |
|----------------------|--------|
| ≤1250px | First product tightening |
| ≤1100px | Gutters to 24px, header 76px, booking grid stacks |
| ≤900px | Header section links hidden |
| ≤800px, ≤760px | Product studies reflow |
| ≤600px | Mobile: 20px gutters, header 70px, footer stacks, headings shrink |
| ≤420px, ≤374px, ≤360px | Small-phone tightening |

The console uses Tailwind `sm` (640px), `md` (768px), and `lg` (1024px). Below `md` the inbox shows the list or the detail, never both, with a "← Volver" button on the detail. Every screen must work at 360px wide.

## Elevation & Depth

The default is **flat**. Structure comes from 1px `line` borders, white `panel` on warm `canvas`, and whitespace. Shadows only appear on objects meant to look physical or to float.

| Context | Observed shadow |
|---------|-----------------|
| Ink button hover | `0 3px 12px rgb(28 37 58 / 0.08)` |
| Floating product sheet | `0 2px 3px rgb(28 37 58 / 0.02), 0 22px 55px -28px rgb(57 72 97 / 0.23)` |
| Transfer card, layered | `0 1px 2px rgb(28 37 58 / 0.03), 12px 20px 30px -18px rgb(28 37 58 / 0.24), 30px 45px 55px -36px rgb(28 37 58 / 0.27)` |
| Receipt | `0 1px 3px rgb(38 54 74 / 0.03), 0 18px 40px -20px rgb(38 54 74 / 0.35)` |
| Tilted source sheet | `12px 20px 25px -24px rgb(28 37 58 / 0.29)` |
| Physical card art | `0 2px 3px rgb(23 36 53 / 0.2), 0 20px 32px -17px rgb(28 37 58 / 0.467)` plus a 1px `#646975` outline |
| Dark glass panel | `0 24px 80px -32px rgb(4 14 28 / 0.5), inset 0 1px rgb(213 226 245 / 0.05)` |

The recipe is always a near-invisible contact shadow plus one long, soft, negatively spread shadow tinted with ink (`rgb(28 37 58)`), never black. Sheets also get a 1px near-white border (`rgb(255 255 255 / 0.9)`) so the edge reads as paper.

Other depth devices: paper grain (`.grain-paper`, SVG fractal noise at 15% opacity, `mix-blend-mode: multiply`); rotated stacked sheets (`-7deg`, `11deg`) in illustrations; backdrop blur on the header (14px) and glass (28px).

**Console levels**

| Level | Treatment | Used by |
|-------|-----------|---------|
| 0, page | `bg-canvas` | Body |
| 1, surface | `bg-panel border border-line`, no shadow | Cards, list panels, header, inputs |
| 1, inset | `bg-sunken` (often with `border-line`) | Rule rows, email body, review-action box, duplicate notice |
| 2, floating | `bg-panel border border-line` plus the floating-sheet shadow | Dropdown menu, dialog, future popovers and toasts |
| Backdrop | `backdrop:bg-ink/30` | Native `<dialog>` |

For level 2 use the ink-tinted recipe as an arbitrary value, `shadow-[0_2px_3px_rgb(28_37_58/0.02),0_22px_55px_-28px_rgb(57_72_97/0.23)]`, not Tailwind's grey `shadow-lg`/`shadow-xl`.

## Shapes

| Token | Value | Tailwind | Use |
|-------|-------|----------|-----|
| `none` | 0 | `rounded-none` | Rules, full-bleed sections, accordion rows |
| `xs` | 2px | `rounded-sm` | Flags, rule-row stripes, focus outline on inline links |
| — | 4px | `rounded` | Quiet text buttons, skeleton bars, icon hit areas |
| `sm` | 6px | `rounded-md` | Console buttons, inputs, menus, inset boxes; site route rows |
| `md` | 8px | `rounded-lg` | Console cards, list panels, dialogs; site skip link |
| `lg` | 12px | — | Choice rows, option tiles, inner dark panels |
| `xl` | 16px | — | Material studies, receipts, mobile glass panel |
| `2xl` | 20px | — | Stages, floating sheets, desktop glass panel |
| `full` | 9999px | `rounded-full` | Marketing CTAs, status chips, filter pills, token chips, progress bars, dots, flags, radios |

- Nest radii: inner elements are 4–8px smaller than their container (a 7px fund mark in a 12px row in a 20px sheet).
- Round things are truly round (`50%`): flags (32px, 25px), radio marks (16–19px), icon buttons (24–28px), status dots (6px).
- Marketing CTAs are pills. Console buttons are 6px rectangles that share the pill's color and weight, not its shape. In the console, pills are reserved for chips, filters, and progress bars.

## Components

The front matter holds each component's tokens. These notes cover borders, states, and behavior the schema can't express.

### Buttons

| Variant | Tokens | Spec |
|---------|--------|------|
| Primary pill (marketing) | `button-primary` | 48px tall, 25px inline padding, 25px gap to the trailing arrow, 1px transparent border, `transition: background 0.18s, box-shadow 0.18s` |
| Small pill (header) | `button-primary-small` | 38px, 18px padding, 14px gap, `↗` arrow |
| Ink pill | `button-ink` | Secondary emphasis on paper; hover `ink-hover` plus the ink hover shadow |
| Two-line text link | — | 11px muted question over a 13px ink link with `↗` ("Have more questions?" / "Talk to our team ↗") |
| Console primary | `app-button-primary` | `PRIMARY_BUTTON_CLASS`: `h-10 rounded-md bg-accent px-4 text-sm font-medium text-white hover:bg-accent-hover` |
| Console secondary | `app-button-secondary` | `SECONDARY_BUTTON_CLASS`: `border border-line bg-panel`, hover `bg-sunken` |
| Console destructive | `app-button-danger` | `border border-danger/40 bg-panel text-danger hover:bg-danger-soft` ("Rechazar") |
| Quiet text | — | `QUIET_BUTTON_CLASS`: `rounded px-1 text-sm text-muted hover:text-ink` |
| Destructive text | — | `DANGER_TEXT_BUTTON_CLASS`: `text-danger hover:underline` ("Eliminar") |
| Header action | — | 36px (`h-9`) versions of primary and quiet for the console header |
| Icon button | — | `grid size-6`/`size-8 place-items-center rounded(-full) text-muted hover:bg-sunken`, always with `aria-label` |

- One primary button per view or decision. Everything else is secondary or quiet. The approve/reject pair is primary plus destructive.
- In a dialog footer: `flex justify-end gap-2 border-t border-line pt-4`, cancel (secondary) before confirm (primary).
- Pending: keep the width, swap the label to a gerund with three dots ("Aprobando...", "Guardando..."), and disable.
- Disabled: console `opacity-60` (`opacity-50` for text buttons) with `cursor-not-allowed` and no hover change. Marketing uses `opacity: 0.4`.
- Arrows trail the label: `→` to proceed, `↗` for "go elsewhere" (external page, sign-up, contact), `←` only for "back". Never lead a label with an icon.

### Navigation

- **Marketing header links:** `nav` type in `nav-ink`, `gap: 26px`, hover to `primary`.
- **Console tabs:** `px-3 py-2.5 text-sm border-b-2`; current tab `border-accent font-medium text-ink` with `aria-current="page"`; others `border-transparent text-muted hover:text-ink`. The row sits on the header's bottom border (`-mb-px`) and scrolls horizontally on small screens.
- **Back link:** quiet text button "← Volver a la bandeja".

### Selection

| Pattern | Spec |
|---------|------|
| Choice row (light) | Grid `[mark] [label] [radio]`, `min-height: 59px`, `padding: 10px 12px`, 12px radius, `sunken` fill, transparent 1px border. Hover `sunken-hover`. Selected (`aria-pressed="true"`): `primary-wash` fill, 1px `primary` border, radio filled cobalt with a white check |
| Route row (dense list) | No fill, 6px radius, `padding: 10px 8px`, currency code right-aligned in small muted caps. Hover `rgb(28 37 58 / 0.024)`. Active: `route-wash` and `primary` text |
| Option tile (dark) | `min-height: 50px`, 12px radius, fill `rgb(115 130 150 / 0.07)`, border `rgb(146 159 179 / 0.16)`, both doubled on hover. Checked: fill `rgb(42 75 208 / 0.18)`, border `rgb(92 120 232 / 0.85)`. 16px radio with a 6px white dot that scales in over 0.14s |
| Filter pill (console) | `h-8 rounded-full px-3 text-xs font-medium` in a `role="group"` bar; active `bg-accent-wash text-accent` with `aria-pressed`; idle `text-muted hover:bg-sunken` |
| Checkbox (console) | Native `size-4 accent-accent` inside a `min-h-10` label for a 40px target |

### Lists and rows

- **Inbox row:** full-width button, `px-5 py-3.5`, sender `text-sm font-medium`, relative time `text-xs text-muted` on the right, subject `text-sm`, snippet `text-xs text-muted`, then a status chip and the amount (`tabular-nums`, foreign currency with "≈ USD" beneath). Hover `bg-sunken/60`; selected `bg-sunken` with `aria-current`. Focus outline sits inside the row (`-outline-offset-2`).
- **Divided list:** `divide-y divide-line` inside a card, or `rounded-md border border-line` for nested lists.
- **Activity row (marketing):** 32px icon tile (10px radius, `#e9edf2`), name and meta on the left, amount right-aligned. The highlighted row gets `#f5f7fc`, a `#e0e6f0` border, and a cobalt icon on `#e9edf9`.

### Product sheets (marketing)

`product-sheet`: `sheet` background, 1px white border, 20px radius, 23–30px padding, layered ink shadow. `product-ink` amounts, `product-slate` labels, faded decimals. The physical card is real artwork tilted 11°, with a 1px outline.

### Console cards

- `CARD_CLASS` is `rounded-lg border border-line bg-panel`, with padding `p-5` (lists `p-4`, `md:p-5` on decision cards).
- Inside: `space-y-4` or `gap-5`; sub-sections separated by `border-t border-line pt-3`.
- Card header: title on the left, hint or chip on the right (`flex flex-wrap items-baseline justify-between gap-2`).
- Footer actions: `flex gap-3 border-t border-line pt-3`.
- Missing values read "Sin dato" (or "Sin tope" for limits) in `text-muted`.

### Decision card (agent verdict)

The core console component. Order, top to bottom:

1. Eyebrow naming who decided ("Decisión del agente" / "Decisión de una persona") with the verdict chip (`px-3 py-1 text-sm`) on the right.
2. The explanation in `text-[15px] leading-relaxed`, then an optional human note.
3. Facts row: Beneficiario, Monto, ≈ USD, Categoría.
4. Duplicate notice (inset box with a link to the original) when applicable.
5. "Puntos que impiden pagar solo": failing rules, hold before review, always expanded.
6. Collapsed passing rules ("N reglas cumplidas").
7. "Datos leídos de la factura": an evidence table of extracted fields.
8. The checker's opinion, then a collapsible decision history (lazy-loaded, `aria-live="polite"`).
9. Review actions in an inset `bg-sunken` box when a person can decide: title, explanation, optional note `textarea` with a character counter, then "Aprobar pago" and "Rechazar".

### Rule rows

`rule-row`: `flex gap-3 rounded-sm border-l-2 bg-sunken/60 px-3 py-2`. Stripe by effect: `border-l-danger` (hold), `border-l-warning` (review), `border-l-line` (pass). A 12px glyph column (`✕`, `!`, `✓`) in the status color, an `sr-only` effect label, the reason in `text-sm leading-relaxed`, and the rule id, name, and evidence in `text-xs text-muted` joined by ` · `.

### Status chips

| Token | Classes | Email states | Bill verdicts |
|-------|---------|--------------|---------------|
| `status-pay` | `bg-success-soft text-success` | Pagado | Pagada |
| `status-review` | `bg-warning-soft text-warning` | En revisión, Evaluando | En revisión |
| `status-hold` | `bg-danger-soft text-danger` | Frenado, Bloqueado | Frenada, Rechazada |
| `status-neutral` | `bg-sunken text-muted` | Recibido, Revisando, Duplicado, Sin factura | Duplicada |
| Error | `border border-danger/40 bg-panel text-danger` | Error | — |

Shape: `inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-xs font-medium`. States still in progress (received, processing, analyzing) add a 6px `animate-pulse` dot in `bg-current`. Payee chips reuse the same shapes: Permitido (`status-pay`), Bloqueado (`status-hold`).

### Forms

- **Input and select:** `INPUT_CLASS`: `h-10 w-full rounded-md border border-line bg-panel px-3 text-sm text-ink outline-none`. Focus `border-accent ring-2 ring-accent/20`. Disabled `opacity-60`. Numeric inputs add `tabular-nums` (and `text-right` in tables). Currency codes add `uppercase`.
- **Textarea:** same border, radius, and padding (`px-3 py-2`), `resize-y`, placeholder `text-muted/70`, with a right-aligned `text-xs tabular-nums` counter beneath.
- **Field:** `space-y-1.5`: label (`LABEL_CLASS`), control, hint (`HINT_CLASS`). Errors use `role="alert" text-sm text-danger` below the form or field. Visually hidden labels use `sr-only`, never placeholder-only fields.
- **Forms:** `noValidate` with messages written by the app. Save row: primary button and an `aria-live="polite"` hint side by side. The hint explains the consequence before saving and confirms after ("Guardada como versión 4.").
- **Token chips (multi-value):** `h-8 rounded-full bg-sunken pl-3 pr-1 text-sm tabular-nums` with a `size-6` round remove button labeled `Quitar {value}`.
- **Marketing selects:** `appearance: none`, inherit font, custom chevron.

### Menus and dialogs

- **Dropdown menu:** a `<details>`/`<summary>` trigger. The panel is `absolute z-10 mt-1 w-72 max-h-[70vh] overflow-y-auto rounded-md border border-line bg-panel py-1`, aligned left on mobile and right from `md`. Items are full-width `px-3 py-2 text-left text-sm hover:bg-sunken focus-visible:bg-sunken`.
- **Dialog:** native `<dialog>` with `aria-labelledby`, `m-auto w-[min(36rem,calc(100vw-2rem))] rounded-lg border border-line bg-panel p-0`, backdrop `bg-ink/30`. Content is a `form` with `space-y-4 p-5`, the title in `SECTION_HEADING_CLASS`, and the button footer.
- **Destructive confirmation:** `window.confirm("¿Eliminar a {nombre}?")` for now. A styled dialog replacement must keep the question format.

### Feedback states

| State | Pattern |
|-------|---------|
| Loading list or card | `aria-hidden` skeleton bars: `h-3`–`h-10 animate-pulse rounded bg-sunken`, matching the real layout |
| Working | `size-4 animate-spin rounded-full border-2 border-line border-t-accent` spinner with a gerund sentence, inside `aria-live="polite"` |
| Empty | Centered `px-5 py-12`: a `text-sm font-medium` statement ("Tu bandeja está vacía") plus a muted sentence saying what to do next |
| Page error | Full-width `role="alert"` banner under the header: `bg-danger-soft px-4 py-2 text-center text-sm text-danger` |
| Inline error | `role="alert" text-sm text-danger` near the action that failed |
| Blocked by guardrails | Inset `rounded-md border border-danger/30 bg-danger-soft p-4` with a danger title, violation codes in `font-mono text-xs`, and "No se ejecutó ningún agente." |
| Connection status | `rounded-full border border-line bg-panel px-2.5 py-1 text-xs` pill with a 6px `bg-success`/`bg-danger` dot |
| Budget usage | `role="progressbar"` with `aria-valuenow`/`max`; `h-1.5 rounded-full bg-sunken` track, `bg-accent` fill, `bg-danger` near the limit; values in `text-xs tabular-nums` |

### Disclosure and accordion

- **Marketing accordion:** rows separated by `line` rules, no radius, `min-height: 63px`, `padding: 16px 0`, an 18–20px outline icon, a 16px label, `+`/`−` on the right, and the answer in 14px muted indented under the label.
- **Console disclosure:** `<details className="group">` with the marker hidden (`list-none [&::-webkit-details-marker]:hidden`) and a `›` chevron that rotates 90° (`group-open:rotate-90`). The summary is `text-sm text-muted hover:text-ink`.

### Marketing-only blocks

- **Dark invitation:** a `night` section with 110px block padding and the radial gradient. Glass form (`glass-panel`): 20px radius (16px mobile), `padding: 28px 24px 12px`, 1px border `rgb(183 195 211 / 0.19)`, max 900px. Full-width cobalt "Continue →" at 40% opacity until both questions are answered.
- **Footer:** 150px top padding fading into `night`, 82px wordmark plus tagline, "Get in touch ↗" on the right, numbered legal rows, and a 10px copyright row with Legal, Disclosures, Privacy, and Terms.
- **Legal links:** `ink` text, 1px `link-underline` underline at 3px offset, underline turns `currentColor` on hover over 0.15s.
- **Logo marquee:** grayscale marks in 128 × 32px slots, continuous scroll paused on hover, plus a 28px round pause button.

## Do's and Don'ts

- Do keep cobalt (`primary`) for actions, selection, and focus. One cobalt CTA per view.
- Do use `canvas` for the page and `panel` for surfaces. Their contrast is the main separator.
- Do reach for a 1px `line` border and whitespace before a shadow.
- Do set every amount, limit, and ID in tabular numerals with its currency code, and show "≈ USD" next to foreign amounts.
- Do pair every status color with a word or glyph, and put a plain-language explanation next to every agent verdict.
- Do use weight 450 with negative tracking for headings, 400 for body, and 500 for controls, names, and eyebrows.
- Do write sentence case. Marketing headings are short declaratives ending in a period ("Global payments.").
- Do separate inline metadata with ` · ` ("Pix · TED", "CHK-01 · monto máximo").
- Do respect `prefers-reduced-motion` and keep a visible focus outline on every interactive element.
- Do reuse `styles.ts` constants and `@theme` tokens instead of raw hex or retyped class strings.
- Don't add hues, gradients, or bright illustration colors to the console. Flags and logos are the only multicolor content.
- Don't use pure black for text or shadows. Use `ink` and ink-tinted shadows.
- Don't use weights 600 or 700, or all caps outside the 11px eyebrow.
- Don't use pill buttons, display headlines, faded decimals, material gradients, or tilted sheets in console workflows.
- Don't use cobalt for a status, or a status color for an action.
- Don't use Tailwind's grey `shadow-lg`/`shadow-xl`. Cards are flat, and floating layers use the ink recipe.
- Don't use monospace as a voice. It's only for machine codes.
- Don't put em dashes in UI copy, invent figures, or ship placeholder names in product screens.

## Motion

Motion is short, functional, and mostly color.

| Use | Duration | Easing |
|-----|----------|--------|
| Color, background, and border on hover or focus | 0.14–0.18s (console: Tailwind `transition-colors`, 0.15s) | default or `ease-out` |
| Radio dot scale-in | 0.14s | default |
| Legal link underline color | 0.15s | default |
| Disclosure chevron rotation | `transition-transform`, 0.15s | default |
| Hero ribbon entrance | 1.6s | `cubic-bezier(0.2, 0.75, 0.25, 1)` |
| Logo marquee | continuous, pauses on hover and via button | linear |
| Pending status dot, skeletons | `animate-pulse` | Tailwind default |
| Working spinner | `animate-spin` | linear |

- Animate only `color`, `background-color`, `border-color`, `opacity`, and `transform`. Never animate layout.
- `prefers-reduced-motion: reduce` collapses animations and transitions to 0.01ms (in `globals.css`).
- Gate hover-only effects with `@media (hover: hover) and (pointer: fine)` where they would stick on touch.
- Live data refreshes by polling (4s while items are pending, 15s when idle) with no visual flash. Rows update in place.

## Iconography & Imagery

- **Icons:** thin outline glyphs, 1.5px stroke, 14–20px, `currentColor`, usually `muted`. Small directional icons in pills and links are 12–15px. Icons are decorative (`aria-hidden`) unless they are the only content of a button.
- **Text glyphs** are acceptable in the console: `→ ↗ ←` for direction, `› ` for disclosure, `✓ ! ✕` for rule effects, `·` as separator.
- **Flags:** circular at 25–32px in product sheets; rectangular 15–17 × 10–12px with 2px radius in dense lists.
- **Illustration:** navy engraved line art (ribbon, globe dots, dark-section arcs) with a single cobalt highlight such as a route arc. Never photography of people or stock imagery.
- **Product evidence:** show real-looking UI fragments (balances, receipts, rule rows), not abstract icons, to explain a capability.

## Accessibility

- **Focus:** `outline: 2px solid` `primary`. Offset is 5px on marketing links and buttons, 3px on choice rows, and 2px in the console (`focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent`). Inputs use the border-plus-ring treatment. On dark surfaces the outline is `dark-focus` `#b9c8ff`. Never remove an outline without a replacement.
- **Contrast (measured):** `ink` on `canvas` 14.2:1, `muted` on `canvas` 5.1:1, `muted` on `sunken` 4.9:1, white on `primary` 7.0:1, `primary` on `primary-wash` 6.4:1, `night-muted` on `night` 9.3:1, `warning` on `warning-soft` 5.0:1 at the documented L 0.52.
- **Targets:** marketing controls are 38–50px. Console buttons and inputs are 40px, header controls 36px, filter pills 32px, and icon buttons 24–32px with an `aria-label`. Checkbox labels stretch to 40px.
- **Skip link:** `.launch-skip` sits off-screen and appears at `top: 12px` on focus (white, 8px radius, 15px padding).
- **Semantics:** `aria-current` for the selected row and current tab, `aria-pressed` for toggles and filters, `role="group"` with a label for filter bars, `role="alert"` for errors, `aria-live="polite"` for async progress and save confirmations, `role="progressbar"` with values for budgets, and `sr-only` text for glyph-only meaning. Sections get `aria-label`s.
- **Language:** the console is Spanish (`<html lang="es">`; dates and money formatted with `es-CL`). The marketing site is English.

## Voice & Copy

- Plain, calm, and specific. Say what happened and why, in one sentence the operator can act on.
- The console is in Spanish and uses "tú" ("Tu decisión", "Tu bandeja está vacía").
- Gender agrees with the noun: emails are masculine (Pagado, Frenado, Bloqueado), bills are feminine (Pagada, Frenada, Rechazada, Duplicada).
- Labels are sentence case with no trailing period. Explanations, hints, and errors are full sentences with periods.
- Loading: a gerund plus three dots ("Cargando correo...", "Simulando...", "Aprobando...").
- Errors: "No se pudo {acción}." plus what happens next when known ("Reintentando...").
- Empty: say what is missing ("Sin dato", "Sin tope", "La lista negra está vacía."), never a bare dash.
- Amounts keep the ISO currency code before the number (`USD 1.234,56`, `es-CL` format). Dates use medium date with short time. Lists use relative time ("hace 5 minutos").
- Marketing copy is English, sentence case, short declaratives, with footnote superscripts for regulated claims.

## Implementation

| DESIGN.md token | `globals.css` variable | Tailwind utility |
|-----------------|------------------------|------------------|
| `colors.canvas` | `--color-canvas` | `bg-canvas` |
| `colors.panel` | `--color-panel` | `bg-panel` |
| `colors.sunken` | `--color-sunken` | `bg-sunken` |
| `colors.line` | `--color-line` | `border-line`, `divide-line` |
| `colors.ink` | `--color-ink` | `text-ink`, `backdrop:bg-ink/30` |
| `colors.muted` | `--color-muted` | `text-muted` |
| `colors.primary` | `--color-accent` | `bg-accent`, `text-accent`, `border-accent`, `outline-accent`, `ring-accent/20`, `accent-accent` |
| `colors.primary-hover` | `--color-accent-hover` | `hover:bg-accent-hover` |
| `colors.primary-wash` | `--color-accent-wash` | `bg-accent-wash` |
| `colors.success(-soft)` | `--color-success(-soft)` | `text-success`, `bg-success`, `bg-success-soft` |
| `colors.warning(-soft)` | `--color-warning(-soft)` | `text-warning`, `bg-warning-soft` |
| `colors.danger(-soft)` | `--color-danger(-soft)` | `text-danger`, `bg-danger`, `bg-danger-soft`, `border-danger/40` |
| `rounded.xs` / `sm` / `md` / `full` | Tailwind defaults | `rounded-sm` / `rounded-md` / `rounded-lg` / `rounded-full` |

- Add a token here first, then to `@theme` in `src/app/globals.css`. Don't hard-code hex values in components.
- Shared class strings live in `src/components/settings/styles.ts`. Extend them rather than duplicating.
- `npx @google/design.md export --format css-tailwind frontend/DESIGN.md` emits a Tailwind v4 `@theme` block. Rename `primary*` to `accent*` to match the existing utilities.

### Known deviations in the current code

These spots in `frontend/src` don't follow this document yet. Fix them when you next touch the file.

| Where | Deviation | Should be |
|-------|-----------|-----------|
| `app/globals.css` | `--color-warning: oklch(0.55 0.13 70)` gives 4.4:1 on `warning-soft` | `oklch(0.52 0.13 70)` (5.0:1) |
| `app/login/page.tsx` | Title `text-2xl font-semibold tracking-tight`; wordmark `font-semibold`; input and button classes retyped | Weight 450 with `-0.02em`/`-0.035em`; `INPUT_CLASS`, `PRIMARY_BUTTON_CLASS` |
| `components/inbox/EmailDetail.tsx` | Notice titles use `font-semibold` | `font-medium` |
| `app/inbox/page.tsx` | Menu uses `shadow-lg`; header buttons retype the primary class | Ink floating shadow; a shared 36px variant |
| `app/settings/payees/page.tsx` | Dialog uses `shadow-xl` | Ink floating shadow |
| `components/bills/ReviewActions.tsx` | Textarea focus uses an outline, unlike inputs; button classes retyped | `focus-visible:border-accent focus-visible:ring-2 focus-visible:ring-accent/20`; constants |
| Several files | Disabled opacity mixes `50` and `60` | `opacity-60` for buttons and inputs, `50` for text buttons |
