import os
import sys
import json
import base64
import secrets
import urllib.request

from pgpy import PGPKey, PGPMessage

# CONFIGURATION - Matching the working rmap_client_test.py
IDENTITY = "Group_04"  # Must match what server expects
CLIENT_PRIV_KEY_PATH = "priv.asc"  # Path to your group private key
CLIENT_PRIV_PASSPHRASE = "Grabbed-Harbor-Breathing-Growth-Jump-Ability-Never-Ask-Worth6"
CLIENT_PUB_KEY_PATH = "pub.asc"    # Path to your group public key  
SERVER_PUB_KEY_PATH = "pub.asc"    # Use pub.asc as server key (same as working client)
SERVER_URL = "http://localhost:5000"        # Change if server is remote

class WorkingIdentityManager:
    def __init__(self, client_priv, server_pub, passphrase):
        self.client_priv = client_priv
        self.server_pub = server_pub
        self.passphrase = passphrase

    def encrypt_for_server(self, obj):
        """Encrypt a message for the server"""
        msg = json.dumps(obj, separators=(",", ":"), sort_keys=True)  # Match working client format
        pgpmsg = PGPMessage.new(msg)
        encrypted = self.server_pub.encrypt(pgpmsg)
        armored = str(encrypted)  # Convert to armored string first
        return base64.b64encode(armored.encode()).decode()

    def decrypt_for_client(self, b64msg):
        """Decrypt a message using the client's private key with context manager"""
        armored = base64.b64decode(b64msg)
        pgpmsg = PGPMessage.from_blob(armored)
        
        # Use context manager like the working client
        with self.client_priv.unlock(self.passphrase) as unlocked_key:
            decrypted = unlocked_key.decrypt(pgpmsg)
            return json.loads(decrypted.message)

def main():
    print("Loading keys...")
    
    # Load keys
    try:
        client_priv, _ = PGPKey.from_file(CLIENT_PRIV_KEY_PATH)
        server_pub, _ = PGPKey.from_file(SERVER_PUB_KEY_PATH)
        print("Keys loaded successfully")
        
        # Verify key setup
        print(f"Client private key fingerprint: {client_priv.fingerprint}")
        print(f"Server public key fingerprint: {server_pub.fingerprint}")
        print(f"Using identity: {IDENTITY}")
        
    except Exception as e:
        print(f"Failed to load keys: {e}")
        sys.exit(1)

    # Test key unlocking
    print("Testing private key unlock...")
    try:
        with client_priv.unlock(CLIENT_PRIV_PASSPHRASE) as unlocked_key:
            print(f"Key unlock test successful. Unlocked status: {unlocked_key.is_unlocked}")
    except Exception as e:
        print(f"Key unlock test failed: {e}")
        sys.exit(1)

    # Create identity manager
    try:
        idm = WorkingIdentityManager(client_priv, server_pub, CLIENT_PRIV_PASSPHRASE)
        print("Identity manager created successfully")
    except Exception as e:
        print(f"Failed to create identity manager: {e}")
        sys.exit(1)

    print("Starting RMAP protocol...")

    # Step 1: Initiate handshake
    print("Step 1: Initiating handshake...")
    nonce_client = secrets.randbits(64)
    
    try:
        payload1_b64 = idm.encrypt_for_server({"identity": IDENTITY, "nonceClient": nonce_client})
        print(f"[+] Sending Message1: identity={IDENTITY} nonceClient={nonce_client}")
        print(f"[DEBUG] Payload length: {len(payload1_b64)}")
        print(f"[DEBUG] Payload first 100 chars: {payload1_b64[:100]}...")
        
        req = urllib.request.Request(
            f"{SERVER_URL}/api/rmap-initiate",
            data=json.dumps({"payload": payload1_b64}).encode(),
            headers={"Content-Type": "application/json"}
        )
        
        with urllib.request.urlopen(req, timeout=30) as resp:
            body1 = json.loads(resp.read().decode())
            print(f"[DEBUG] Response status: {resp.status}")
            
        payload2_b64 = body1["payload"]
        print("Step 1 completed successfully")
        
    except Exception as e:
        print(f"Step 1 failed: {e}")
        sys.exit(1)

    # Step 2: Decrypt server response and send nonceServer
    print("Step 2: Processing server response...")
    try:
        obj = idm.decrypt_for_client(payload2_b64)
        print(f"[+] Decrypted server response: {obj}")
        
        # Verify nonce
        received_nonce = int(obj["nonceClient"])
        if received_nonce != nonce_client:
            raise Exception(f"NonceClient mismatch! Expected: {nonce_client}, Got: {received_nonce}")
            
        nonce_server = int(obj["nonceServer"])
        print("Step 2: Server response validated successfully")
        
    except Exception as e:
        print(f"Step 2 failed: {e}")
        sys.exit(1)

    print("Step 3: Sending nonce confirmation...")
    try:
        payload3_b64 = idm.encrypt_for_server({"nonceServer": nonce_server})
        req2 = urllib.request.Request(
            f"{SERVER_URL}/api/rmap-get-link",
            data=json.dumps({"payload": payload3_b64}).encode(),
            headers={"Content-Type": "application/json"}
        )
        
        with urllib.request.urlopen(req2, timeout=30) as resp:
            body2 = json.loads(resp.read().decode())

        link = body2["result"]
        print(f"Got link: {link} (identity: {body2.get('identity', '')})")
        
    except Exception as e:
        print(f"Step 3 failed: {e}")
        sys.exit(1)

    # Step 4: Download the watermarked PDF
    print("Step 4: Downloading watermarked PDF...")
    try:
        req3 = urllib.request.Request(f"{SERVER_URL}/api/get-version/{link}")
        with urllib.request.urlopen(req3, timeout=30) as resp:
            pdf_data = resp.read()
            
        out_fn = f"{IDENTITY}_watermarked.pdf"
        with open(out_fn, "wb") as f:
            f.write(pdf_data)
        print(f"Success! Saved watermarked PDF to: {out_fn}")
        
    except Exception as e:
        print(f"Step 4 failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()