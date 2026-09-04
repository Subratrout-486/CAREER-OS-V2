# ARACHNE — DESIGN.md

Original design system for the Career OS control plane (ARACHNE). This is an
original language — inspired by, but never copying, any external brand. It
combines a **spider-web / network** visual identity with a premium technical
aesthetic and purposeful motion.

A coding agent reading this file should produce UI that is visually consistent
with the ARACHNE language.

## Identity

- **Concept** — ARACHNE is the spider at the center of your career web. The
  operating metaphor is a *living network*: your full candidate truth sits at
  the center, job opportunities and companies connected to it, outcomes verified
  as strong links.
- **Voice** — calm, precise, operative. No playful copy. Technical but not
  ossified. Think mission control, not marketing site.
- **Never** copy another company's branding, logos, or signature layouts.

## Color tokens

Dark, warm-on-cool command center:

| Token              | Hex       | Use                                            |
| ------------------ | --------- | ---------------------------------------------- |
| `--bg`             | `#07090d` | App background                                |
| `--bg2`            | `#0b0e14` | Secondary background / sidebar                 |
| `--panel`          | `#10151d` | Card base                                     |
| `--panel2`         | `#141b26` | Card hover / raised panel                      |
| `--line`           | `#1e2836` | Hairline borders                              |
| `--line2`          | `#2a3648` | Stronger borders                              |
| `--text`           | `#eaf0f6` | Primary text                                  |
| `--muted`          | `#8b98a8` | Secondary text                                |
| `--faint`          | `#5b6a7d` | Tertiary text / captions                      |
| `--accent`         | `#f2a33c` | Primary action (amber)                         |
| `--accent2`        | `#ffd27a` | Accent highlight                              |
| `--ok`             | `#3ddc84` | Verified / success                            |
| `--warn`           | `#ffbd4a` | Attention / review needed                      |
| `--danger`         | `#ff6b7a` | Failed / blocked                              |
| `--info`           | `#5aa7ff` | In-flight / discovery                          |

Use accent colors sparingly and semantically (approx. ≤12% of any surface).

## Typography

- Sans: `Inter, ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto`.
- Mono: `'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, monospace` —
  reserved for timestamps, IDs, evidence, and status values.
- Type scale: view title 26px/750/-0.03em → section heading 13px uppercase
  700 tracking 0.02em → body 14–15px → caption 11–12px muted.
- Numeric emphasis (metrics, scores, fit) must be tabular-weight 800.

## Motion language

Motion communicates pipeline progression and network liveliness, never
decoration:

- **Pipeline wave** — completed connectors carry a traveling light pulse
  (`wire`), expressing DISCOVERED → ANALYZED → MATCHED → TAILORED → REVIEWED →
  APPROVED → EXECUTING → VERIFIED.
- **Active node glow** — the current stage node breathes (1.6s) with a soft
  amber halo.
- **Candidate pulse ring** — the center node emits a faint expanding ring to
  show the network is alive.
- **Loading shimmer** — skeleton surfaces use a 1.4s sheen sweep.
- Respect `prefers-reduced-motion`: disable pulse/wave/glow when set.

## Layout & hierarchy

- Sidebar (248px) + main content; mobile collapses to a compact rail.
- Grid: 4 → 3 → 2 → 1 column as viewport shrinks (k4/k3/k2 classes).
- One primary action per view; secondary actions quiet (outlined, hover-to-amber).
- Information hierarchy: headline metrics first, then live pipeline, then list
  rows, then deep detail on drill-in views.

## Components

- **Card** — `panel2→panel` gradient, 1px `line` border, 14px radius, soft
  shadow. Headings uppercase-muted.
- **Pill** — rounded status badge; semantic colors (ok/warn/danger/info/gold/
  muted). Never style a pill as a button.
- **Stage** — circular node + label; states: pending (hollow), done (filled ok),
  active (amber glow), fail (danger).
- **Job row** — 40px icon square (first letter, semantic fill), title, sub-meta,
  optional fit score, status pill. Hover raises to `panel2`.
- **Empty state** — centered: big primary line, muted explanation, one clear
  next action.
- **Graph** — candidate at center, jobs/companies/outcomes on concentric rings;
  edges color-coded (verified = ok green, pending = amber). Labels ≤18 chars.

## Accessibility

- Contrast: `--muted` on `--bg` passes AA; never rely on color alone — pair
  status colors with labels or icons.
- Animations honour `prefers-reduced-motion`.
- Targets ≥ 36px touch; focus-visible states on interactive rows/buttons.
- All controls reachable by keyboard; rows expose keyboard activation.

## Spacing & radius

- Base unit 4px. Card padding 18–24px, row padding 12–14px, grid gap 14px.
- Radii: cards 14px, controls 10px, pills 999px, icons 8–11px.