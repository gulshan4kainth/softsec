#!/usr/bin/env python3
"""
Simple RMAP client for testing with other groups
Just modify the configuration section and run
"""

import os
import sys
import json
import base64
import secrets
import urllib.request

from pgpy import PGPKey, PGPMessage

# ===== CONFIGURATION - MODIFY THESE VALUES =====
YOUR_IDENTITY = "Group_04"  # Your group (always Group_04)
YOUR_PRIV_KEY = "priv.asc"  # Your private key
YOUR_PASSPHRASE = "Grabbed-Harbor-Breathing-Growth-Jump-Ability-Never-Ask-Worth6"

# TARGET GROUP - Change these for each group you want to test:
TARGET_SERVER_URL = "http://144.24.5.229:5000"  # 🔴 CHANGE THIS: Target group's server IP
TARGET_GROUP_PUBKEY = "Group_04.asc"            # 🔴 CHANGE THIS: Target group's public key file

# ================================================

class SimpleRMAPClient:
    def __init__(self, your_priv_key, target_pub_key, passphrase):
        self.your_priv_key = your_priv_key
        self.target_pub_key = target_pub_key
        self.passphrase = passphrase

    def encrypt_to_target(self, data):
        """Encrypt data to target server"""
        msg = json.dumps(data, separators=(",", ":"), sort_keys=True)
        pgpmsg = PGPMessage.new(msg)
        encrypted = self.target_pub_key.encrypt(pgpmsg)
        return base64.b64encode(str(encrypted).encode()).decode()

    def decrypt_from_target(self, b64_data):
        """Decrypt response from target server"""
        armored = base64.b64decode(b64_data)
        pgpmsg = PGPMessage.from_blob(armored)
        
        with self.your_priv_key.unlock(self.passphrase) as unlocked_key:
            decrypted = unlocked_key.decrypt(pgpmsg)
            return json.loads(decrypted.message)

def main():
    print(f"🎯 Testing RMAP with target group")
    print(f"   Your identity: {YOUR_IDENTITY}")
    print(f"   Target server: {TARGET_SERVER_URL}")
    print(f"   Target pubkey: {TARGET_GROUP_PUBKEY}")
    
    # Load keys
    try:
        print("\n📂 Loading keys...")
        your_priv, _ = PGPKey.from_file(YOUR_PRIV_KEY)
        target_pub, _ = PGPKey.from_file(TARGET_GROUP_PUBKEY)
        
        print(f"   ✓ Your private key: {your_priv.fingerprint}")
        print(f"   ✓ Target public key: {target_pub.fingerprint}")
        
    except FileNotFoundError as e:
        print(f"   ❌ Key file not found: {e}")
        print(f"\nMake sure you have:")
        print(f"   - {YOUR_PRIV_KEY} (your private key)")
        print(f"   - {TARGET_GROUP_PUBKEY} (target group's public key)")
        return
    except Exception as e:
        print(f"   ❌ Error loading keys: {e}")
        return

    # Test key unlock
    try:
        with your_priv.unlock(YOUR_PASSPHRASE):
            print("   ✓ Your key unlocks successfully")
    except Exception as e:
        print(f"   ❌ Key unlock failed: {e}")
        return

    # Create client
    client = SimpleRMAPClient(your_priv, target_pub, YOUR_PASSPHRASE)

    # RMAP Protocol
    print(f"\n🔄 Starting RMAP handshake...")
    
    # Step 1: Send identity + nonce
    nonce_client = secrets.randbits(64)
    try:
        print("   Step 1: Sending identity and client nonce...")
        payload = client.encrypt_to_target({
            "identity": YOUR_IDENTITY,
            "nonceClient": nonce_client
        })
        
        response = urllib.request.urlopen(
            urllib.request.Request(
                f"{TARGET_SERVER_URL}/api/rmap-initiate",
                data=json.dumps({"payload": payload}).encode(),
                headers={"Content-Type": "application/json"}
            ),
            timeout=30
        )
        
        result = json.loads(response.read().decode())
        print("   ✓ Server responded to handshake")
        
    except Exception as e:
        print(f"   ❌ Step 1 failed: {e}")
        print(f"\nPossible issues:")
        print(f"   - Server {TARGET_SERVER_URL} is not reachable")
        print(f"   - Server doesn't have your public key for identity {YOUR_IDENTITY}")
        return

    # Step 2: Decrypt response and verify nonce
    try:
        print("   Step 2: Decrypting server response...")
        server_data = client.decrypt_from_target(result["payload"])
        
        if int(server_data["nonceClient"]) != nonce_client:
            raise Exception("Nonce verification failed!")
        
        nonce_server = int(server_data["nonceServer"])
        print(f"   ✓ Nonce verified, server nonce: {nonce_server}")
        
    except Exception as e:
        print(f"   ❌ Step 2 failed: {e}")
        print(f"\nPossible issues:")
        print(f"   - Server encrypted response with wrong key")
        print(f"   - Your identity {YOUR_IDENTITY} not registered on their server")
        print(f"   - They don't have your correct public key")
        return

    # Step 3: Send server nonce back and get link
    try:
        print("   Step 3: Confirming server nonce...")
        payload = client.encrypt_to_target({"nonceServer": nonce_server})
        
        response = urllib.request.urlopen(
            urllib.request.Request(
                f"{TARGET_SERVER_URL}/api/rmap-get-link",
                data=json.dumps({"payload": payload}).encode(),
                headers={"Content-Type": "application/json"}
            ),
            timeout=30
        )
        
        result = json.loads(response.read().decode())
        download_link = result["result"]
        confirmed_identity = result.get("identity", "unknown")
        
        print(f"   ✓ Got download link: {download_link}")
        print(f"   ✓ Server confirmed identity: {confirmed_identity}")
        
    except Exception as e:
        print(f"   ❌ Step 3 failed: {e}")
        return

    # Step 4: Download PDF
    try:
        print("   Step 4: Downloading watermarked PDF...")
        
        response = urllib.request.urlopen(
            f"{TARGET_SERVER_URL}/api/get-version/{download_link}",
            timeout=30
        )
        
        pdf_data = response.read()
        
        # Create filename with target info
        target_name = TARGET_GROUP_PUBKEY.replace('.asc', '').replace('Group_', 'Group')
        filename = f"{YOUR_IDENTITY}_from_{target_name}.pdf"
        
        with open(filename, 'wb') as f:
            f.write(pdf_data)
        
        print(f"   ✓ Downloaded {len(pdf_data)} bytes")
        print(f"   ✓ Saved as: {filename}")
        
    except Exception as e:
        print(f"   ❌ Step 4 failed: {e}")
        return

    print(f"\n🎉 SUCCESS! RMAP completed with target group")
    print(f"\n📋 Summary:")
    print(f"   - Your identity: {YOUR_IDENTITY}")
    print(f"   - Target server: {TARGET_SERVER_URL}")
    print(f"   - Downloaded: {filename}")

if __name__ == "__main__":
    main()