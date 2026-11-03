# Service API Keys - Who Does What
### Round 15, issue R15-RH1 (#213) and its follow-ups. Read this before touching any service-to-service call.

---

## Why this exists

When one of our services calls another (Inventory asks Forecast for a number, Supplier Portal asks Compliance to screen a supplier), the service being called has no way to know who is calling. Anyone who can reach the port can call it.

Service API keys fix that. Every calling service sends its own secret key with each request. The service being called checks the key before doing anything. A missing, wrong or revoked key is rejected.

User logins (JWT tokens and `/verify`) stay exactly as they are. API keys are only for **service-to-service** calls.

---

## The one rule

**Each person changes only their own service.** Rahul builds the platform side and writes down exactly how to use it. Everyone else then adds it to their own service, following his guide.

This is the same approach we used for auth in Round 5: one person builds and documents the pattern, everyone else copies it.

Why not let one person change all services in one PR?
- Those files belong to other owners, who just changed them for their own Round 15 work. One big PR would conflict with theirs.
- A PR touching five services is hard to review and hard to roll back.
- Each owner knows their own HTTP client and config best.

---

## Who calls whom

Taken from the integration blueprint, section 4.

| Caller | Calls | Caller owner | Receiver owner |
|---|---|---|---|
| Inventory | Forecast serving (`GET /api/v1/demand/forecast/{sku_id}`) | Balaji | Ajith |
| Inventory | Compliance (`POST /api/v1/compliance/internal-check`) | Balaji | Rashida |
| Supplier Portal | Compliance (`POST /api/v1/compliance/internal-check`) | Rashida | Rashida |
| Supplier Portal | Supplier Risk (`GET /api/v1/suppliers/{supplier_id}/risk-score`) | Rashida | Mahendhar |
| Gateway BFF | Services it proxies or aggregates | Mahendhar | each service owner |

So there are two kinds of work:
- **Sending a key** (the caller side): Inventory, Supplier Portal, Gateway BFF.
- **Checking a key** (the receiver side): Forecast serving, Compliance, Supplier Risk.

---

## Order of work

```
Step 1: Rahul        R15-RH1 (#213)   platform side + "how to use it" guide
                           |
                           v   (merged into develop)
Step 2: in parallel  R15-B6   Balaji      Inventory sends its key
                     R15-R7   Rashida     Supplier Portal sends its key; Compliance checks keys
                     R15-M5   Mahendhar   Gateway BFF sends its key; Supplier Risk checks keys
                     R15-A6   Ajith       Forecast serving checks keys
```

**Nobody starts step 2 until Rahul's PR is merged.** Until then, read his PR and ask questions on it.

---

## Step 1: Rahul (R15-RH1, #213)

Platform service only. No changes in any other service's folder.

**Build:**
- Issue a key per calling service (`inventory`, `supplier-portal`, `gateway-bff`) and revoke a key.
- One way for a receiving service to check a key: either a verify endpoint on the platform service, or a small shared helper. Pick one, explain why in the README.
- Seed demo keys automatically with `make seed`.
- Tests: valid key accepted, missing key rejected, wrong key rejected, revoked key rejected.
- `.env.example` with the variable names (no real keys).

**Write a README section: "How to call another service with an API key".** This section is the contract everyone else follows, so it must answer, with examples:
1. **Env var names**, for the caller's own key, and for the receiver if it needs any setting.
2. **Header**: the exact header name and value format, with one example request (`curl`).
3. **Caller snippet**: a copy-paste Python example using `httpx`, with a timeout.
4. **Receiver snippet**: a copy-paste FastAPI dependency that checks the key, or the call to the verify endpoint.
5. **Responses**: what a receiver returns for a missing or invalid key (401) and for a valid key that isn't allowed to call this endpoint (403), with the error body format.
6. **Local setup**: how someone gets a working key on their laptop in one step.
7. **Rules**: keys come only from environment variables, are never committed, and are never logged.

**Update the "Done when" list on #213** to match this list, then go ahead.

---

## Step 2: the follow-up issues

Each one is small (about half a day), has **"Depends on: R15-RH1 (#213)"**, and is on the Week 2 milestone.

### R15-B6: Balaji, Inventory sends its service key
- Load the key from the env var named in Rahul's guide.
- Send it on calls to Forecast serving and to Compliance, using the header from the guide.
- `.env.example` updated.
- Tests: the header is present on both outgoing calls, and a 401 from the receiver is handled the way your service already handles a failed call (no crash, clear log line without the key in it).

### R15-R7: Rashida, Supplier Portal sends its key, Compliance checks keys
- **Supplier Portal (caller):** load the key from env, send it on calls to Compliance and Supplier Risk.
- **Compliance (receiver):** check the key on `/internal-check` the way Rahul's guide says.
- `.env.example` updated in both services.
- Tests: valid key accepted, missing key 401, revoked key 401. Your existing `/internal-check` contract test still passes.

### R15-M5: Mahendhar, Gateway BFF sends its key, Supplier Risk checks keys
- **Gateway BFF (caller):** send the key on outbound calls to services.
- **Supplier Risk (receiver):** check the key on `/risk-score`.
- `.env.example` updated in both.
- Tests: same three cases for Supplier Risk; the header is present on BFF outbound calls.

### R15-A6: Ajith, Forecast serving checks keys
- Check the key on the forecast endpoint the way Rahul's guide says.
- Health and readiness endpoints stay open (no key needed), so Kubernetes and Docker health checks keep working.
- `.env.example` updated.
- Tests: valid key accepted, missing key 401, revoked key 401.

---

## Things that must not happen

- Changing another person's service, even "just one line". Ask them on their issue instead.
- A real key in any committed file, test fixture or example. Use obviously fake values in `.env.example`, like `SERVICE_API_KEY=change-me`.
- Logging the key, even partly, even at debug level.
- Putting the key in a URL or query string. Header only.
- Using a user's login token for a service-to-service call.

---

## If you're unsure

Ask on the issue, not in private chat, so the answer is there for the next person:
- Questions about the key format, header or checks: comment on **#213**.
- Questions about your own service: comment on your own follow-up issue.
