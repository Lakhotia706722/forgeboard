# Custom Subdomain White-Label Architecture

> **Status: Design document — not yet built.**
> This document scopes what a custom-subdomain setup requires so it can be
> planned as a follow-up without surprises.

---

## What we have after Phase 9d

Each agency-managed workspace can carry:
- `brand_logo_url` — external HTTPS URL to a logo image
- `brand_primary_color` — CSS hex color applied via CSS custom property
- `brand_app_name` — replaces "ForgeBoard" in the nav

These are applied client-side via the `useBranding` hook.
The URL is always `app.forgeboard.io` regardless of branding.

---

## What custom subdomains would add

An agency wants their clients to access the platform at:
```
acme.yourdomain.com   →  ForgeBoard, white-labeled as "Acme Agents"
```

instead of `app.forgeboard.io`.

---

## What it requires

### 1. DNS

The agency (or their client) adds a CNAME in their DNS:
```
acme.yourdomain.com  CNAME  app.forgeboard.io
```

We need to handle `Host: acme.yourdomain.com` arriving at our server.

---

### 2. TLS certificate provisioning

Two viable approaches:

**Option A — Let's Encrypt + cert-manager (recommended for self-hosted)**
- Use cert-manager in Kubernetes with an ACME HTTP-01 or DNS-01 challenge.
- Each new custom domain triggers a `Certificate` CRD creation.
- cert-manager issues and auto-renews. Turnaround: ~30–60 seconds.

**Option B — Cloudflare for SaaS (simplest for managed hosting)**
- Agency points their DNS to Cloudflare.
- Cloudflare issues a cert and proxies to our origin.
- We only need a wildcard cert on our origin (`*.forgeboard.io`).
- No cert management code needed on our side.
- Cost: ~$2/custom domain/month on Cloudflare's SSL for SaaS plan.

**Option C — AWS ACM + ALB**
- Use ACM for cert issuance, ALB for routing.
- Works well if already on AWS. Requires ACM DNS validation per domain.

---

### 3. Routing — map hostname → workspace

When a request arrives at `acme.yourdomain.com`, the backend needs to:
1. Extract the `Host` header.
2. Look up `workspaces WHERE custom_domain = 'acme.yourdomain.com'`.
3. Serve the app with that workspace's branding pre-loaded.

**DB change needed:**
```sql
ALTER TABLE workspaces ADD COLUMN custom_domain VARCHAR(255) UNIQUE;
CREATE INDEX ix_workspaces_custom_domain ON workspaces(custom_domain);
```

**New `WorkspaceByDomain` endpoint:**
```
GET /public/workspace-by-domain?host=acme.yourdomain.com
→ { workspace_id, brand_* fields }
```

The frontend calls this on load (before the user logs in) to apply branding
and set the default workspace context for the login page.

---

### 4. Frontend changes

Currently the frontend is served as a static SPA from a single origin.
With custom domains it could be served from multiple origins.

Two approaches:

**Option A — Single SPA, branding via API**
The same `index.html` bundle is served for all domains.
On load, the app calls `GET /public/workspace-by-domain` using
`window.location.hostname`, gets the branding, and applies it.
**This is the simplest path and works without changes to the build pipeline.**

**Option B — Per-agency static build**
Generate a separate build per agency with their colors baked into the CSS.
Only worth it for very large agencies who need maximum performance.
Not recommended — maintenance overhead is high.

---

### 5. Auth / CORS

The JWT stays domain-agnostic (encodes `user_id` only).
CORS needs to accept `acme.yourdomain.com` as an allowed origin.

Two ways:
- **Dynamic CORS**: middleware reads `Host`, checks against `custom_domain`
  column, adds it to allowed origins on the fly.
- **Wildcard CORS**: allow any origin that resolves to our IP (risky — avoid).

---

## Implementation checklist (when ready to build)

1. `workspaces.custom_domain` column + index + validation endpoint
2. Choose TLS strategy (Cloudflare for SaaS is fastest to market)
3. `GET /public/workspace-by-domain` unauthenticated endpoint
4. Frontend: on-load hostname check + `useBranding` reads from that endpoint
   for unauthenticated pages (login, signup)
5. CORS middleware: dynamic allowed-origins from `custom_domain` table
6. Admin UI: workspace settings page → "Custom domain" field + DNS instructions

---

## Rough effort estimate

| Step | Estimate |
|------|----------|
| DB + routing endpoint | 0.5 days |
| Frontend hostname detection | 0.5 days |
| TLS (Cloudflare for SaaS setup) | 1 day |
| Dynamic CORS | 0.5 days |
| Admin UI + DNS instructions copy | 0.5 days |
| **Total** | **~3 days** |

This is a well-scoped follow-up once Phase 9d branding is validated with
at least one real agency client.
