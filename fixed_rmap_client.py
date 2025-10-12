#!/usr/bin/env python3
"""Fixed RMAP client with better error handling and debugging.

This version includes:
1. Better error handling and debugging output
2. Verification that we're using different keys for client/server
3. More detailed server response analysis
4. Fallback options for different key configurations
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
SERVER_BASE = "http://144.24.5.229:5000"  # Server base URL

# Try different possible server public key locations
SERVER_PUB_KEY_CANDIDATES = [
    "pub.asc",                        # Current location
    "keys/public.asc",               # Alternative location 1
    "keys/public.pgp",               # Alternative location 2
    "tatou/keys/server/pub.asc",     # Server's actual key location
]

CLIENT_PRIV_KEY_PATH = "priv.asc"     # Client *private* key (NOT just public)
CLIENT_PRIV_PASSPHRASE = "Grabbed-Harbor-Breathing-Growth-Jump-Ability-Never-Ask-Worth6"

def find_and_load_server_key():
    """Try to find and load the correct server public key."""
    print("=== Looking for Server Public Key ===")
    
    for candidate in SERVER_PUB_KEY_CANDIDATES:
        if Path(candidate).is_file():
            try:
                server_pub_key, _ = PGPKey.from_file(str(candidate))
                print(f"✓ Loaded server public key from: {candidate}")
                print(f"  Fingerprint: {server_pub_key.fingerprint}")
                print(f"  Algorithm: {server_pub_key.key_algorithm}")
                print(f"  Key size: {server_pub_key.key_size}")
                
                # Try to get user ID info
                if hasattr(server_pub_key, 'userids') and server_pub_key.userids:
                    print(f"  User ID: {server_pub_key.userids[0]}")
                
                return server_pub_key, candidate
            except Exception as e:
                print(f"✗ Failed to load {candidate}: {e}")
                continue
    
    print("✗ Could not find valid server public key")
    return None, None

def load_and_verify_client_key():
    """Load and verify the client private key."""
    print("=== Loading Client Private Key ===")
    
    if not Path(CLIENT_PRIV_KEY_PATH).is_file():
        print(f"✗ Client private key not found: {CLIENT_PRIV_KEY_PATH}")
        return None
    
    try:
        client_priv_key, _ = PGPKey.from_file(str(CLIENT_PRIV_KEY_PATH))
        
        if client_priv_key.is_public:
            print("✗ Provided client key file is only a PUBLIC key; need the PRIVATE key")
            return None
        
        print(f"✓ Loaded client private key from: {CLIENT_PRIV_KEY_PATH}")
        print(f"  Fingerprint: {client_priv_key.fingerprint}")
        print(f"  Is protected: {client_priv_key.is_protected}")
        
        # Get the public key part
        client_pub_key = client_priv_key.pubkey
        if hasattr(client_pub_key, 'userids') and client_pub_key.userids:
            print(f"  User ID: {client_pub_key.userids[0]}")
        
        return client_priv_key
        
    except Exception as e:
        print(f"✗ Failed to load client private key: {e}")
        return None

def verify_different_keys(server_pub_key, client_priv_key):
    """Verify that server and client keys are actually different."""
    print("=== Verifying Key Differences ===")
    
    server_fingerprint = server_pub_key.fingerprint
    client_fingerprint = client_priv_key.fingerprint
    
    if server_fingerprint == client_fingerprint:
        print("✗ ERROR: Server and client keys have the same fingerprint!")
        print("  This means you're using the same key for both, which is wrong.")
        print(f"  Fingerprint: {server_fingerprint}")
        return False
    
    print("✓ Server and client keys are different (good)")
    print(f"  Server fingerprint: {server_fingerprint}")
    print(f"  Client fingerprint: {client_fingerprint}")
    return True

def encrypt_to_server(obj: dict, server_pub_key) -> str:
    """Encrypt a dictionary to the server's public key."""
    plaintext = json.dumps(obj, separators=(",", ":"), sort_keys=True)
    msg = PGPMessage.new(plaintext)
    enc = server_pub_key.encrypt(msg)
    armored = str(enc)
    return base64.b64encode(armored.encode()).decode()

def decrypt_from_server(payload_b64: str, client_priv_key) -> dict:
    """Decrypt a base64 payload from the server using client private key."""
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

