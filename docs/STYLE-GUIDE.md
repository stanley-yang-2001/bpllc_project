# Web app style guide

What the web app looks like and why. The source of truth is the code: tokens in `web/src/index.css`,
shared components in `web/src/components/ui.tsx`. If this file and the code disagree, the code wins; fix this file.

## In one paragraph
Calm and quiet, so the learner's own words are the main thing on screen. One indigo brand colour, a warm amber used
only for small "coming soon" tags, slate greys for everything else, white cards on a pale grey page, generous spacing,
and Inter for text. Icons are thin line icons that always sit next to a word. Nothing animates except small hover
transitions and loading spinners. There is a matching dark theme.

## Palette
Defined once as tokens (`@theme` in `index.css`); components use the names, never raw hex values.

| Role | Token / Tailwind | Value | Used for |
|---|---|---|---|
| Brand | `brand-600` | `#4f46e5` | primary buttons, links, logo mark, active tab |
| Brand hover / pressed | `brand-700`, `brand-800` | `#4338ca`, `#3730a3` | button states |
| Brand tint | `brand-50`, `brand-100`, `brand-200` | `#eef2ff`, `#e0e7ff`, `#c7d2fe` | active nav pill, selection bar, avatar, info notice |
| Accent | `accent-100`, `accent-800` | `#fef3c7`, `#92400e` | "Soon" / "Planned" badges only |
| Page | `slate-50` | `#f8fafc` | page background |
| Surface | `white` | | cards, inputs, header (85% opaque with blur) |
| Text | `slate-900` / `slate-600` / `slate-500` | | headings and body / descriptions / hints and placeholders |
| Borders | `slate-200` (default), `slate-100` (row dividers), `slate-300` (inputs) | | |
| Success / warning / error | `emerald`, `amber`, `red` | | notices, status dots, danger button |

Tailwind v4 draws borders in `currentColor` (black) by default. `index.css` sets the default border colour to `slate-200`;
do not remove that rule.

**Measured contrast (WCAG, text needs 4.5:1, graphics 3:1):** body text 17.1, descriptions 7.6, hints and
placeholders 4.8, white on brand button 6.3, white on red button 4.8, brand text on brand tint 7.1, "Soon" badge 6.4,
error text 6.5. Light grey icons (`slate-400`, 2.6) failed and were changed to `slate-500`; the only `slate-400`
left is the text of a *disabled* button, which WCAG exempts.

## Typography
- **Inter Variable**, self-hosted through `@fontsource-variable/inter` (bundled by Vite, so it works offline and under the
  strict CSP). Fallback: the system UI font stack. Only the character ranges a page uses are downloaded.
- Page title `text-2xl font-semibold tracking-tight`; card title `font-semibold`; body and controls `text-sm` (14 px);
  hints `text-xs text-slate-500`; table headers `text-xs font-semibold uppercase tracking-wide text-slate-500`.
- Big numbers on the home page: `text-4xl font-semibold tracking-tight`.

## Shape, spacing, layout
- Cards `rounded-xl border shadow-xs p-5`; controls `rounded-lg`; badges and avatar `rounded-full`.
- Page content is centred, `max-w-5xl`, `px-4 py-8`; sections are separated by `mb-6`.
- **Header:** two rows at every width. Row 1: logo mark + name, language picker, avatar with name, log-out icon. Row 2:
  the navigation (icons at 640 px and up; scrolls sideways on phones). It sticks to the top with a translucent
  background. A one-row header only fitted by luck at some widths, so it was dropped.
- **Login:** two columns on large screens (brand panel on the left, form on the right); form only on small screens.

