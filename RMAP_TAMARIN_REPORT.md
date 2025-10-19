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
After running the prover on this model, record the concrete outcomes and any immediate follow-ups. Below is a template you can edit with the actual results produced by `tamarin-prover`.

- Date run: YYYY-MM-DD
- Tamarin version: <insert version reported by the tool>
- Command used: `tamarin-prover --prove rmap.spthy` (or `tamarin-prover interactive rmap.spthy` for the UI)

Summary of results (example template):

- secrecy_link: Proven (✔) — No trace found where the attacker derives `link` under the current model (no key compromise rules). The proof used invariants X and Y.
- client_auth: Proven (✔) — Client completion implies a prior `ServerReply` event; proof closed automatically.
- server_auth: Proven (✔) — Server issuance implies a matching client start and client receipt of server nonce.
- injective_client_auth: Proven (✔) — Server replies are unique per completed client session.

If any lemma failed (✘), include:

- Failed lemma: <name>
- Trace summary: brief description of the attack (e.g., "Attacker replays M2 with stale ns; server issues same link twice" or "K(link) obtained after adding Reveal(skC)").
- Root cause hypothesis: (e.g., missing freshness assumption, omitted nonce binding, unintended key leak in rules).
- Suggested fix: (e.g., add explicit state checks, strengthen nonce binding in rules, restrict Reveal rules to experiments).

Next steps and notes:

- If all lemmas are proven, consider modeling key compromise scenarios (targeted `Reveal` rules) and re-running to enumerate attacks.
- If a lemma fails and the trace is valid, fix the model or document the vulnerability and the expected real-world mitigation.
- Attach screenshots or the interactive trace export when filing the final report or a bug ticket.

---
Edit the items above with your actual run outputs to finalize this section.
