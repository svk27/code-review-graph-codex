---
name: code-review-graph-build-graph
description: Build or refresh the code-review-graph knowledge graph for this repository. Use when the graph may be missing or stale, or before graph-powered review workflows.
---

# Code Review Graph Build Graph

1. Call `list_graph_stats_tool` first.
2. If `last_updated` is null, call `build_or_update_graph_tool(full_rebuild=True)`.
3. Otherwise call `build_or_update_graph_tool()` for an incremental refresh.
4. Call `list_graph_stats_tool` again and report files, nodes, edges, languages, and any errors.
5. Mention `code-review-graph watch` when the user wants Codex-side automatic graph refreshes.
