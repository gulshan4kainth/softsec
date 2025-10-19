# RMAP Protocol – Tamarin Formal Analysis

## 1. Scope & Objectives

We model the RMAP 3‑message handshake with an explicit encrypted link delivery step (M4). This flow produces a per‑recipient secret link (modeled as a fresh term) used later to fetch a personalized watermarked PDF. We aim to analyze:

1. Confidentiality of the issued secret link term (no attacker knowledge).
2. Mutual authentication (basic agreement) between Client and Server over nonces and identity.
3. Injective agreement (uniqueness of the Server’s reply per completed Client session).

Out‑of‑scope in this first model: watermark embedding, database side‑effects, passphrase handling, key revocation, replay throttling, and multi‑round revocation or revocation proofs.

## 2. Modeling Choices

| Aspect | Real System | Tamarin Abstraction |
| ------ | ----------- | ------------------- |
| Crypto | OpenPGP asymmetric encryption | Dolev–Yao perfect public‑key encryption `aenc/adec` |
| Identities | File‑based public keys per group/client | Dynamically generated identities with `PublishClientIdentity` |
| Nonces | 64‑bit randoms (client & server) | `Fr(nc)`, `Fr(ns)` fresh terms |
| Secret Link | 128‑bit hex | Fresh `link` delivered as `aenc(link, pkC)` in M4 |
| Sessions | In‑memory RMAP state | State facts `PendingClient`, `PendingServer` |
| Adversary | Network control, cannot forge signatures/decrypt without keys | Standard Dolev–Yao attacker with public channel (Out/In) |
| Key Compromise | Not yet modeled | Future rule could leak `sk(id)` |

## 3. Protocol (Abstract Messages)

1. M1: C→S: aenc( Pair(id, nc), pkS )
2. M2: S→C: aenc( Pair(nc, ns), pkC )
3. M3: C→S: aenc( ns, pkS )
4. M4: S→C: aenc( link, pkC )

## 4. State & Event Facts

- `CState1(id,nc,kC)`, `CState2(id,nc,ns,kC)` – client local state.
- `SState(id,nc,ns,pkC)` – server local state.
- Event labels: `ClientStart`, `ServerReply`, `ClientGotNonceS`, `ServerIssue`, `ClientComplete`.

## 5. Security Lemmas

```text
lemma secrecy_link:
  All id nc ns link #i. ServerIssue(id,nc,ns,link) @ i ==> not( K(link) )

lemma client_auth:
  All id nc ns link #i.
    ClientComplete(id,nc,ns,link) @ i ==> (Ex #j. ServerReply(id,nc,ns) @ j & j < i)

lemma server_auth:
  All id nc ns link #i.
    ServerIssue(id,nc,ns,link) @ i ==> (Ex #j #k. ClientStart(id,nc) @ j & ClientGotNonceS(id,nc,ns) @ k & j < k & k < i)

lemma injective_client_auth:
  All id nc ns link #i #j1 #j2.
    ClientComplete(id,nc,ns,link) @ i & ServerReply(id,nc,ns) @ j1 & ServerReply(id,nc,ns) @ j2 ==> j1 = j2
```

Interpretation:

- `secrecy_link`: The adversary never derives a valid issued link (unless future compromise rules added).
- `client_auth`: Client completion implies a matching unique server response happened earlier.
- `server_auth`: Server issuance is justified by an honest client initiation and receipt of server nonce.
- `injective_client_auth`: Prevents multiple distinct ServerReply events matching the same client completion (uniqueness of session matching).

## 6. Expected Results
Given no key‑compromise rules and perfect crypto, all four lemmas are expected to be provable. If a compromise rule leaking `kC` (client private key) is added, `secrecy_link` is expected to fail (attack trace) while agreement lemmas may still hold depending on modeling.

## 7. Potential Extensions

- Key Compromise: Add `Reveal(id)` rule exposing `sk(id)`.
- Replay Resistance: Lemma forbidding reuse of `(nc,ns)` across different sessions.
- Injective Server Auth: Mirror of injective uniqueness from server perspective.
- Distinctness of Secrets: Prove `Secret(id,nc,ns)` values are pairwise unique per fresh nonces.
- Optional Link Binding: If link distribution was wrapped, ensure secrecy still holds.

## 8. Limitations

- Single round, no expiry or timeout modeling.
- No modeling of message rejection paths (e.g. malformed decrypt).
- Perfect crypto assumption excludes side‑channel or key management flaws.

## 9. How to Run

Provable batch mode:

```bash
tamarin-prover --prove rmap.spthy
```

Interactive (web UI):

