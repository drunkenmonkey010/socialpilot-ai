# SocialPilot AI --- Development Progress & Technical Decision Log

## 1. Purpose of This Document

This document records everything completed so far for the social-media
integration portion of **SocialPilot AI**, including:

-   What we originally planned
-   What changed and why
-   Technologies and platforms considered
-   Problems encountered
-   How each problem was diagnosed and fixed
-   Architecture decisions
-   Current implementation state
-   Important use cases
-   Failure/crash scenarios
-   Security concerns
-   What should be done next

This is a development-history document for the project. It is
intentionally detailed so that future development can continue without
losing the reasoning behind earlier decisions.

------------------------------------------------------------------------

# 2. Original Goal

The broader goal of SocialPilot AI is to build an **agentic AI
social-media management platform**.

The intended application flow is:

``` text
User
  ↓
SocialPilot AI
  ↓
Connect social-media accounts
  ↓
Create / generate content
  ↓
Select platform(s)
  ↓
Publish / schedule
  ↓
Social-media platform APIs
```

The social-account layer therefore needs to support:

-   Connecting external social-media accounts
-   Securely storing account information and OAuth credentials
-   Associating every social account with the correct SocialPilot user
-   Reusing connected accounts when creating posts
-   Eventually publishing posts through platform APIs
-   Eventually supporting multiple platforms from one common abstraction

The first major integration attempt did not end up being the final
platform choice.

------------------------------------------------------------------------

# 3. Platform Decisions and Change of Plan

## 3.1 X/Twitter --- Dropped for Development

X was initially considered as a social-media integration.

We investigated the developer/OAuth setup and obtained the required
credentials during development.

However, an important project requirement became clear:

> Development should not depend on a platform that requires paid API
> access for the functionality we need.

Because of the cost/access limitations associated with X API usage, we
decided:

``` text
X
↓
DROP FOR DEVELOPMENT
```

The plan is to potentially bring X back later during production if the
project's budget and API requirements justify it.

### Why this decision was made

The priority during development is:

-   Keep the project free/low-cost
-   Avoid unnecessary external API expenses
-   Get the architecture working with a platform that permits
    development/testing
-   Avoid locking the entire project around a paid API

Therefore, X was intentionally removed from the current development
path.

------------------------------------------------------------------------

# 4. Meta / Instagram --- Problem Encountered

Instagram/Meta was also part of the planned social-media integrations.

A basic Instagram route already existed:

``` text
app/api/routes/instagram.py
```

The project also had Instagram configuration fields:

``` text
instagram_app_id
instagram_app_secret
instagram_redirect_uri
```

However, the Meta/Instagram integration was not progressing reliably
enough for the current development stage.

Rather than spending excessive time blocking the entire social-account
architecture on Meta's configuration/API requirements, we decided to use
another platform for development.

This led to the Mastodon decision.

------------------------------------------------------------------------

# 5. Mastodon --- Development Platform Decision

Mastodon was selected as the current development platform because it
provides a practical OAuth/API environment for testing the
social-account architecture without making the project dependent on X's
paid API requirements.

The development instance used is:

``` text
https://mastodon.social
```

The project was configured around:

``` text
mastodon_instance_url
mastodon_client_id
mastodon_client_secret
mastodon_redirect_uri
```

The redirect URI currently used is:

``` text
http://localhost:8000/social-accounts/mastodon/callback
```

### Important architectural decision

Mastodon is being used as a **development implementation of the generic
social-account architecture**, not as a statement that Mastodon is the
only platform SocialPilot AI will ever support.

The intended architecture is:

``` text
                 SocialPilot AI
                       |
          +------------+------------+
          |            |            |
       Instagram    Mastodon       X
          |            |            |
       Adapter       Adapter      Adapter
```

The common SocialAccount model/service is intended to keep
platform-specific logic separated from the generic account-management
layer.

------------------------------------------------------------------------

# 6. Existing Social Account Architecture

Before Mastodon was fully connected, the project already had the
foundation for a generic social-account system.

The relevant layers are:

``` text
app/
├── api/
│   └── routes/
│       ├── mastodon.py
│       ├── instagram.py
│       └── social_account.py
│
├── integrations/
│   └── mastodon/
│       └── oauth.py
│
├── models/
│   ├── social_account.py
│   └── user.py
│
├── repositories/
│   └── social_account.py
│
├── schemas/
│   └── social_account.py
│
└── services/
    └── social_account.py
```

