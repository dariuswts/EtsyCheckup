# WF1 EverBee Global Consolidation v2 Prompt Preview

You are consolidating accepted WF1 grouped EverBee direction candidates after bundle-level live review.

Use only accepted candidate rows and their evidence lineage. Do not invent new query groups, directions, evidence IDs, products, shops, metrics, or claims. Merge near-duplicate directions only when their sanitized direction language and evidence support clearly describe the same reusable market direction.

Return strict JSON matching schema `wf1_everbee_global_consolidation_v2`. Accepted directions must preserve source query group IDs, source bundle IDs, supporting evidence IDs, risk flags, and human review notes. Held directions must include a clear hold reason. Do not create WF2 product concepts, designs, listing copy, scores, or winners.
