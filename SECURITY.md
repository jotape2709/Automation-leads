# Security policy

## Security model

Automation Leads is a local application. The dashboard binds exclusively to
`127.0.0.1`, rejects non-loopback clients, validates the `Host` and `Origin`
headers and does not provide a remote deployment mode.

Credentials are read from a local `.env` file ignored by Git. Lead spreadsheets,
CRM databases and common credential formats are also ignored. The repository
includes a secret scanner executed by CI and a dependency audit with
`pip-audit`.

The application never sends WhatsApp messages automatically. It creates a draft,
opens `wa.me` and requires the operator to review and send the message.

## Google Places key

The Google Places API key identifies a Google Cloud project and its billable API
usage. It is not a Google account password and cannot be used to sign in to
Gmail, Drive or the Google Cloud console. An exposed unrestricted key can,
however, consume quota and generate charges in the linked Cloud project.

Before using the collector:

1. Create a dedicated Google Cloud project and a key used only by this app.
2. Restrict the key to **Places API (New)**.
3. Apply an IP restriction if the computer has a stable public IP.
4. If the IP is dynamic, keep the key server-side, use a separate project and
   configure strict API quotas and billing alerts.
5. Disable every API not required by this project.
6. Review usage by credential in Metrics Explorer.
7. Keep `GOOGLE_PLACES_ENABLED=0` until the restrictions and quotas are ready.

The collector has a configurable request ceiling and an explicit opt-in gate,
but those controls do not replace restrictions in Google Cloud.

## Public-repository audit

On 2026-08-16, the current tree and 30 reachable commits were inspected for
Google, OpenAI, GitHub and AWS credential formats, generic assigned secrets and
private keys. No credential was detected. GitHub secret scanning, Dependabot
alerts and code scanning should still be enabled after the repository becomes
public.

Security review reduces risk but cannot guarantee that a third-party platform,
dependency or future change will never introduce a vulnerability.

## Reporting

Do not open a public issue containing a credential, lead list, phone number or
customer information. Revoke the credential first, then contact the repository
owner privately.