This separation is intentional.

------------------------------------------------------------------------

# 7. SocialAccount Database Model

The project contains a generic `SocialAccount` model.

Important fields include:

``` text
id
user_id
platform
account_name
account_id
access_token
refresh_token
token_expires_at
is_active
created_at
updated_at
```

Conceptually:

``` text
User
 |
 +---- SocialAccount
          |
          +---- platform
          +---- account_name
          +---- account_id
          +---- access_token
          +---- refresh_token
          +---- expiry
```

## Why a generic model was chosen

Instead of creating:

``` text
MastodonAccount
InstagramAccount
XAccount
LinkedInAccount
```

as separate database tables, the current architecture uses one common
`social_accounts` table.

This makes it possible for one user to have:

``` text
Mastodon account
Instagram account
LinkedIn account
X account
```

without requiring a completely different account-management
implementation for every platform.

------------------------------------------------------------------------

# 8. User ↔ SocialAccount Relationship

The `User` model contains:

``` text
social_accounts
```

with a relationship to `SocialAccount`.

The relationship uses:

``` text
cascade="all, delete-orphan"
```

This means social accounts belong to their SocialPilot user.

Conceptually:

``` text
User #2
 |
 +-- Mastodon
 |
 +-- Instagram
 |
 +-- Future LinkedIn
 |
 +-- Future X
```

This is important for multi-user isolation.

A user should only be able to access their own connected accounts.

------------------------------------------------------------------------

# 9. Authentication

The Mastodon `/connect` endpoint is protected by the existing
SocialPilot authentication system.

The route uses:

``` text
get_current_user
```

The authentication process is:

``` text
Authorization: Bearer <JWT>
             ↓
decode JWT
             ↓
extract "sub"
             ↓
convert subject to user ID
             ↓
retrieve user from database
             ↓
verify user is active
             ↓
current_user
```

This prevents an unauthenticated request from starting a social-account
connection for an arbitrary user.

------------------------------------------------------------------------

# 10. Mastodon OAuth Architecture

The Mastodon OAuth implementation was placed in:

``` text
app/integrations/mastodon/oauth.py
```

This file handles platform-specific OAuth functionality.

It contains functionality for:

``` text
get_mastodon_authorization_url()
exchange_code_for_token()
get_mastodon_account()
```

This keeps Mastodon-specific HTTP/API logic out of the generic
social-account service.

------------------------------------------------------------------------

# 11. Mastodon Authorization Flow

The final intended flow is:

``` text
User logs into SocialPilot
          ↓
GET /social-accounts/mastodon/connect
          ↓
SocialPilot validates JWT
          ↓
Generate OAuth state
          ↓
Create Mastodon authorization URL
          ↓
Redirect user to Mastodon
          ↓
User authorizes application
          ↓
Mastodon redirects to callback
          ↓
Validate OAuth state
          ↓
Exchange authorization code
          ↓
Receive access token
          ↓
Verify Mastodon account
          ↓
Check whether account already exists
          ↓
Create/update SocialAccount
          ↓
Return successful connection response
```

------------------------------------------------------------------------

# 12. OAuth State Problem and Solution

One of the important improvements made during implementation was adding
an OAuth state mechanism.

OAuth state is important because the callback needs to be associated
with the user who initiated the connection.

The project now creates and verifies OAuth state values.

During debugging, we tested:

``` text
_create_oauth_state(2)
```

and verified that the generated state could recover:

``` text
user_id = 2
```

The test produced:

``` text
State created: True
Recovered user: 2
```

This confirmed that the state mechanism was functioning.

### Why this matters

Without appropriate state validation, an OAuth callback could
potentially be associated with the wrong application user.

The state mechanism gives the callback a way to establish:

``` text
OAuth callback
      ↓
Which SocialPilot user initiated this?
      ↓
User #2
```

------------------------------------------------------------------------

# 13. First Routing Problem

Initially, the Mastodon router existed independently, but it was not
correctly visible in the FastAPI application's resolved route list.

A test such as:

``` python
[r.path for r in app.routes if hasattr(r, 'path')]
```

returned only the top-level routes:

``` text
/openapi.json
/docs
/docs/oauth2-redirect
/redoc
/health
/
```

This was confusing because:

