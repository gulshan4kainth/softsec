# RMAP Integration Guide

This document explains how RMAP is implemented in the Tatou server, how to configure and deploy it, and how the two RMAP-related endpoints operate end-to-end.

## Overview

RMAP (Registration-based Message Anti-Piracy) adds a privacy-preserving issuance flow to generate a unique secret per recipient, embed it as a watermark into a base PDF, and serve a personalized link for retrieval. The flow is handled using OpenPGP messages and a handshake between a client and the server via two API endpoints.

Core components:
- `rmap.identity_manager.IdentityManager`: loads server keypair and trusted client public keys, and performs OpenPGP (de)cryption.
- `rmap.rmap.RMAP`: implements the RMAP protocol primitives and state (nonces, message handlers).
- Tatou server: exposes two endpoints `/api/rmap-initiate` and `/api/rmap-get-link` and, on success, creates a watermarked PDF version tied to the generated secret.

## Architecture in this repo

- Entry: `server/src/server.py`
  - Helper `_get_rmap()` lazily constructs `IdentityManager` and `RMAP` with paths from environment variables.
  - Endpoints:
    - `POST /api/rmap-initiate` → calls `rmap.handle_message1` and returns a base64 OpenPGP payload.
    - `POST /api/rmap-get-link` → calls `rmap.handle_message2` to obtain the final 128-bit secret (hex). The server derives the recipient identity, watermarks the configured base document, inserts a row into `Versions`, and returns the retrieval link.
- Watermarking: delegated to unified registry (`watermarking_utils.py`). Configurable method via `RMAP_WATERMARK_METHOD` (default: `gulshan`).

## Configuration

Set these in `tatou/.env` (or your deployment environment):

- `RMAP_ENABLE`: `true` to enable endpoints.
- `RMAP_CLIENT_KEYS_DIR`: directory of trusted client public keys inside the container; defaults to `/app/rmap/clients`.
- `RMAP_SERVER_PRIV`: path to server private key (OpenPGP) inside the container; defaults to `/app/rmap/server/priv.asc`.
- `RMAP_SERVER_PUB`: path to server public key inside the container; defaults to `/app/rmap/server/pub.asc`.
- `RMAP_SERVER_PRIV_PASSPHRASE`: passphrase for the server private key, if protected.
- `RMAP_DOCUMENT_ID`: integer ID of the base PDF in `Documents` to watermark per issuance.
- `RMAP_WATERMARK_METHOD`: WM method name, e.g. `gulshan`, `PSM`.
- `RMAP_WATERMARK_KEY`: symmetric key used by the watermark method; defaults to `SECRET_KEY`.

Related existing variables (already in use by the server):
- `SECRET_KEY`, `TOKEN_TTL_SECONDS`, `STORAGE_DIR`.
- DB: `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`.

## Keys and volumes

`docker-compose.yml` mounts keys into the container:

- Client public keys (safe to commit): `./keys/clients` → `/app/rmap/clients:ro`
- Server keypair (DO NOT COMMIT): `${RMAP_SERVER_KEYS_HOST_DIR:-../keys}` → `/app/rmap/server:ro`

Place your server `priv.asc` and `pub.asc` in a secure host directory referenced by `RMAP_SERVER_KEYS_HOST_DIR` (outside the repository), e.g. `../keys` relative to `tatou/`.

## Database schema usage

- `Documents`: base files uploaded/managed by users. RMAP uses a specific `id` configured via `RMAP_DOCUMENT_ID`.
- `Versions`: created by RMAP with columns `documentid`, `link`, `intended_for`, `secret`, `method`, `position`, `path`.
  - `link` is set to the secret hex returned by `handle_message2`. Retrieval is via `GET /api/get-version/<link>`.

## Endpoint details

1) POST `/api/rmap-initiate`
- Body: `{ "payload": "<base64 OpenPGP message 1 from client>" }`
- Server: `RMAP.handle_message1` → returns `{ "payload": "<base64 OpenPGP message 2 to client>" }`.
- Errors: `{ "error": "..." }` with appropriate status.

2) POST `/api/rmap-get-link`
- Body: `{ "payload": "<base64 OpenPGP message 3 from client>" }`
- Server:
  - `RMAP.handle_message2` → `{ "result": "<secret_hex>" }` on success.
  - Decrypts the payload via `IdentityManager.decrypt_for_server` to get `nonceServer`, matches it against `rmap.nonces` to infer the `identity`.
  - Reads `RMAP_DOCUMENT_ID`, applies watermark (`WMUtils.apply_watermark`) with `secret_hex` using method/key from env, writes `.../watermarks/<base_name>__<identity>.pdf`.
  - Inserts a row in `Versions` with `link = secret_hex` and returns `{ "result": "<link>", "identity": "<identity>" }`.
- Errors: JSON with `error` and status code.

Example request/response (pseudo):

Request 1:
```
POST /api/rmap-initiate
{ "payload": "<b64 PGP message 1>" }
```
Response 1:
```
200 { "payload": "<b64 PGP message 2>" }
```

Request 2:
```
POST /api/rmap-get-link
{ "payload": "<b64 PGP message 3>" }
```
Response 2:
```
200 { "result": "b1c9e51102d62b333ac175212a49ca31", "identity": "Group_07" }
```

Retrieval:
```
GET /api/get-version/b1c9e51102d62b333ac175212a49ca31
```
Returns a watermarked PDF.

## Deployment steps

