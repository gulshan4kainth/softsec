# RMAP Protocol – Tamarin Formal Analysis

## Protocol (Abstract Messages)

The abstract protocol messages modeled in `RMAP_TAMARIN.spthy` are:

1. M1: C→S: aenc( Pair(id, nc), pk(skS) )
2. M2: S→C: aenc( Pair(nc, ns), pk(sk(id)) )
3. M3: C→S: aenc( ns, pk(skS) )
4. Server issues secret: Secret(id,nc,ns)

These messages and the associated state facts produce the `Secret(...)` fact recorded by the server when the issuance completes.

(See `RMAP_TAMARIN.spthy` for exact formal statements.)

This document summarizes the concrete results from running the Tamarin prover on the theory `RMAP_TAMARIN.spthy`, together with quick interpretation and next steps.

## 1. Quick summary

- Command run (batch prove):

```bash
mkdir -p tamarin-output
tamarin-prover --prove RMAP_TAMARIN.spthy --output-json tamarin-output/traces.json --output-dot tamarin-output/traces.dot -v
```

- Supporting rendering command (Graphviz):

```bash
dot tamarin-output/traces.dot -Tpng -o tamarin-output/traces.png
```

- High-level results (Tamarin 1.10.0):
  - `types` — verified
  - `nonce_secrecy` — falsified (attack found)
  - `injective_agreement` — falsified (counterexample found)
  - `session_key_setup_possible` — verified

Artifacts created are placed in `tamarin-output/`.

## 2. Modeling & protocol (brief)

- Public-key crypto modeled `aenc/adec`.
- Fresh nonces `ni` (client) and `nr` (server). Secret link is modeled as an allocated `link` term and recorded via `Secret` facts.
- Protocol rules implement: client initial message (I_1), server response (R_1), client check & secret derivation (I_2..I_3), server finalization issuing `Secret` (R_2).

If you want the full theory, open `RMAP_TAMARIN.spthy` in the repository.


## 3. What the prover found

- types: verified — no type/shape issues in traces.

- nonce_secrecy: falsified — Tamarin found at least one trace where a `Secret(...)` fact exists and the adversary (`K(...)`) also knows the secret value. The run's internal logs show an explicit satisfying trace pattern like `Secret(A, B, s) @ #i` together with `K(s) @ #j` and no `RevLtk` events, meaning the leak occurs under the current rules without any explicit long-term key revelation steps.

- injective_agreement: falsified — Tamarin produced a counterexample trace showing that the same `Commit`/`ClientComplete` can be matched with multiple `ServerReply` events (non‑injective matching). The trace demonstrates an ordering of events that invalidates injectivity under current modeling.

- session_key_setup_possible: verified — a run exists showing a successful session and secret setup (i.e., the normal happy path is reachable).

Summary from the prover run (printed at end of tool output):
```
summary of summaries:

analyzed: /workspaces/codespaces-blank/RMAP_TAMARIN.spthy

  processing time: ~4s

  types (all-traces): verified
  nonce_secrecy (all-traces): falsified - found trace
  injective_agreement (all-traces): falsified - found trace
  session_key_setup_possible (exists-trace): verified
```

## 4. Where to see the counterexample traces

The prover export and rendered graph are available under `tamarin-output/` in the repo root (created by the run above):

- `tamarin-output/traces.json` — serialized traces and counterexample details (JSON). This contains the concrete trace steps, including rule names and event facts; you can extract a human-readable trace from it.
- `tamarin-output/traces.dot` — Graphviz dot export representing traces/graphs.
- `tamarin-output/traces.png` — PNG rendering of the dot export for quick visual inspection.
- `tamarin-output/index.html` — quick HTML summary page (if present) embedding `traces.png` and linking the raw artifacts.

To inspect the fail trace in human-readable form, you can open `traces.json` and search for the guard-formula or the lemma name (e.g. `nonce_secrecy`) to find the matching satisfying trace.

## 5. Quick interpretation & likely root causes

- nonce_secrecy falsified:
  - The run indicates there is a path in the model that exposes the `link` term to the adversary. Common root causes in models similar to RMAP are:
    - Some `Out(...)` message leaks the secret or the secret is encrypted under a key the adversary can learn (for instance, if PK publication or long-term key facts are modeled so the attacker can decrypt or the private key is leaked by other rules).
    - A rule may publish a value (e.g., using `Out`) without sufficient protection, or a derived term (pairing of nonces) may be re-used or exposed.
  - Next step: inspect the counterexample in `traces.json` to see exactly which rule produced the `Out` leading to `K(s)` and whether the leak comes from the server or client side.

- injective_agreement falsified:
  - Often caused by insufficient linking between session identifiers and event facts or by not preventing replayed/duplicated server replies.
  - Fix approach: strengthen state facts or add uniqueness conditions (e.g., record `UsedNonce` facts and require they are consumed) or ensure `Commit` facts carry a unique session identifier that prevents two different `ServerReply` events from matching the same completion.

## 6. Reproduction steps (exact)

Run from the repository root:

```bash
# 1) produce JSON and DOT traces
mkdir -p tamarin-output
tamarin-prover --prove RMAP_TAMARIN.spthy --output-json tamarin-output/traces.json --output-dot tamarin-output/traces.dot -v

# 2) (optional) render the graph image
dot tamarin-output/traces.dot -Tpng -o tamarin-output/traces.png
```

Open `tamarin-output/traces.json` and examine the counterexamples for `nonce_secrecy` and `injective_agreement`. You can also run the interactive UI for guided inspection:

```bash
tamarin-prover interactive RMAP_TAMARIN.spthy
# then open the URL printed by the prover in a browser
```

## 7. Artifacts added by the run

(Located at repo root in `tamarin-output/`)

- `traces.json` — JSON traces
- `traces.dot` — DOT export
- `traces.png` — PNG rendering (Graphviz)
- `index.html` — optional quick summary page