``` text
app.api.routes.mastodon.router
```

itself contained:

``` text
/social-accounts/mastodon/connect
/social-accounts/mastodon/callback
```

## Diagnosis

FastAPI internally represented included routers as `_IncludedRouter`
objects in `app.routes`.

Therefore directly checking `r.path` was not a reliable way to inspect
included routes in this situation.

## Better verification

The OpenAPI schema was inspected:

``` python
schema = app.openapi()
[p for p in schema["paths"] if "mastodon" in p]
```

This correctly returned:

``` text
/social-accounts/mastodon/connect
/social-accounts/mastodon/callback
```

### Lesson

When debugging FastAPI route registration, OpenAPI is often a better
verification mechanism than assuming every item in `app.routes` will
directly expose a route path.

------------------------------------------------------------------------

# 14. PowerShell Command-Line Issue

During testing, a Unix-style multiline curl command was initially used:

``` text
\
```

PowerShell interpreted the backslash differently and produced a parser
error.

The solution was to use:

``` text
curl.exe
```

and a normal PowerShell-compatible command.

Example:

``` powershell
curl.exe -v -X GET "http://127.0.0.1:8000/social-accounts/mastodon/connect" -H "Authorization: Bearer YOUR_JWT"
```

### Lesson

Commands copied from Linux/macOS documentation may not work directly in
PowerShell.

For Windows testing, explicitly using:

``` text
curl.exe
```

avoids some PowerShell alias/command parsing confusion.

------------------------------------------------------------------------

# 15. Authentication Test

An initial request returned:

``` json
{
  "detail": "Not authenticated"
}
```

The reason was that the Authorization header being sent in that
particular test did not contain the actual JWT.

A subsequent verbose curl request showed the correct behavior:

``` text
HTTP/1.1 307 Temporary Redirect
```

with a Mastodon authorization URL.

This confirmed:

``` text
JWT authentication
        ↓
Mastodon connect endpoint
        ↓
successful redirect
```

was working.

------------------------------------------------------------------------

# 16. First OAuth Callback Problem

The first full OAuth attempt successfully reached the callback, proving
that the external OAuth flow itself was functioning.

However, the callback failed when trying to check whether the Mastodon
account already existed.

The error was essentially:

``` text
SocialAccountRepository has no attribute
get_by_platform_and_account_id
```

## Root cause

The Mastodon callback needed to perform a lookup using:

``` text
user_id
platform
account_id
```

but the repository did not yet implement that query.

------------------------------------------------------------------------

# 17. Repository Fix

The missing method was added:

``` text
get_by_platform_and_account_id()
```

Its purpose is:

``` text
Find SocialAccount
WHERE
    user_id = current user
    AND platform = Mastodon
    AND account_id = Mastodon account ID
```

This prevents duplicate connections for the same platform account
belonging to the same SocialPilot user.

The method was tested directly with:

``` python
hasattr(
    SocialAccountRepository,
    "get_by_platform_and_account_id"
)
```

and returned:

``` text
True
```

------------------------------------------------------------------------

# 18. Final Mastodon OAuth Test

After the repository fix, the complete OAuth process was executed again.

This time it succeeded.

The result confirmed:

``` text
status: connected
message: Mastodon account connected successfully.
platform: mastodon
account_name: socialpilot_ai
is_active: true
```

The account was stored in the database.

The returned SocialAccount included:

``` text
id: 2
user_id: 2
platform: mastodon
account_name: socialpilot_ai
account_id: 117203384978868329
is_active: true
```

This is the first successful end-to-end Mastodon social-account
integration milestone.

------------------------------------------------------------------------

# 19. Database/API Verification

After OAuth succeeded, the generic endpoint was tested:

``` text
GET /social-accounts
```

with the user's JWT.

The API returned the connected Mastodon account.

This proved that the account was not merely held temporarily in memory.

The full chain was therefore verified:

``` text
Mastodon
   ↓
OAuth
   ↓
access token
   ↓
account verification
   ↓
SocialAccount model
   ↓
PostgreSQL
   ↓
SocialAccount API
```

------------------------------------------------------------------------

# 20. Migration

A migration was added:

``` text
migrations/versions/9f31b34c1261_create_social_accounts_table.py
```

This establishes the database table required for persistent
social-account storage.

This was included in the development commit.

------------------------------------------------------------------------

