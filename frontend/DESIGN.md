# Stripe — Style Reference
> cobalt-ink ledger on warm paper

**Theme:** light

Source measurements are normalized; roles and recommendations are interpreted. Font summary lists are independent, not paired by position. HTML examples are reconstructions, not source components.

**Palette source:** every color below is Blinka's own, read from the live stylesheet of [blinka.co](https://blinka.co/) (`/assets/main-CqMgimik.css`, October 17, 2026). The layout, type and component rules keep the Stripe reference; only the colors were replaced. Where a value is a `--launch-*` variable or appears in a named selector, the "Observed in" column says so.

Stripe uses a near-monochrome financial-instrument language: a warm paper canvas (#f7f7f4) with deep ink headings, almost no decorative chrome, and one vivid cobalt (#2a4bd0) that earns the right to be a button, link, or icon stroke. Typography is exclusively sohne-var at weight 300 — even at 56px display size — which reads as confident restraint rather than corporate shouting; letter-spacing tightens aggressively as size grows. Buttons are small, squared at 4px, and use cobalt fills or hairline outlines. The system avoids shadows entirely; depth comes from background tint shifts (paper → white → #f0f2f4 → cobalt washes) rather than elevation. The whole interface behaves like a ledger or terminal: dense information, crisp rules, generous whitespace between sections, and color appearing only when something needs to be acted on.

## Tokens — Colors

| Name | Value | Token | Observed in | Role |
|------|-------|-------|-------------|------|
| Cobalt | `#2a4bd0` | `--color-cobalt` | `--launch-accent` | Action color for filled buttons, selected navigation states, focus outlines, and focused conversion moments. |
| Cobalt Hover | `#2342bd` | `--color-cobalt-hover` | `.launch-primary:hover` | Hover background for every cobalt button. Hover darkens; it never lightens. |
| Ink | `#1c253a` | `--color-ink` | `--launch-ink` | Primary heading and body text — deep navy that anchors the entire type system; also the ink button fill |
| Ink Hover | `#334360` | `--color-ink-hover` | `.launch-button:hover` | Hover background for ink buttons |
| Muted | `#656975` | `--color-muted` | `--launch-muted` | Gray text for labels, tags, captions, and short supporting phrases. |
| Nav Ink | `#505563` | `--color-nav-ink` | `.launch-nav-links` | Tertiary body text, helper copy, and navigation links |
| Quiet | `#929ba8` | `--color-quiet` | `.payment-route-currencies` | Muted text for large decorative numerals and secondary codes — never for body paragraphs |
| Paper | `#f7f7f4` | `--color-paper` | `--launch-paper` | Page canvas; the warm default background against which everything else is measured |
| White | `#ffffff` | `--color-white` | buttons, sheets | Elevated surfaces on paper: cards, navigation bar, inputs, footer band |
| Sheet | `#fdfdfd` | `--color-sheet` | `.pg-card-receipt`, `.ts-transfer` | Receipts and floating product sheets |
| Sunken | `#f0f2f4` | `--color-sunken` | `.ts-fund-choice` | Unselected choices, neutral tags, quiet section bands |
| Sunken Hover | `#e9ecf2` | `--color-sunken-hover` | `.ts-fund-choice:hover` | Hover background on sunken choices and quiet buttons |
| Line | `#dedfdc` | `--color-line` | `--launch-line` | Primary border and divider color; the workhorse neutral that divides content |
| Selection | `#dce2ef` | `--color-selection` | `::selection` | Hairline outline button border (1px) — the cobalt-tinted companion to cobalt fills |
| Soft Edge | `#e0e6f0` | `--color-soft-edge` | `.pg-activity-received` | Secondary outline button border and softer cobalt-tinted dividers |
| Cobalt Wash | `#f3f5fd` | `--color-cobalt-wash` | `.ts-fund-choice[aria-pressed=true]` | Lightest cobalt surface — selected choices, highlighted cards, tag pills, emphasis blocks |
| Icon Wash | `#e9edf9` | `--color-icon-wash` | `.pg-activity-received .pg-activity-icon` | Tile behind a cobalt icon in a highlighted row |
| Route Wash | `#2a4bd00c` | `--color-route-wash` | `.payment-destination[aria-pressed=true]` | Active row in a dense list (cobalt at 4.7%) |
| Link Underline | `#bdc0c7` | `--color-link-underline` | `.launch-legal-row a` | 1px underline of inline links before hover |
| Night | `#111720` | `--color-night` | `.launch-footer`, dark header | Heaviest accent — emphasized borders, dark sections, and blocked states; reads almost as black-navy |
| Night Ink | `#e9edf1` | `--color-night-ink` | `.launch-footer` | Text on night |
| Night Muted | `#b2bbc7` | `--color-night-muted` | `.launch-footer` | Supporting text on night |
| Night Line | `#b9c7da2b` | `--color-night-line` | dark header, footer | Dividers on night |
| Dark Focus | `#b9c8ff` | `--color-dark-focus` | `a:focus-visible` on dark | Focus outline on any dark or cobalt surface |
| Completed | `#007456` | `--color-completed` | `.pg-receipt-heading` | The single green on the site: the "Completed" text of a payment receipt. Text only, never a fill |

## Tokens — Typography

### sohne-var — Sole type family across the entire interface — headings, body, navigation, buttons, and labels. Weight 300 dominates even at 56px display size, which is the signature: headlines whisper instead of shout, earning authority through restraint rather than volume. Weight 400 appears only at 14–16px for navigation and button text where small-size readability needs the extra stroke. · `--font-sohne-var`
- **Substitute:** Inter Tight (variable, weight 300/400) or a similar humanist sans with tall x-height
- **Weights:** 300, 400
- **Sizes:** 12, 14, 16, 18, 20, 22, 26, 32, 48, 56
- **Line height:** 1.00, 1.03, 1.10, 1.12, 1.20, 1.40, 1.45
- **Letter spacing:** -0.0100em at 26px and below; -0.0200em at 32–48px; -0.0250em at 56px; -0.0300em reserved for the largest display sizes — tracking tightens aggressively as type grows, creating the characteristic 'pulled-in' feel of Stripe's headlines
- **OpenType features:** `"ss01" on, "tnum" on`
- **Role:** Sole type family across the entire interface — headings, body, navigation, buttons, and labels. Weight 300 dominates even at 56px display size, which is the signature: headlines whisper instead of shout, earning authority through restraint rather than volume. Weight 400 appears only at 14–16px for navigation and button text where small-size readability needs the extra stroke.

### Type Scale

| Role | Family | Weight | Size | Line Height | Letter Spacing | Token |
|------|--------|--------|------|-------------|----------------|-------|
| caption | — | — | 12px | 1.45 | -0.12px | `--text-caption` |
| body-sm | — | — | 14px | 1.4 | -0.14px | `--text-body-sm` |
| body | — | — | 16px | 1.2 | -0.16px | `--text-body` |
| body-lg | — | — | 20px | 1.4 | -0.2px | `--text-body-lg` |
| subheading | — | — | 22px | 1.1 | -0.22px | `--text-subheading` |
| heading-sm | — | — | 26px | 1.12 | -0.26px | `--text-heading-sm` |
| heading | — | — | 32px | 1.1 | -0.64px | `--text-heading` |
| heading-lg | — | — | 48px | 1.03 | -0.96px | `--text-heading-lg` |
| display | — | — | 56px | 1.03 | -1.4px | `--text-display` |

## Tokens — Spacing & Shapes

**Base unit:** 8px

**Density:** comfortable

### Spacing Scale

| Name | Value | Token |
|------|-------|-------|
| 8 | 8px | `--spacing-8` |
| 16 | 16px | `--spacing-16` |
| 24 | 24px | `--spacing-24` |
| 32 | 32px | `--spacing-32` |
| 40 | 40px | `--spacing-40` |
| 48 | 48px | `--spacing-48` |
| 64 | 64px | `--spacing-64` |
| 80 | 80px | `--spacing-80` |
| 96 | 96px | `--spacing-96` |

### Border Radius

| Element | Value |
|---------|-------|
| tags | 9999px |
| cards | 4px |
| inputs | 4px |
| buttons | 4px |

### Layout

- **Page max-width:** 1320px
- **Section gap:** 96px
- **Card padding:** 32px
- **Element gap:** 8px

## Components

### Primary Filled Button
**Role:** Main conversion action — 'Empieza ahora', 'Contacta con ventas'

Background #2a4bd0, white text (#ffffff), 4px radius, padding 15.5px 24px (vertical slightly asymmetric due to optical alignment). Typography: sohne-var weight 400 at 14px. On hover, darkens to #2342bd. No shadow. The 4px radius — not pill, not square — is a deliberate middle ground that reads as professional rather than friendly.

### Ghost Outline Button
**Role:** Secondary action paired with a filled CTA — 'Accede con tu cuenta de Google'

Transparent background, cobalt text (#2a4bd0), 1px border in #dce2ef (selection), 4px radius, padding 14.5px 24px. Same typographic spec as the filled button (sohne-var 400 at 14px). The border is intentionally lighter than the text — the text is the loud element, the border whispers. Hover fills with #f3f5fd.

### Tertiary Outline Button
**Role:** Low-emphasis action — 'Conoce su historia', link-style buttons

Transparent background, cobalt text, 1px border in #e0e6f0 (soft edge, paler than selection), 4px radius, smaller padding. Used when a button is needed but shouldn't compete with the primary action above it.

### Text Link Button
**Role:** Inline action with chevron — 'Empieza ahora ›' inside body copy

No border, no background. Text in #2a4bd0 with a trailing chevron character. Typography: sohne-var weight 400 at 16px, inheriting body line-height. Often paired with a brief description above it. The chevron is part of the visual identity — directional without being aggressive.

### Underline Link
**Role:** In-paragraph links and editorial references

Text in #2a4bd0 with a 1px underline in the same color. No border, no background. Used for inline references within body copy where the chevron pattern would feel too heavy. Legal and footer links use ink text with a #bdc0c7 underline that turns to the current color on hover.

### Section Heading Block
**Role:** Major section title with supporting paragraph — appears at top of each product section

Display-size heading (48–56px sohne-var weight 300, #1c253a, letter-spacing -0.96 to -1.40px) on one or two lines, followed by a muted (#656975) supporting paragraph at 22–26px weight 300. Generous vertical gap (32–48px) between heading and paragraph. This is the 'Stripe statement' pattern — confident headline, quiet explanation.

### Product Feature Card
**Role:** Card describing a Stripe product capability (Payments, Billing, Connect, etc.)

Paper (#f7f7f4) or white (#ffffff) surface, no shadow, no visible border by default. Content: small muted label or tag at top, then heading-sm (32px weight 300 #1c253a), then body paragraph. Generous internal padding (~32px). Cards are distinguished only by layout and whitespace, never by chrome.

### Customer Logo Rail
**Role:** Social proof — vertical stack of customer brand logos (Amazon, Ford, Coinbase, Google, Mindbody, etc.)

Logos rendered at their native brand colors on the paper background, vertically stacked with consistent spacing. Logos retain their original palette — the rail itself uses no Stripe chrome. Functions as a 'who trusts us' signal without visual competition with surrounding content.

### Navigation Bar
**Role:** Top-level site navigation

Paper or white background, hairline #dedfdc bottom border (1px). Wordmark on left in #1c253a. Menu items (Productos, Soluciones, Desarrolladores, Recursos, Tarifas) in sohne-var weight 400 at 14px, #505563, with 8px gap between items. Right side: ghost outline 'Inicia sesión' link and filled primary 'Contacta con ventas' button. Fixed height ~76px.

### Metric/Stat Block
**Role:** Displaying large numbers — '50%', '1.4T$', etc.

Number rendered at display size (48–56px sohne-var weight 300 #1c253a, tight letter-spacing) with a muted (#656975) label below it at body size. No card, no border — the number itself carries the visual weight. The combination of whisper-weight type and enormous size creates a distinctive 'quiet monument' effect.

### Hero CTA Pair
**Role:** Primary + secondary action group at the top of the page

Filled primary button ('Empieza ahora') directly followed by ghost outline button ('Accede con tu cuenta de Google') with 8px gap. Both at the same height (14px text, ~48px total). The ghost button features a small Google 'G' icon before its text — a rare instance of an inline icon in a button.

### Section Divider
**Role:** Horizontal rule between major page sections

A 1px solid line in #dedfdc spanning the full content width. No decorative elements — just a quiet horizontal rule that resets the page rhythm. This is the primary structural element of the layout; there are no shadows, no background shifts between sections.

## Do's and Don'ts

### Do
- Use #2a4bd0 exclusively for primary actions, active links, and icon strokes — never for body text, backgrounds spanning large areas, or decorative elements
- Set all headings and body text to sohne-var weight 300 — the whisper-weight is the signature; do not use weight 600 or 700 anywhere except the Stripe wordmark
- Tighten letter-spacing as type size grows: -0.0100em up to 26px, -0.0200em at 32–48px, -0.0250em at 56px, -0.0300em above 56px
- Apply font-feature-settings: 'ss01' on, 'tnum' on to all text — tabular numerals are essential for the metric/stat blocks and pricing displays
- Use 4px border-radius on all buttons, inputs, and cards — never 0px (too sharp), never pill (too friendly), never 8px+ (too soft)
- Separate sections with 1px #dedfdc horizontal rules and 96px vertical gaps — do not use background color shifts, shadows, or card containers to divide content
- Pair each filled primary button with a ghost outline button (#dce2ef border) as its secondary action — never present a filled button alone
- Use #b9c8ff for focus outlines on night or cobalt surfaces, and #2a4bd0 everywhere else

### Don't
- Do not use shadows, blurs, or any form of CSS elevation on cards, buttons, or images — depth comes from background tint, never from box-shadow
- Do not introduce additional accent colors — the system is monochromatic plus one cobalt; adding greens, oranges, or pinks breaks the ledger aesthetic. The only exception is #007456, as text, for a completed payment
- Do not use semibold or bold weights for headings — weight 300 at display size is the entire typographic identity
- Do not use rounded corners beyond 4px — pill buttons, large radii, or fully circular elements break the precision-tool feel
- Do not fill large areas with #2a4bd0 — the cobalt should appear in small functional doses (buttons, links, icon strokes); large cobalt backgrounds belong only to feature cards designed for contrast
- Do not center body copy or headings — Stripe text blocks are always left-aligned within their column; centering is reserved for logo marks and a few isolated stat displays
- Do not use #656975 or #505563 for anything longer than a sentence — these are muted text colors for labels and captions, not for paragraphs
- Do not use pure white (#ffffff) as the page canvas — the canvas is paper (#f7f7f4); white is a raised surface

## Surfaces

| Level | Name | Value | Purpose |
|-------|------|-------|---------|
| 0 | Paper | `#f7f7f4` | Primary page background for hero and most content sections |
| 1 | White | `#ffffff` | Navigation bar, cards, inputs, and the footer band; a quiet lift off the paper |
| 2 | Sunken | `#f0f2f4` | Unselected choices, neutral tags, hover backgrounds (#e9ecf2 on hover); creates depth without shadow |
| 3 | Cobalt Wash | `#f3f5fd` | Tinted surface for selected choices, highlighted content blocks and emphasized cards |
| 4 | Cobalt Surface | `#2a4bd0` | Brand accent surface for feature cards or dramatic highlight panels |
| — | Night | `#111720` | Dark sections and footer on the marketing site, with #e9edf1 text and #b2bbc7 supporting text |

## Elevation

Stripe avoids shadows entirely. Depth and hierarchy are created through background tint progression (#f7f7f4 → #ffffff → #f0f2f4 → #f3f5fd → #2a4bd0), hairline 1px dividers in #dedfdc, and generous whitespace. No card has a box-shadow. No button has a shadow on any state. This flatness is deliberate — it reads as financial instrument rather than consumer app.

## Imagery

Imagery is restrained and documentary-style. Full-bleed photographs appear only in editorial case-study sections (e.g., aerial traffic photography for Hertz), shot from above or at a dramatic angle with natural color — no duotone or color treatment. Product UI screenshots are used inside feature cards, rendered with sharp corners and 1px borders, no device frames. Logo rails show partner brands in their native colors without any wrapping container. There are no illustrations, no 3D renders, no decorative abstract graphics. Icons are uniform: 1.5px stroke weight, #2a4bd0 stroke on paper or white, geometric line-art style (chevrons, arrows, checkmarks, document marks). The page is predominantly text-and-whitespace; images occupy less than 15% of total visual area.

## Layout

Max-width ~1320px centered content column on the paper canvas. Hero is a left-aligned text block at full display size (56px) with two CTAs below, no hero image — the typography IS the hero. Sections are stacked vertically with consistent 96px gaps and 1px #dedfdc dividers; no alternating dark/light bands. Each section follows a repeating pattern: small uppercase section label (muted color, 12px), then a 32–48px heading, then a 22px muted paragraph, then a grid of product cards (3-column at desktop) or a 2-column text-plus-visual block. Customer logos appear in a narrow left-aligned vertical rail. Footer is a single wide white band with multi-column link lists. The overall rhythm is slow, deliberate, and text-dominant — information density is low despite long scroll length.

## Agent Prompt Guide

## Quick Color Reference
- Text primary: #1c253a
- Text secondary: #656975
- Text muted: #505563
- Background canvas: #f7f7f4
- Raised surface / band: #ffffff
- Border / divider: #dedfdc
- Accent / link / icon stroke: #2a4bd0
- Hover accent: #2342bd
- Ghost button border: #dce2ef
- Selected / highlighted surface: #f3f5fd
- primary action: #2a4bd0 (filled action)

## Example Component Prompts

1. Create a Primary Action Button: #2a4bd0 background, #ffffff text, 9999px radius, compact pill padding. Use this filled treatment for the main CTA.

2. **Product feature card grid**: Paper (#f7f7f4) cards on the paper canvas, no shadow, no border. Each card: 32px padding, 8px gap between label and heading. Label at 12px sohne-var weight 300 in #929ba8. Heading at 32px weight 300 in #1c253a, letter-spacing -0.64px. Body at 16px weight 400 in #505563, line-height 1.40. 3-column grid with 24px column gap. Separate cards by whitespace alone — no visible borders.

3. **Section heading + stat block**: 96px top padding. Section label at 12px sohne-var weight 300 in #656975, text-transform uppercase, letter-spacing 0.5px. Heading at 48px weight 300 in #1c253a, letter-spacing -0.96px. Below: a large stat — number at 56px weight 300 in #1c253a, with a muted (#656975) 18px label below it. 32px gap between heading and stat.

4. **Ghost outline button**: Transparent background. Text at 14px sohne-var weight 400 in #2a4bd0. 1px solid border in #dce2ef. 4px border-radius. Padding: 14.5px top, 24px left/right, 15.5px bottom. No shadow. Optional inline icon at 16px to the left of text, rendered as 1.5px stroke #2a4bd0 line-art.

5. **Section divider**: 1px solid horizontal line in #dedfdc, spanning the full content width (max 1320px), centered. 96px vertical space above and below.

## Similar Brands

- **Linear** — Same sohne-var weight 300 headline approach, same tight letter-spacing at large sizes, same single-accent-color-on-monochrome discipline, same avoidance of shadows
- **Vercel** — Same whisper-weight display headlines, same minimal-chrome card design, same restraint with color — but Vercel uses black instead of cobalt as the accent
- **Notion** — Same left-aligned text-led layout with generous section gaps and 1px hairline dividers instead of shadows or card containers
- **Figma** — Same monochromatic base with one vivid accent for actions and icons, same hairline borders, same flat-surface philosophy
- **Arc browser** — Same playful-but-precise typographic voice at weight 300, same trust in whitespace rather than chrome

## Quick Start

### CSS Custom Properties

```css
:root {
  /* Colors (from blinka.co) */
  --color-cobalt: #2a4bd0;
  --color-cobalt-hover: #2342bd;
  --color-ink: #1c253a;
  --color-ink-hover: #334360;
  --color-muted: #656975;
  --color-nav-ink: #505563;
  --color-quiet: #929ba8;
  --color-paper: #f7f7f4;
  --color-white: #ffffff;
  --color-sheet: #fdfdfd;
  --color-sunken: #f0f2f4;
  --color-sunken-hover: #e9ecf2;
  --color-line: #dedfdc;
  --color-selection: #dce2ef;
  --color-soft-edge: #e0e6f0;
  --color-cobalt-wash: #f3f5fd;
  --color-icon-wash: #e9edf9;
  --color-route-wash: #2a4bd00c;
  --color-link-underline: #bdc0c7;
  --color-night: #111720;
  --color-night-ink: #e9edf1;
  --color-night-muted: #b2bbc7;
  --color-night-line: #b9c7da2b;
  --color-dark-focus: #b9c8ff;
  --color-completed: #007456;

  /* Typography — Font Families */
  --font-sohne-var: 'sohne-var', ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;

  /* Typography — Scale */
  --text-caption: 12px;
  --leading-caption: 1.45;
  --tracking-caption: -0.12px;
  --text-body-sm: 14px;
  --leading-body-sm: 1.4;
  --tracking-body-sm: -0.14px;
  --text-body: 16px;
  --leading-body: 1.2;
  --tracking-body: -0.16px;
  --text-body-lg: 20px;
  --leading-body-lg: 1.4;
  --tracking-body-lg: -0.2px;
  --text-subheading: 22px;
  --leading-subheading: 1.1;
  --tracking-subheading: -0.22px;
  --text-heading-sm: 26px;
  --leading-heading-sm: 1.12;
  --tracking-heading-sm: -0.26px;
  --text-heading: 32px;
  --leading-heading: 1.1;
  --tracking-heading: -0.64px;
  --text-heading-lg: 48px;
  --leading-heading-lg: 1.03;
  --tracking-heading-lg: -0.96px;
  --text-display: 56px;
  --leading-display: 1.03;
  --tracking-display: -1.4px;

  /* Typography — Weights */
  --font-weight-light: 300;
  --font-weight-regular: 400;

  /* Spacing */
  --spacing-unit: 8px;
  --spacing-8: 8px;
  --spacing-16: 16px;
  --spacing-24: 24px;
  --spacing-32: 32px;
  --spacing-40: 40px;
  --spacing-48: 48px;
  --spacing-64: 64px;
  --spacing-80: 80px;
  --spacing-96: 96px;

  /* Layout */
  --page-max-width: 1320px;
  --section-gap: 96px;
  --card-padding: 32px;
  --element-gap: 8px;

  /* Border Radius */
  --radius-md: 4px;

  /* Named Radii */
  --radius-tags: 9999px;
  --radius-cards: 4px;
  --radius-inputs: 4px;
  --radius-buttons: 4px;

  /* Surfaces */
  --surface-paper: #f7f7f4;
  --surface-white: #ffffff;
  --surface-sunken: #f0f2f4;
  --surface-cobalt-wash: #f3f5fd;
  --surface-cobalt: #2a4bd0;
  --surface-night: #111720;
}
```

### Tailwind v4

```css
@theme {
  /* Colors (from blinka.co) */
  --color-cobalt: #2a4bd0;
  --color-cobalt-hover: #2342bd;
  --color-ink: #1c253a;
  --color-ink-hover: #334360;
  --color-muted: #656975;
  --color-nav-ink: #505563;
  --color-quiet: #929ba8;
  --color-paper: #f7f7f4;
  --color-white: #ffffff;
  --color-sheet: #fdfdfd;
  --color-sunken: #f0f2f4;
  --color-sunken-hover: #e9ecf2;
  --color-line: #dedfdc;
  --color-selection: #dce2ef;
  --color-soft-edge: #e0e6f0;
  --color-cobalt-wash: #f3f5fd;
  --color-icon-wash: #e9edf9;
  --color-route-wash: #2a4bd00c;
  --color-link-underline: #bdc0c7;
  --color-night: #111720;
  --color-night-ink: #e9edf1;
  --color-night-muted: #b2bbc7;
  --color-night-line: #b9c7da2b;
  --color-dark-focus: #b9c8ff;
  --color-completed: #007456;

  /* Typography */
  --font-sohne-var: 'sohne-var', ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;

  /* Typography — Scale */
  --text-caption: 12px;
  --leading-caption: 1.45;
  --tracking-caption: -0.12px;
  --text-body-sm: 14px;
  --leading-body-sm: 1.4;
  --tracking-body-sm: -0.14px;
  --text-body: 16px;
  --leading-body: 1.2;
  --tracking-body: -0.16px;
  --text-body-lg: 20px;
  --leading-body-lg: 1.4;
  --tracking-body-lg: -0.2px;
  --text-subheading: 22px;
  --leading-subheading: 1.1;
  --tracking-subheading: -0.22px;
  --text-heading-sm: 26px;
  --leading-heading-sm: 1.12;
  --tracking-heading-sm: -0.26px;
  --text-heading: 32px;
  --leading-heading: 1.1;
  --tracking-heading: -0.64px;
  --text-heading-lg: 48px;
  --leading-heading-lg: 1.03;
  --tracking-heading-lg: -0.96px;
  --text-display: 56px;
  --leading-display: 1.03;
  --tracking-display: -1.4px;

  /* Spacing */
  --spacing-8: 8px;
  --spacing-16: 16px;
  --spacing-24: 24px;
  --spacing-32: 32px;
  --spacing-40: 40px;
  --spacing-48: 48px;
  --spacing-64: 64px;
  --spacing-80: 80px;
  --spacing-96: 96px;

  /* Border Radius */
  --radius-md: 4px;
}
```