def test_server_connectivity():
    """Test basic server connectivity."""
    print("=== Testing Server Connectivity ===")
    
    try:
        r = requests.get(f"{SERVER_BASE}/", timeout=10)
        print(f"✓ Server reachable - Status: {r.status_code}")
        return True
    except Exception as e:
        print(f"✗ Server unreachable: {e}")
        return False

def main():
    """Main RMAP client handshake."""
    
    # Test server connectivity first
    if not test_server_connectivity():
        print("\n❌ Cannot proceed - server is not reachable")
        return False
    
    # Load keys
    server_pub_key, server_key_path = find_and_load_server_key()
    if not server_pub_key:
        print("\n❌ Cannot proceed - no valid server public key found")
        return False
    
    client_priv_key = load_and_verify_client_key()
    if not client_priv_key:
        print("\n❌ Cannot proceed - no valid client private key found")
        return False
    
    # Verify keys are different
    if not verify_different_keys(server_pub_key, client_priv_key):
        print("\n❌ Cannot proceed - key configuration is invalid")
        print("SOLUTION: You need to get the correct server public key.")
        print("The current server public key appears to be the same as your client key.")
        return False
    
    print("\n=== Starting RMAP Handshake ===")
    
    try:
        # ---- Message 1 ----
        nonce_client = secrets.randbits(64)
        msg1_payload_b64 = encrypt_to_server({"identity": IDENTITY, "nonceClient": nonce_client}, server_pub_key)
        
        print(f"[1] Sending Message1: identity={IDENTITY} nonceClient={nonce_client}")
        print(f"    Using server key: {server_key_path}")
        print(f"    Payload length: {len(msg1_payload_b64)} chars")
        
        r1 = requests.post(f"{SERVER_BASE}/api/rmap-initiate", json={"payload": msg1_payload_b64}, timeout=30)
        
        print(f"    Response status: {r1.status_code}")
        print(f"    Response headers: {dict(r1.headers)}")
        
        if r1.status_code != 200:
            print(f"    Response body: {r1.text}")
            print(f"\n❌ Message 1 failed with status {r1.status_code}")
            return False
        
        resp1 = r1.json()
        if "payload" not in resp1:
            print(f"    Server returned error: {resp1}")
            return False
        
        # ---- Decrypt server response (Message 1 response) ----
        print("[2] Decrypting server response...")
        obj1 = decrypt_from_server(resp1["payload"], client_priv_key)
        print(f"    Decrypted Response1: {obj1}")
        
        if obj1.get("nonceClient") != nonce_client:
            print("❌ nonceClient mismatch in server response")
            return False
        
        nonce_server = obj1["nonceServer"]
        
        # ---- Message 2 ----
        print(f"[3] Sending Message2 with nonceServer={nonce_server}")
        msg2_payload_b64 = encrypt_to_server({"nonceServer": nonce_server}, server_pub_key)
        
        r2 = requests.post(f"{SERVER_BASE}/api/rmap-get-link", json={"payload": msg2_payload_b64}, timeout=30)
        
        print(f"    Response status: {r2.status_code}")
        
        if r2.status_code != 200:
            print(f"    Response body: {r2.text}")
            print(f"\n❌ Message 2 failed with status {r2.status_code}")
            return False
        
        resp2 = r2.json()
        if "result" not in resp2:
            print(f"    Server returned error: {resp2}")
            return False
        
        link_token = resp2["result"]
        print(f"✓ Link token received: {link_token}")
        
        # ---- Download watermarked PDF ----
        print("[4] Downloading watermarked PDF...")
        pdf_resp = requests.get(f"{SERVER_BASE}/api/get-version/{link_token}", timeout=30)
        
        if pdf_resp.status_code != 200 or pdf_resp.headers.get("Content-Type") != "application/pdf":
            print(f"❌ Failed to download PDF: {pdf_resp.status_code} {pdf_resp.text[:200]}")
            return False
        
        fname = f"watermarked_{IDENTITY}.pdf"
        with open(fname, "wb") as f:
            f.write(pdf_resp.content)
        
        print(f"✅ Success! Saved watermarked PDF: {fname} ({len(pdf_resp.content)} bytes)")
        return True
        
    except Exception as e:
        print(f"\n❌ Unexpected error during handshake: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)