# 21. Generic Social Account API

The existing generic route provides:

``` text
POST   /social-accounts
GET    /social-accounts
GET    /social-accounts/{account_id}
PATCH  /social-accounts/{account_id}
DELETE /social-accounts/{account_id}
```

This is useful because Mastodon-specific OAuth does not need to reinvent
account CRUD operations.

The Mastodon integration creates the account, while the generic
social-account API can subsequently manage it.

------------------------------------------------------------------------

# 22. Current Architecture

The current architecture can be visualized as:

``` text
                         ┌──────────────────┐
                         │      User        │
                         └────────┬─────────┘
                                  │ JWT
                                  ▼
                    ┌─────────────────────────┐
                    │ FastAPI Authentication  │
                    └────────────┬────────────┘
                                 │
                                 ▼
                    ┌─────────────────────────┐
                    │ Mastodon OAuth Routes   │
                    │                         │
                    │ /connect                │
                    │ /callback               │
                    └────────────┬────────────┘
                                 │
                                 ▼
                    ┌─────────────────────────┐
                    │ Mastodon OAuth Adapter  │
                    │                         │
                    │ authorization URL      │
                    │ token exchange         │
                    │ account verification   │
                    └────────────┬────────────┘
                                 │
                                 ▼
                    ┌─────────────────────────┐
                    │ SocialAccount Service  │
                    └────────────┬────────────┘
                                 │
                                 ▼
                    ┌─────────────────────────┐
                    │ SocialAccount Repo     │
                    └────────────┬────────────┘
                                 │
                                 ▼
                    ┌─────────────────────────┐
                    │ PostgreSQL              │
                    │ social_accounts table   │
                    └─────────────────────────┘
```

------------------------------------------------------------------------

# 23. Why We Kept Generic SocialAccount Logic

A major architectural decision was to avoid making the application
Mastodon-specific.

The reusable portion is:

``` text
SocialAccount
SocialAccountCreate
SocialAccountUpdate
SocialAccountResponse
SocialAccountService
SocialAccountRepository
```

Platform-specific code lives in:

``` text
integrations/mastodon/
integrations/instagram/
future integrations/linkedin/
future integrations/x/
```

This should make future integrations significantly easier.

------------------------------------------------------------------------

# 24. Security Considerations

## 24.1 Access Tokens Are Sensitive

The Mastodon access token was visible during development testing.

This is acceptable as a temporary debugging event, but it must **never**
be committed to Git.

Tokens must not appear in:

``` text
GitHub
README files
source code
screenshots
logs
frontend responses
public documentation
```

If a real token is exposed, it should be revoked/replaced.

------------------------------------------------------------------------

# 25. Important Security Issue Still To Fix

The current generic response schema contains:

``` text
access_token
refresh_token
```

Therefore the `/social-accounts` endpoint currently returns the raw
access token.

That is **not appropriate for production**.

The frontend generally does not need the raw OAuth credential.

A safer response would expose something like:

``` text
id
platform
account_name
account_id
is_active
created_at
```

while keeping:

``` text
access_token
refresh_token
```

server-side only.

This should be fixed before production and preferably before exposing
the social-account API to a real frontend.

------------------------------------------------------------------------

# 26. Where the Application Can Fail

The current system has multiple failure points.

## 26.1 User Is Not Authenticated

Request:

``` text
GET /social-accounts/mastodon/connect
```

without a valid JWT.

Possible result:

``` text
401 Not Authenticated
```

------------------------------------------------------------------------

## 26.2 JWT Is Invalid

If:

-   JWT is expired
-   signature is invalid
-   subject is missing
-   user ID is invalid
-   user does not exist
-   user is inactive

authentication fails.

Expected behavior:

``` text
401 Could not validate credentials
```

------------------------------------------------------------------------

## 26.3 Mastodon Client ID Missing

If:

``` text
mastodon_client_id
```

is not configured:

``` text
500 Mastodon Client ID is not configured
```

------------------------------------------------------------------------

## 26.4 Mastodon Client Secret Missing

If:

``` text
mastodon_client_secret
```

is missing:

``` text
500 Mastodon Client Secret is not configured
```

------------------------------------------------------------------------

## 26.5 Wrong Redirect URI

If the redirect URI configured in Mastodon does not exactly match:

``` text
http://localhost:8000/social-accounts/mastodon/callback
```

