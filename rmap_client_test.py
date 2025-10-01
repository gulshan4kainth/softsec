"""Minimal RMAP client handshake test script (no environment variable usage).

Performs:
 1. Message 1 (identity + nonceClient) encrypted to server public key.
 2. Decrypts server response (needs YOUR client private key).
 3. Message 2 (nonceServer) encrypted to server public key.
 4. Fetches resulting watermarked PDF version.

Adjust the CONSTANTS section below to match your setup.

NOTE: This Python 3.13 environment removed the stdlib 'imghdr' module which
      PGPy still imports. A local shim is injected before importing PGPy.
"""

import sys, secrets, base64, json, requests
from pathlib import Path

# ---- Python 3.13 imghdr shim (PGPy still imports it) ----
if 'imghdr' not in sys.modules:  # pragma: no cover
    import types
    shim = types.ModuleType('imghdr')
    def what(file, h=None):  # minimal API
        return None
    shim.what = what
    sys.modules['imghdr'] = shim

from pgpy import PGPKey, PGPMessage  # after shim

# ---- CONSTANTS (edit these) ----
IDENTITY = "Group_04"                 # Must match public key file stem on server
SERVER_BASE = "http://127.0.0.1:5000"  # Server base URL
SERVER_PUB_KEY_PATH = "pub.asc"       # Server public key (ASCII-armored)
CLIENT_PRIV_KEY_PATH = "priv.asc"     # Client *private* key (NOT just public)
CLIENT_PRIV_PASSPHRASE = "Grabbed-Harbor-Breathing-Growth-Jump-Ability-Never-Ask-Worth6"          # Set passphrase string if key is protected

for p in (SERVER_PUB_KEY_PATH, CLIENT_PRIV_KEY_PATH):
    if not Path(p).is_file():
        print(f"[ERROR] Missing key file: {p}", file=sys.stderr)
        sys.exit(2)

# ---- Load keys ----
server_pub_key, _ = PGPKey.from_file(str(SERVER_PUB_KEY_PATH))
client_priv_key, _ = PGPKey.from_file(str(CLIENT_PRIV_KEY_PATH))
if client_priv_key.is_public:
    raise SystemExit("Provided client key file is only a PUBLIC key; need the PRIVATE key for identity")

# Optional: derive client public key to show identity
client_pub_key = client_priv_key.pubkey

def encrypt_to_server(obj: dict) -> str:
    plaintext = json.dumps(obj, separators=(",", ":"), sort_keys=True)
    msg = PGPMessage.new(plaintext)
    enc = server_pub_key.encrypt(msg)
    armored = str(enc)
    return base64.b64encode(armored.encode()).decode()

def decrypt_from_server(payload_b64: str) -> dict:
    armored = base64.b64decode(payload_b64)
    pgp_msg = PGPMessage.from_blob(armored)
    if client_priv_key.is_protected and CLIENT_PRIV_PASSPHRASE is None:
        raise SystemExit("Private key needs passphrase but none provided.")
    if client_priv_key.is_protected:
        with client_priv_key.unlock(CLIENT_PRIV_PASSPHRASE):
            dec = client_priv_key.decrypt(pgp_msg)
    else:
        dec = client_priv_key.decrypt(pgp_msg)
    return json.loads(dec.message)

# ---- Message 1 ----
nonce_client = secrets.randbits(64)
msg1_payload_b64 = encrypt_to_server({"identity": IDENTITY, "nonceClient": nonce_client})
print(f"[+] Sending Message1: identity={IDENTITY} nonceClient={nonce_client}")
r1 = requests.post(f"{SERVER_BASE}/api/rmap-initiate", json={"payload": msg1_payload_b64}, timeout=30)
r1.raise_for_status()
resp1 = r1.json()
if "payload" not in resp1:
    raise SystemExit(f"Server returned error in message1: {resp1}")

# ---- Decrypt server response (Message 1 response) ----
obj1 = decrypt_from_server(resp1["payload"])
print(f"[+] Decrypted Response1: {obj1}")
if obj1.get("nonceClient") != nonce_client:
    raise SystemExit("nonceClient mismatch in server response.")
nonce_server = obj1["nonceServer"]

# ---- Message 2 ----
msg2_payload_b64 = encrypt_to_server({"nonceServer": nonce_server})
r2 = requests.post(f"{SERVER_BASE}/api/rmap-get-link", json={"payload": msg2_payload_b64}, timeout=30)
r2.raise_for_status()
resp2 = r2.json()
if "result" not in resp2:
    raise SystemExit(f"Server returned error in message2: {resp2}")
link_token = resp2["result"]
print("[+] Link token (secret):", link_token)

# ---- Download watermarked PDF ----
pdf_resp = requests.get(f"{SERVER_BASE}/api/get-version/{link_token}", timeout=30)
if pdf_resp.status_code != 200 or pdf_resp.headers.get("Content-Type") != "application/pdf":
    raise SystemExit(f"Failed to download version: {pdf_resp.status_code} {pdf_resp.text[:200]}")
fname = f"watermarked_{IDENTITY}.pdf"
with open(fname, "wb") as f:
    f.write(pdf_resp.content)
print("[+] Saved watermarked PDF:", fname, "size:", len(pdf_resp.content))