# Security Policy & Cryptographic Architecture (v3.2)

## Security Model

**JPX Lab Automation Leads & CRM** is a local-first application. Both the native
Rust gateway (`src/main.rs`) and the Python backend (`app.py`) bind exclusively
to `127.0.0.1`, reject non-loopback clients, validate `Host`, `Origin`, and
`X-JPX-Token` (CSRF) headers, and never expose a remote deployment mode.

The application never sends WhatsApp messages automatically. It creates a
context-aware draft, opens `wa.me`, and requires the human operator to review
and send every message manually.

## Local Cryptographic Vault (`prospeccao/vault.py`)

API keys (`OPENAI_API_KEY`, `GEMINI_API_KEY`, `GOOGLE_PLACES_API_KEY`) and SDR
defaults configured through the **🔐 Configurações & Cofre** tab are encrypted
at rest in `data/vault.enc` (ignored by Git) using an audited **Encrypt-then-MAC
AEAD** construction built on Python's standard cryptographic primitives:

1. **Key Derivation (`PBKDF2-HMAC-SHA256`)**: Derives 512 bits of key material
   using **600,000 iterations** (OWASP recommendation) and a 128-bit CSPRNG salt,
   combining a local 256-bit machine entropy key (`data/.vault.key`, `chmod 600`)
   with an optional operator Master Passphrase.
2. **Subkey Separation (`HMAC-SHA256`)**: Splits derived material into
   independent 256-bit encryption (`K_enc`) and authentication (`K_mac`) subkeys.
3. **Stream Cipher + Integrity Tag (`CTR-HMAC-SHA256`)**: Encrypts the JSON
   payload in Counter Mode using a 128-bit CSPRNG nonce and authenticates the
   header (`JPXVAULT1`), salt, nonce, and ciphertext with an `HMAC-SHA256` tag
   verified in **constant time** via `hmac.compare_digest`.
4. **Secret Masking, Memory Lock & Key Rotation**:
   - Saved secrets are always masked (`sk-p••••••••1234`) when returned by
     `GET /api/settings`;
   - Operators can wipe decrypted keys from RAM at any time via
     `POST /api/vault/lock` and rotate the cryptographic key/salt/nonce via
     `POST /api/vault/rotate`;
   - A sliding-window rate limiter (`LimitadorTaxa`) protects vault unlock and
     save operations against brute-force attempts.

## Google Places Key

The Google Places API key identifies a Google Cloud project and its billable API
usage. Before enabling collection (`GOOGLE_PLACES_ENABLED=1`):

1. Create a dedicated Google Cloud project and a key used only by this app.
2. Restrict the key to **Places API (New)**.
3. Apply an IP restriction if the computer has a stable public IP.
4. Configure strict API quotas and billing alerts in Google Cloud.
5. Keep `GOOGLE_PLACES_ENABLED=0` until restrictions and quotas are active.

## Defense-in-Depth Controls

- **Static Secret & File Scanner (`scripts/security_scan.py`)**: Blocks `.xlsx`,
  `.db`, `.enc`, `.vault`, `.key`, and `.env` files as well as Google, OpenAI,
  GitHub, and AWS key patterns from ever being tracked by Git.
- **Strict DOM Rendering**: `static/index.html` uses safe DOM construction
  (`createElement` / `textContent`) with zero `innerHTML` or inline `onclick=`
  handlers, enforced by automated unit tests (`tests/test_security.py`) and a
  strict `Content-Security-Policy`.
- **Spreadsheet Hardening**: `prospeccao/leads.py` inspects `.xlsx` archives for
  zip-bomb compression ratios before parsing, and `index.py` neutralizes formula
  prefixes (`=`, `+`, `-`, `@`) on export.

## Reporting

Do not open a public issue containing a credential, lead list, phone number, or
customer information. Revoke the credential first, then contact the repository
owner privately.