OAuth authorization can fail.

This is especially easy to break by changing:

``` text
localhost
```

to:

``` text
127.0.0.1
```

or changing the port.

------------------------------------------------------------------------

## 26.6 OAuth State Missing

If the callback does not contain:

``` text
state
```

the callback should fail.

This protects the OAuth flow from being accepted without proper
correlation.

------------------------------------------------------------------------

## 26.7 Authorization Code Missing

If Mastodon returns no:

``` text
code
```

the callback cannot exchange credentials.

------------------------------------------------------------------------

## 26.8 User Denies Authorization

Mastodon can return an OAuth error.

The callback handles:

``` text
error
error_description
```

and returns an HTTP error instead of attempting to continue.

------------------------------------------------------------------------

## 26.9 Authorization Code Exchange Failure

The token exchange can fail because of:

-   Invalid client ID
-   Invalid client secret
-   Expired authorization code
-   Reused authorization code
-   Wrong redirect URI
-   Incorrect OAuth parameters
-   Mastodon outage
-   Network failure

------------------------------------------------------------------------

## 26.10 Mastodon API Failure

Account verification can fail because:

-   Mastodon is unavailable
-   Network connection fails
-   Access token is invalid
-   Token was revoked
-   API endpoint changes
-   Rate limits are reached

------------------------------------------------------------------------

## 26.11 Database Failure

Account creation can fail because:

-   PostgreSQL is down
-   database connection is unavailable
-   migration has not been applied
-   schema is outdated
-   constraint violation occurs
-   transaction fails

------------------------------------------------------------------------

## 26.12 Duplicate Account

A user could try to connect the same Mastodon account multiple times.

The repository lookup:

``` text
get_by_platform_and_account_id()
```

was added specifically to support duplicate detection.

------------------------------------------------------------------------

## 26.13 Token Expiration / Revocation

The current Mastodon account stores:

``` text
token_expires_at
```

and:

``` text
refresh_token
```

but Mastodon returned:

``` text
refresh_token: null
token_expires_at: null
```

during the tested connection.

Therefore future implementations must not assume that every platform
behaves like a traditional expiring OAuth token system.

------------------------------------------------------------------------

# 27. Important Development Use Cases

## Use Case 1 --- Connect Mastodon

``` text
User
→ Connect Mastodon
→ OAuth authorization
→ account saved
```

------------------------------------------------------------------------

## Use Case 2 --- Multiple Social Accounts

One SocialPilot user could eventually have:

``` text
Mastodon @socialpilot_ai
Instagram @brand_account
LinkedIn Company Page
```

The same generic `SocialAccount` system can represent them.

------------------------------------------------------------------------

## Use Case 3 --- Generate Once, Publish Multiple Times

Eventually:

``` text
AI generates post
        ↓
User approves
        ↓
Mastodon
Instagram
LinkedIn
X
```

Each platform can have its own publishing adapter.

------------------------------------------------------------------------

## Use Case 4 --- Schedule Content

Future architecture:

``` text
Post
 ↓
Scheduled time
 ↓
Worker / scheduler
 ↓
Platform adapter
 ↓
Publish
```

------------------------------------------------------------------------

## Use Case 5 --- Disconnect Account

User calls:

``` text
DELETE /social-accounts/{account_id}
```

The associated social-account record is removed.

------------------------------------------------------------------------

## Use Case 6 --- Temporarily Disable Account

Instead of deleting the account:

``` text
is_active = false
```

can be used.

This is useful if a platform temporarily fails or the user wants to stop
publishing without losing the connection record.

------------------------------------------------------------------------

# 28. What We Deliberately Did NOT Build Yet

The current milestone is **account connection**, not the complete
social-media management system.

Not completed yet:

``` text
Mastodon post publishing
Mastodon media upload
Mastodon scheduling
Mastodon post analytics
Frontend Mastodon connection UI
Frontend publishing UI
Multi-platform publishing
Automatic token recovery
Retry system
Rate-limit handling
Background publishing workers
Advanced error handling
```

These should be implemented incrementally.

------------------------------------------------------------------------

# 29. Change of Development Strategy

The development strategy changed from:

``` text
Try to get every major platform working immediately
```

to:

``` text
Build one complete integration correctly
        ↓
Validate architecture
        ↓
Build reusable publishing abstraction
        ↓
Add additional platforms
```

