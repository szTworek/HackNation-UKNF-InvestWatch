# Design

InvestWatch follows the visual language of knf.gov.pl, so it reads as a tool from the same institution. It does not use the KNF logo or name as its own brand.

## Tokens

| Role | Value |
|---|---|
| Text | `#2B303B` |
| Secondary text | `#5F6673` |
| Primary, brand, M1 | `#113B6F` |
| Links, active menu item, M2 | `#1E6AC8` |
| M3 | `#4B5F7C` |
| Suspected fraud, critical | `#C00417` on `#FDF0F1` |
| High risk | `#C2500A` |
| Medium risk | `#946200` |
| Soft surfaces | `#F9F9F9`, `#F3F4F6` |
| Borders | `#E5E7EB` |

## Type

Inter, self-hosted through `@fontsource/inter`, at 400 to 800. Page title 36px/700, section title 16px/700, menu 14px/600 uppercase. Numbers in tables use tabular figures.

## Shell

6px dark top line, white header (wordmark, search, tools), uppercase menu with module counts, new-records bar, breadcrumb, then the page in a 1440px container.

## Components

- Controls and sections are square, with 1px borders and no shadows.
- Section headers sit on `#F9F9F9`.
- Table headers have a dark 1px rule; rows are separated by light rules.
- Red appears only for suspected fraud, critical risk and errors.
- No side accent bars, gradients, eyebrows or decorative motion.

## Motion

Only state changes: 150ms colour transitions, a short highlight on new rows and the slow new-records bar. All of it respects `prefers-reduced-motion`.
