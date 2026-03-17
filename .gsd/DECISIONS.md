# Decisions Register

<!-- Append-only. Never edit or remove existing rows.
     To reverse a decision, add a new row that supersedes it.
     Read this file at the start of any planning or research phase. -->

| # | When | Scope | Decision | Choice | Rationale | Revisable? |
|---|------|-------|----------|--------|-----------|------------|
| D001 | M001 | scope | Market coverage focus | Vinted Homme and Femme categories plus all reachable sub-categories only | Keeps the first radar focused enough to cover deeply and compare contextually. | Yes — if a later milestone explicitly expands marketplace scope |
| D002 | M001 | arch | Data acquisition backbone | Public collection only, no login required, and no central dependency on undocumented private APIs | Matches access constraints and reduces fragility risk. | Yes — if an official supported data channel becomes available and complements public collection |
| D003 | M001 | pattern | Truth surface in product | Separate observed facts, inferred conclusions, and uncertain states everywhere that matters | Product credibility depends on making evidence and uncertainty explicit. | No |
| D004 | M001 | pattern | Primary product view | Mixed dashboard with market summary first and listing-level proof immediately underneath | The product must tell a market story and let the user verify it quickly. | No |
| D005 | M001 | operability | Local runtime modes | Support both batch mode and continuous mode in M001 | Batch supports testing and controlled reruns; continuous mode is required for a living radar. | No |
| D006 | M001 | data | Listing state model posture | Use a prudent state machine covering active, sold observed/probable, unavailable non-conclusive, deleted when distinct, and unknown | Avoids overclaiming from ambiguous public signals. | Yes — if live evidence later justifies tighter or broader state distinctions |
| D007 | M001 | data | Ranking split | Provide separate “demande pure” and “premium” rankings | These answer different market questions and should not collapse into one score. | No |
| D008 | M001 | pattern | Premium score weighting | Price acts as an intelligent contextual factor, not the dominant driver | The premium ranking should reward strong performance at relatively high price, not simply expensive listings. | No |
| D009 | M001 | arch | Milestone sequencing | Build listing-level credibility first, then richer market reading, then product-level intelligence plus AI, then SaaS hardening | Preserves the evidence backbone before richer analytics and commercialization. | Yes — if execution proves a different sequence is materially safer or faster |