1. Prepare keys and env
   - Place client public keys in `tatou/keys/clients/`.
   - Place server `priv.asc`/`pub.asc` in a secure host directory, e.g. `../keys` relative to `tatou/`.
   - Set `RMAP_SERVER_KEYS_HOST_DIR` to that directory and ensure `.env` has all RMAP variables including passphrase.

2. Build and start
```
cd tatou
docker compose up --build -d
```

3. Health check
```
curl -s http://localhost:5000/healthz | jq
```

4. Verify handshake (integration)
   - Use a proper RMAP client that constructs Message 1 with a known identity.
   - POST Message 1 to `/api/rmap-initiate`; send resulting payload back from the client as Message 3 to `/api/rmap-get-link`.
   - On success, note `result` (link) and test `/api/get-version/<link>`.

## Quick Start: Test Handshake (Optional)

This section shows how to run a one-off, in-container client to validate the full RMAP flow end-to-end without persisting any sensitive keys in your repo.

- Temporarily switch client keys dir to a writable path for testing:

```bash
sed -i 's|^RMAP_CLIENT_KEYS_DIR=.*$|RMAP_CLIENT_KEYS_DIR=/app/tmp/clients|' tatou/.env
docker compose up -d --force-recreate
```

- Run a complete handshake from inside the server container:

```bash
docker exec -i tatou-server-1 python - <<'PY'
import os, json, base64, secrets, urllib.request
from pgpy import PGPKey, PGPUID, PGPMessage
from pgpy.constants import PubKeyAlgorithm, KeyFlags, HashAlgorithm, SymmetricKeyAlgorithm, CompressionAlgorithm
from rmap.identity_manager import IdentityManager

os.makedirs('/app/tmp/clients', exist_ok=True)
identity = 'CI_Test_Hand'
key = PGPKey.new(PubKeyAlgorithm.RSAEncryptOrSign, 2048)
uid = PGPUID.new(identity, email='ci@test.local')
key.add_uid(uid, usage={KeyFlags.Sign, KeyFlags.EncryptCommunications}, hashes=[HashAlgorithm.SHA256], ciphers=[SymmetricKeyAlgorithm.AES256], compression=[CompressionAlgorithm.ZLIB])
with open(f'/app/tmp/clients/{identity}.asc','w') as f:
  f.write(str(key.pubkey))

# Build IdentityManager pointing to temp dir
idm = IdentityManager('/app/tmp/clients','/app/rmap/server/pub.asc','/app/rmap/server/priv.asc', os.environ.get('RMAP_SERVER_PRIV_PASSPHRASE'))

# Message 1: to server
nonce_client = secrets.randbits(64)
msg1_b64 = idm.encrypt_for_server({'identity': identity, 'nonceClient': nonce_client})
req = urllib.request.Request('http://localhost:5000/api/rmap-initiate', data=json.dumps({'payload': msg1_b64}).encode('utf-8'), headers={'Content-Type':'application/json'})
with urllib.request.urlopen(req, timeout=30) as resp:
  body1 = json.loads(resp.read().decode())

# Decrypt Response 1 with client private key to get nonceServer
payload2_b64 = body1['payload']
payload2 = base64.b64decode(payload2_b64)
pgpmsg = PGPMessage.from_blob(payload2)
clear = key.decrypt(pgpmsg)
obj = json.loads(clear.message)
assert int(obj['nonceClient']) == int(nonce_client)
nonce_server = int(obj['nonceServer'])

# Message 3: to server
msg3_b64 = idm.encrypt_for_server({'nonceServer': nonce_server})
req2 = urllib.request.Request('http://localhost:5000/api/rmap-get-link', data=json.dumps({'payload': msg3_b64}).encode('utf-8'), headers={'Content-Type':'application/json'})
with urllib.request.urlopen(req2, timeout=30) as resp:
  body2 = json.loads(resp.read().decode())

print('Issued:', body2)

# HEAD the version link
link = body2['result']
req3 = urllib.request.Request(f'http://localhost:5000/api/get-version/{link}', method='HEAD')
with urllib.request.urlopen(req3, timeout=30) as resp:
  print('HEAD', resp.status, resp.getheader('Content-Type'), resp.getheader('Content-Length'))
PY
```

- Revert and clean up (restore production client dir and remove temp identity):

```bash
sed -i 's|^RMAP_CLIENT_KEYS_DIR=.*$|RMAP_CLIENT_KEYS_DIR=/app/rmap/clients|' tatou/.env
docker compose up -d --force-recreate
docker exec tatou-server-1 sh -lc 'rm -rf /app/tmp/clients'
```

This leaves previously issued links functional while returning the server to production settings.

## Troubleshooting

- "RMAP disabled": ensure `RMAP_ENABLE=true` in `.env` and container restarted.
- "clients dir not found" / "server keypair not found": validate volumes and `RMAP_SERVER_KEYS_HOST_DIR`.
- Decryption errors: verify `RMAP_SERVER_PRIV_PASSPHRASE` matches the private key and server can read the files.
- "watermarking ... failed": ensure base document exists (`RMAP_DOCUMENT_ID` points to an actual `Documents` row) and watermark method is applicable.
- Link 404: confirm `Versions.link` row was inserted and the file path exists under storage.

## Security notes

- Server keypair must not be committed to Git. Keep it outside the repo and mount read-only. Manage passphrase using `.env` or external secret manager.
- Client keys directory is read-only and contains trusted identities; only add keys from approved clients.
- The server only accepts OpenPGP messages; invalid payloads are rejected with 400.