Mastodon is therefore serving as the first complete reference
implementation.

This is preferable because it lets us test the architecture before
duplicating the same mistakes across several platforms.

------------------------------------------------------------------------

# 30. Git / Version Control Milestone

After the Mastodon integration was completed and verified, the changes
were committed and pushed to:

``` text
dev
```

The final Git state was:

``` text
On branch dev
Your branch is up to date with 'origin/dev'.

nothing to commit, working tree clean
```

This establishes a clean development checkpoint.

This checkpoint should be treated as the stable baseline before
implementing Mastodon publishing.

------------------------------------------------------------------------

# 31. Recommended Next Development Phase

The next phase should be:

## Phase 2 --- Mastodon Publishing

Implement:

``` text
SocialAccount
      ↓
Mastodon publisher
      ↓
POST /api/v1/statuses
      ↓
Mastodon
```

The publishing layer should ideally accept a generic internal
representation:

``` text
Post
 ├── text
 ├── media
 ├── scheduled_at
 └── social_account_id
```

and then route the post to the correct platform adapter.

------------------------------------------------------------------------

# 32. Recommended Future Architecture

Eventually:

``` text
                  SocialPilot Post
                         |
                         ▼
                Publishing Service
                         |
          +--------------+--------------+
          |              |              |
          ▼              ▼              ▼
     Mastodon        Instagram       LinkedIn
      Adapter          Adapter         Adapter
          |              |              |
          ▼              ▼              ▼
      Mastodon         Meta          LinkedIn
        API             API             API
```

The important principle is:

> The core application should not know the low-level details of every
> social-media API.

Instead:

``` text
Core
 ↓
Platform interface
 ↓
Platform adapter
 ↓
External API
```

------------------------------------------------------------------------

# 33. Production Hardening Checklist

Before production, address at least:

-   [ ] Never expose access tokens through normal API responses
-   [ ] Encrypt sensitive tokens at rest
-   [ ] Rotate/revoke exposed development credentials
-   [ ] Validate OAuth state robustly
-   [ ] Store OAuth state securely with expiration
-   [ ] Add proper OAuth error handling
-   [ ] Add database transaction error handling
-   [ ] Add HTTP timeout/retry policies
-   [ ] Handle platform rate limits
-   [ ] Handle revoked tokens
-   [ ] Add structured logging
-   [ ] Avoid logging credentials
-   [ ] Add automated tests
-   [ ] Add integration tests
-   [ ] Add publishing idempotency
-   [ ] Add background jobs for scheduled publishing
-   [ ] Add platform-specific content validation
-   [ ] Add monitoring
-   [ ] Add secret management for production
-   [ ] Review permissions/scopes requested from each platform

------------------------------------------------------------------------

# 34. Current Status

## Completed

``` text
[✓] Generic SocialAccount model
[✓] User ↔ SocialAccount relationship
[✓] SocialAccount schema
[✓] SocialAccount service
[✓] SocialAccount repository
[✓] SocialAccount CRUD API
[✓] Social accounts database migration
[✓] Mastodon configuration
[✓] Mastodon OAuth integration
[✓] OAuth authorization URL
[✓] OAuth state generation
[✓] OAuth state verification
[✓] OAuth callback
[✓] Authorization-code exchange
[✓] Mastodon account verification
[✓] Duplicate-account lookup
[✓] Account persistence
[✓] Authenticated /social-accounts verification
[✓] Git commit
[✓] Push to dev
```

## In Progress / Next

``` text
[ ] Secure SocialAccount response
[ ] Mastodon publishing
[ ] Publishing abstraction
[ ] Frontend account connection
[ ] Frontend post publishing
[ ] Scheduling
[ ] Multi-platform publishing
```

------------------------------------------------------------------------

# 35. Final Development Milestone

The most important result from this phase is not simply that a Mastodon
account connected.

The important result is that we proved the following architecture works:

``` text
SocialPilot User
       ↓
JWT authentication
       ↓
Platform-specific OAuth
       ↓
OAuth state
       ↓
External account verification
       ↓
Generic SocialAccount
       ↓
Repository
       ↓
PostgreSQL
       ↓
Generic SocialAccount API
```

This gives the project a working foundation for adding the actual
publishing functionality.

The next milestone should therefore build on this exact implementation
rather than redesigning the account system again.
