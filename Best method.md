Recommendation: Use gulshan as the default when “hard to remove” is the goal.

Why gulshan is hardest to strip:

Incremental update: Adds a real PDF object plus xref/trailer with Prev, so many viewers/editors keep it when re-saving.
Structural integration: Lives in the document’s revision chain, not just bytes after EOF.
Tamper detection: Binds to the pre-append content hash; changes typically break verification on read.
Why adam/psm are easier to remove:

adam: Strong cryptography (AEAD, doc-hash binding), but appended after EOF with no xref update; any “Save As/Optimize” that rewrites from the last valid xref will drop it.
psm: Simple marker+payload after EOF; trivial to truncate or lose on rewrite.
Trade-offs:

gulshan: Most removal-resistant; secret stored compressed but not encrypted.
adam: Best confidentiality + integrity, but structurally easiest to strip.
psm: Lightweight and simplest; weakest against removal.
Hardening tips (if you want even more resilience):

Reference the watermark object from the Catalog/Info (make it reachable) so “optimize/GC” won’t discard it.
Store metadata in an object stream and add multiple benign cross-references.
Pair structural watermark with a visible overlay to deter casual reauthoring.
Keep using incremental updates (don’t rewrite the whole file) to preserve the chain.
If acceptable, add an out-of-band verification step (server-side expected hash) to detect removal during validation.