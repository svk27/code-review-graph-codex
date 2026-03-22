---
name: code-review-graph-review-delta
description: Review only the current working delta with code-review-graph context. Refresh the graph first, then produce a findings-first review focused on changed code and blast radius.
---

# Code Review Graph Review Delta

1. Refresh the graph first with `build_or_update_graph_tool()`.
2. Call `get_review_context_tool()` to gather changed files, impacted nodes, snippets, and review guidance.
3. Use `query_graph_tool` for targeted follow-up checks such as `tests_for`, `callers_of`, or `inheritors_of` when risk is unclear.
4. Produce a findings-first review: bugs and regressions first, then missing tests, then a brief risk summary.
5. Fall back to direct file reads only for gaps the graph cannot cover.
