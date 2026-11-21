# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Primary user: an analyst at UKNF (the Polish financial supervision office), not technical and not a data scientist. Every working day they open the app, go through a queue of newly detected social media materials and decide on each one: confirm, dismiss or escalate.

Secondary audience: the HackNation jury, who judge a live demo.

## Product Purpose

InvestWatch monitors Polish-language social media and web content about investing. AI modules classify it so analysts can act on what breaches the rules. Success means an analyst reaches a defensible decision on the most urgent material quickly, and can see why the system raised it.

## Positioning

One queue over three supervisory questions and a cross-cutting fraud path, with every signal traced back to the exact sentence, rule and legal basis. The system supports the analyst's decision and never makes it.

## Operating Context

- Module 1: ads of registered investment firms published by third parties, especially finfluencers. Report: firm, advertiser, content, URL.
- Module 2: firms' own marketing, checked against 18 risk-information rules.
- Module 3: entities outside the KNF register that in practice provide investment advice. Report: entity, offer, URL.
- Fraud: fake investment ads impersonating known firms and people, grouped into campaigns by shared phones, domains and channels. High fraud score always raises a critical alert.
- Demo moment that must land: a new high-risk alert arrives live and the analyst acts on it immediately.

## Capabilities and Constraints

- Vite, React 18, TypeScript, Mantine, Recharts, TanStack Query, HashRouter, socket.io-client, Cytoscape.js, dayjs. No CDN; everything works offline and on-premise.
- Interface in Polish. Technical keys never appear in the UI.
- Presentational components take props; pages fetch through hooks in `src/api`.
- Browser console stays clean. Dependencies are pinned.
- Data loads lazily: light list rows first, full record, graph, landing page and video only on demand.
- Required: filters by date, source, risk and module; status changes; CSV reports; real-time alerts; calibration panel where a threshold visibly changes false positives and false negatives.
- Keep the keyboard shortcuts and the new-records bar.

## Brand Commitments

- Name: InvestWatch.
- The user's binding direction: light, office-like colouring. It must be built around modules 1-3. It must not look like Excel, cyberpunk, a trading terminal or generic AI output, and must not have too much happening on screen.
- Careful language: "podejrzenie", "cechy oszustwa", never a verdict of fraud.

## Evidence on Hand

All current data comes from the mock server in `mock-server/` and is synthetic, with fictional firms, people, domains and phone numbers. No real entities, customers, benchmarks or accuracy figures may be invented.

## Product Principles

1. The next decision is always obvious.
2. Every flag shows its evidence.
3. Careful wording: the analyst decides, the system suggests.
4. Plain language for non-technical users; model detail only on request.
5. Calm until something is urgent, then unmistakable.