```bash
tamarin-prover interactive rmap.spthy
```
The command prints a local URL (often <http://127.0.0.1:3001>). Open it in a browser, select the theory, and inspect each lemma’s status, proof, or counterexample trace.

## 10. Reading Results

- Green (✔) lemma: Proven. The automated prover found a proof (no reachable attack trace). Typically the proof will be accompanied by a sequence of applied rules and any auxiliary lemmas used; you can expand these in the UI to inspect the proof skeleton.
- Red (✘) lemma: Attack found. Tamarin produced a counterexample trace demonstrating how the adversary can violate the lemma. Open the trace graph to see the sequence of rule applications, the messages sent on the network, and the attacker knowledge facts. Use the trace to identify which rule or missing assumption (for example, a missing key compromise or a replay protection rule) enables the attack.
- Yellow / Pending (or Unknown): The prover couldn't automatically prove or find an attack within its heuristics or time limits. This often requires manual guidance: add helper lemmas, strengthen or weaken the claim, supply invariants, or interactively guide the proof in the UI.

Tips for reading traces and proofs:

- Start from the final event in the trace (the point where the lemma is violated) and step backwards to see which rule produced the critical fact (e.g., K(link) or a mismatched event ordering).
- Look for any "Attacker" facts (K(...), Out(...)) appearing before the supposed secret is created; these indicate leakage paths.
- Check state facts (e.g., CState1, SState) to ensure the modeled state transitions match your protocol intent; mismodeling often causes false attacks.
- If a lemma fails because of a key compromise you did not intend to model, add a `Reveal(sk(id))` only in targeted experiments, not in the base model.


## 11. Conclusion (Fill After Running)
After running the prover (interactive UI) on this model I captured the prover output and UI state. Below are the concrete findings, diagnostics, and recommended next steps.

- Date run: 2025-10-19
- Tamarin version: 1.10.0
- Command used: `tamarin-prover interactive /workspaces/codespaces-blank/RMAP.spthy`

Observations from the interactive UI (captured from the server pages):

- Theory loaded and translated successfully. "Derivation checks started" / "Derivation checks ended" were reported.
- The UI lists the Message theory, 11 multiset-rewriting rules, and proof script placeholders.
- Raw sources: 19 cases (14 partial deconstructions left). Refined sources: 19 cases (14 partial deconstructions left).
- The proof script shows every lemma currently contains a `sorry` proof step (i.e., unproven placeholders). Specifically:
  - `secrecy_link` — proof step(s): `induction` with `sorry` in both `empty_trace` and `non_empty_trace` cases. Status: not yet proven (requires proof effort / autoprove).
  - `client_auth` — `by sorry`. Status: not yet proven.
  - `server_auth` — `induction` with `sorry` cases. Status: not yet proven.
  - `injective_client_auth` — `by sorry`. Status: not yet proven.
  - `exists_run` — `by sorry` (existential run claimed but not produced automatically).

Interpretation / immediate conclusion:

- No lemmas were automatically proven by the interactive session as-is: each lemma still contains `sorry` proof steps. The prover did not report any explicit counterexample traces (no lemma displayed as a concrete attack trace in the UI output captured), nor did the batch prover finish a full proof run in CLI mode here.
- The presence of many partial deconstructions (14) suggests the proof obligations produce multiple case splits that need either manual guidance, helper lemmas, or more aggressive autoprove resources.

Recommended next steps (practical):

1. Try the UI autoprove: open the interactive UI at http://127.0.0.1:3001, focus a lemma, and press `s` (or use the Actions menu) to run the autoprover for that lemma; `S` will search for all solutions. Autoprove can often close `sorry` steps automatically for standard protocol lemmas.

2. If autoprove times out or stalls, run batch proving with resource adjustments. Example CLI runs you can try:

```bash
# short timeout (seconds)
tamarin-prover --prove /workspaces/codespaces-blank/RMAP.spthy --timeout 120

# increase search (may use more CPU/time)
tamarin-prover --prove /workspaces/codespaces-blank/RMAP.spthy --search "depth=10"
```

3. Add small helper lemmas / invariants or rearrange tactics in the proof script to reduce case splitting. Inspect the `sorry` steps in the UI (click the `sorry` link) to see the open constraints and the raw/refined sources feeding them.

4. If you want to test key compromise scenarios explicitly, add a targeted `Reveal(sk(id))` rule and re-run the prover to see which lemmas (notably `secrecy_link`) fail with concrete attack traces.

5. When a lemma fails (counterexample produced), click the trace in the UI to export or screenshot it; include the trace graph and brief root-cause notes in this document.

Summary table (current statuses):

 - secrecy_link: UNPROVEN (contains `sorry` proof steps in both induction cases)
 - client_auth: UNPROVEN (`sorry`)
 - server_auth: UNPROVEN (induction with `sorry` cases)
 - injective_client_auth: UNPROVEN (`sorry`)
 - exists_run: UNPROVEN (`sorry`)

Final note: the interactive UI is reachable locally at http://127.0.0.1:3001 in this environment (the server is running and serving the theory). Use the UI autoprove or the CLI prove with adjusted resources to try to close the `sorry` steps; if you want, I can (a) run autoprove programmatically for each lemma and capture results, or (b) run an extended batch prove with a timeout and then update this section again with the exact final proof/attack outcomes. Which would you like me to do next?
