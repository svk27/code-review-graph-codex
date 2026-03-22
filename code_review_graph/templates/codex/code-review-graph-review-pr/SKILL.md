---
name: code-review-graph-review-pr
description: Review a branch diff or PR with code-review-graph context. Refresh against the chosen base, inspect high-risk files first, and return a findings-first review.
---

# Code Review Graph Review PR

1. Choose the review base from the user request; otherwise prefer `main` and fall back to `master` if needed.
2. Refresh the graph with `build_or_update_graph_tool(base=<base>)`.
3. Call `get_review_context_tool(base=<base>)` and `get_impact_radius_tool(base=<base>)`.
4. Prioritize files and symbols with the widest blast radius, then use `query_graph_tool` for callers, tests, imports, and inheritance checks.
5. Produce a findings-first review with severity-ordered issues, missing tests, and a short overall risk summary.