## Components (`components/ui.tsx`, `Toast.tsx`)
| Component | Notes |
|---|---|
| `Button` | variants `primary`, `secondary`, `danger`, `ghost`; `loading` shows a spinner and disables it; optional `icon`. A disabled danger button turns plain grey so it never looks like an active error. |
| `Card`, `PageHeader` | every page starts with `PageHeader` (title, one-line description, optional actions) |
| `Badge` | tones `neutral`, `brand`, `accent`, `good`, `bad` |
| `EmptyState` | icon, title, one sentence, optional action. Every list and page has one. |
| `Notice` | info / success / warning panel, e.g. the CSV upload result |
| `Skeleton`, `Spinner` | loading placeholders (skeleton rows for lists, spinner for button waits) |
| `ErrorText` | always inline next to what failed, `role="alert"` |
| `Modal`, `useConfirm()` | built on the browser's own `<dialog>`: focus is trapped and handed back to the opener, Escape and a click on the backdrop cancel. Destructive questions focus **Cancel** first. `useConfirm` replaced the browser's plain `confirm` box. |
| `Toast` | **success messages only** ("Added “water”"), bottom centre, 4.5 s, announced politely to screen readers. Errors are never toasts. Toasts are discarded when the user changes. |

Icons come from `lucide-react` (16 or 18 px, 1.5-2 px stroke), are inline SVG (no network, fine under the CSP), carry
`aria-hidden`, and sit beside a visible label. The only icon-only buttons (log out, show password) have an `aria-label`.

## Interaction and accessibility
- Keyboard focus: a 2 px brand outline on everything focusable; inputs use a brand ring instead.
- Hover and press states on every clickable element; transitions are short and are switched off for people who set
  "reduce motion".
- Every form control has a label (visible or `aria-label`); the tests find controls by those names, so renaming a label
  means updating its tests.
- Contrast checked as above. Colour is never the only signal (status dots come with text).

## Dark mode
Light, Dark or System (follow the device), chosen in Settings → Appearance, with a quick sun/moon switch in the header and
on the login page. The choice is a device setting kept in `localStorage` (`tutor:theme`), so it survives logout and is not
account data.

- **How it works:** a `dark` class on `<html>`. `public/theme-init.js` sets it *before the page paints* (a separate file,
  because the CSP forbids inline scripts), so there is no white flash; `ThemeProvider` then keeps it in step with the
  choice, the operating system and other tabs.
- **One remap, not hundreds of overrides:** every neutral in the app is a `slate-*` utility, so `.dark` in `index.css`
  re-points the slate scale and a new `surface` token (cards, inputs, header). Colours that play two roles (brand-700 is
  text in one place and a button background in another) carry explicit `dark:` classes instead.
- **Dark palette:** page `#020617`, card `#0f172a`, subtle fill/hover `#1e293b`, borders `#2a374d`, headings `#f8fafc`,
  descriptions `#cbd5e1`, hints `#94a3b8`. The login page's left panel is the same indigo gradient in both themes.
- **Measured contrast (dark):** body text on card 17.1, descriptions 12.0, hints 7.0 (5.7 on a hovered row), errors
  (`red-400`) 6.5, white on the brand button 6.3, white on the red button 4.8. All pass AA.
- **Verified in a browser:** an automated axe scan of every screen and dialog, in both themes, finds no WCAG 2 A/AA
  violations (`make e2e`). It did find two real light-theme problems when first run: muted grey text on tinted backgrounds
  (4.43 and 4.46 against the 4.5 minimum), now darkened.

## Not done (honest list)
- No illustrations or custom logo (the mark is an icon on a coloured square).
- Page text is English only; there is no translation layer for the interface itself.
- The login page shows one red "401" line in the browser console on every visit: it is the normal "who am I?" check
  answering "nobody". Harmless, but noisy for someone with devtools open.
- Single JavaScript bundle (about 430 kB, 133 kB compressed); no per-page splitting yet.
- Judged by eye on screenshots in one Chromium build at 1280 px and 390 px wide, in both themes. Not checked in Safari or Firefox. Automated accessibility scanning finds only part of the problems (screen-reader behaviour and keyboard flow beyond the dialogs were not tested by a person).
- Dark mode is only as good as the *pairs* tested; new components need `dark:` variants wherever they use brand or status colours.
