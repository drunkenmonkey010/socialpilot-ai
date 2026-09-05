# SocialPilot AI --- Development Progress & Technical Decision Log

## 1. Purpose of This Document

This document records everything completed so far for the social-media
integration and publishing infrastructure portion of **SocialPilot AI**,
including:

- What we originally planned
- What changed and why
- Technologies and platforms considered
- Problems encountered
- How each problem was diagnosed and fixed
- Architecture decisions
- Current implementation state
- Important use cases
- Failure/crash scenarios
- Security concerns
- Testing and verification
- What should be done next

This is a development-history document for the project. It is intentionally
detailed so that future development can continue without losing the reasoning
behind earlier decisions.

The document is a **living technical log** and should be updated whenever a
major implementation, architectural decision, failure, or milestone is
completed.

------------------------------------------------------------------------

# 2. Original Goal

The broader goal of SocialPilot AI is to build an **agentic AI
social-media management platform**.

The intended application flow is:

```text
User
  ↓
SocialPilot AI
  ↓
Connect social-media accounts
  ↓
Create / generate content
  ↓
Human review
  ↓
Select platform(s)
  ↓
Publish / schedule
  ↓
Background workers
  ↓
Social-media platform APIs
  ↓
Analytics / feedback
```

The social-account and publishing layers therefore need to support:

- Connecting external social-media accounts
- Securely storing account information and OAuth credentials
- Associating every social account with the correct SocialPilot user
- Reusing connected accounts when creating posts
- Generating platform-aware content
- Requiring human approval before publication
- Publishing posts through platform APIs
- Scheduling posts for future publication
- Retrying transient publishing failures
- Recovering stale background jobs
- Eventually supporting multiple platforms through a common abstraction
- Eventually collecting analytics and feedback

The first major integration attempt did not end up being the final platform
choice.

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

```text
X
 ↓
DROP FOR DEVELOPMENT
```

The plan is to potentially bring X back later during production if the
project's budget and API requirements justify it.

### Why this decision was made

The priority during development is:

- Keep the project free/low-cost
- Avoid unnecessary external API expenses
- Get the architecture working with a platform that permits
  development/testing
- Avoid locking the entire project around a paid API

Therefore, X was intentionally removed from the current development path.

------------------------------------------------------------------------

# 4. Meta / Instagram --- Problem Encountered

Instagram/Meta was also part of the planned social-media integrations.

A basic Instagram route already existed:

```text
app/api/routes/instagram.py
```

The project also had Instagram configuration fields:

```text
instagram_app_id
instagram_app_secret
instagram_redirect_uri
```

However, the Meta/Instagram integration was not progressing reliably
enough for the current development stage.

Meta developer registration and verification requirements created external
configuration/verification blockers.

Rather than spending excessive time blocking the entire social-account and
publishing architecture on Meta's configuration/API requirements, we
decided to use another platform for development.

This led to the Mastodon decision.

Instagram remains a future integration.

------------------------------------------------------------------------

# 5. Mastodon --- Development Platform Decision

Mastodon was selected as the current development platform because it
provides a practical OAuth/API environment for testing the social-account
and publishing architecture without making the project dependent on X's
paid API requirements.

The development instance used is:

```text
https://mastodon.social
```

The project was configured around:

```text
mastodon_instance_url
mastodon_client_id
mastodon_client_secret
mastodon_redirect_uri
```

The redirect URI currently used is:

```text
http://localhost:8000/social-accounts/mastodon/callback
```

### Important architectural decision

Mastodon is being used as a **development implementation of the generic
social-account and publishing architecture**, not as a statement that
Mastodon is the only platform SocialPilot AI will ever support.

The intended architecture is:

```text
                 SocialPilot AI
                       |
          +------------+------------+
          |            |            |
      Instagram     Mastodon       X
          |            |            |
       Adapter       Adapter      Adapter
```

The common SocialAccount model/service and future publishing abstraction are
intended to keep platform-specific logic separated from the generic
application layer.

------------------------------------------------------------------------

# 6. Existing Social Account Architecture

Before Mastodon was fully connected, the project already had the foundation
for a generic social-account system.

The relevant layers are:

```text
app/
├── api/
│   └── routes/
│       ├── mastodon.py
│       ├── instagram.py
│       ├── social_account.py
│       └── post.py
│
├── integrations/
│   ├── mastodon/
│   │   └── oauth.py
│   └── queue/
│       └── redis.py
│
├── models/
│   ├── social_account.py
│   ├── user.py
│   └── post.py
│
├── repositories/
│   ├── social_account.py
│   └── post.py
│
├── schemas/
│   ├── social_account.py
│   └── post.py
│
├── services/
│   ├── social_account.py
│   ├── post.py
│   └── ai_content.py
│
└── worker/
    ├── scheduler.py
    ├── publisher.py
    ├── recovery.py
    └── retry_promoter.py
```

This separation is intentional.

------------------------------------------------------------------------

# 7. SocialAccount Database Model

The project contains a generic `SocialAccount` model.

Important fields include:

```text
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

```text
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

```text
MastodonAccount
InstagramAccount
XAccount
LinkedInAccount
```

as separate database tables, the current architecture uses one common
`social_accounts` table.

This makes it possible for one user to have:

```text
Mastodon account
Instagram account
LinkedIn account
X account
```

without requiring a completely different account-management implementation
for every platform.

------------------------------------------------------------------------

# 8. User ↔ SocialAccount Relationship

The `User` model contains:

```text
social_accounts
```

with a relationship to `SocialAccount`.

The relationship uses:

```text
cascade="all, delete-orphan"
```

This means social accounts belong to their SocialPilot user.

Conceptually:

```text
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

The Mastodon `/connect` endpoint is protected by the existing SocialPilot
authentication system.

The route uses:

```text
get_current_user
```

The authentication process is:

```text
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

The same ownership model is applied to campaigns, posts, and social accounts.

------------------------------------------------------------------------

# 10. Mastodon OAuth Architecture

The Mastodon OAuth implementation was placed in:

```text
app/integrations/mastodon/oauth.py
```

This file handles platform-specific OAuth functionality.

It contains functionality for:

```text
get_mastodon_authorization_url()
exchange_code_for_token()
get_mastodon_account()
publish_mastodon_status()
```

This keeps Mastodon-specific HTTP/API logic out of the generic
social-account service.

------------------------------------------------------------------------

# 11. Mastodon Authorization Flow

The final intended flow is:

```text
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

OAuth state is important because the callback needs to be associated with
the user who initiated the connection.

The project now creates and verifies OAuth state values.

During debugging, we tested:

```text
_create_oauth_state(2)
```

and verified that the generated state could recover:

```text
user_id = 2
```

The test produced:

```text
State created: True
Recovered user: 2
```

This confirmed that the state mechanism was functioning.

### Why this matters

Without appropriate state validation, an OAuth callback could potentially
be associated with the wrong application user.

The state mechanism gives the callback a way to establish:

```text
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

```python
[r.path for r in app.routes if hasattr(r, 'path')]
```

returned only the top-level routes:

```text
/openapi.json
/docs
/docs/oauth2-redirect
/redoc
/health
/
```

This was confusing because:

```text
app.api.routes.mastodon.router
```

itself contained:

```text
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

```python
schema = app.openapi()

[p for p in schema["paths"] if "mastodon" in p]
```

This correctly returned:

```text
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

```text
\
```

PowerShell interpreted the backslash differently and produced a parser
error.

The solution was to use:

```text
curl.exe
```

and a normal PowerShell-compatible command.

Example:

```powershell
curl.exe -v -X GET "http://127.0.0.1:8000/social-accounts/mastodon/connect" -H "Authorization: Bearer YOUR_JWT"
```

### Lesson

Commands copied from Linux/macOS documentation may not work directly in
PowerShell.

For Windows testing, explicitly using:

```text
curl.exe
```

avoids some PowerShell alias/command parsing confusion.

------------------------------------------------------------------------

# 15. Authentication Test

An initial request returned:

```json
{
  "detail": "Not authenticated"
}
```

The reason was that the Authorization header being sent in that particular
test did not contain the actual JWT.

A subsequent verbose curl request showed the correct behavior:

```text
HTTP/1.1 307 Temporary Redirect
```

with a Mastodon authorization URL.

This confirmed:

```text
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

```text
SocialAccountRepository has no attribute
get_by_platform_and_account_id
```

## Root cause

The Mastodon callback needed to perform a lookup using:

```text
user_id
platform
account_id
```

but the repository did not yet implement that query.

------------------------------------------------------------------------

# 17. Repository Fix

The missing method was added:

```text
get_by_platform_and_account_id()
```

Its purpose is:

```text
Find SocialAccount

WHERE

    user_id = current user
    AND platform = Mastodon
    AND account_id = Mastodon account ID
```

This prevents duplicate connections for the same platform account belonging
to the same SocialPilot user.

The method was tested directly with:

```python
hasattr(
    SocialAccountRepository,
    "get_by_platform_and_account_id"
)
```

and returned:

```text
True
```

------------------------------------------------------------------------

# 18. Final Mastodon OAuth Test

After the repository fix, the complete OAuth process was executed again.

This time it succeeded.

The result confirmed:

```text
status: connected

message: Mastodon account connected successfully.

platform: mastodon

account_name: socialpilot_ai

is_active: true
```

The account was stored in the database.

The returned SocialAccount included:

```text
id: 2
user_id: 2
platform: mastodon
account_name: socialpilot_ai
account_id: 117203384978868329
is_active: true
```

This was the first successful end-to-end Mastodon social-account integration
milestone.

------------------------------------------------------------------------

# 19. Database/API Verification

After OAuth succeeded, the generic endpoint was tested:

```text
GET /social-accounts
```

with the user's JWT.

The API returned the connected Mastodon account.

This proved that the account was not merely held temporarily in memory.

The full chain was therefore verified:

```text
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

```text
migrations/versions/9f31b34c1261_create_social_accounts_table.py
```

This establishes the database table required for persistent social-account
storage.

This was included in the development commit.

------------------------------------------------------------------------

# 21. Generic Social Account API

The existing generic route provides:

```text
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

The architecture has now expanded beyond account connection into content
generation, human approval, scheduling, Redis-based background processing,
and publishing.

The current high-level architecture is:

```text
                         User
                           │
                           ▼
                    FastAPI / JWT
                           │
             ┌─────────────┴─────────────┐
             │                           │
             ▼                           ▼
        Brand/Campaign               Social Accounts
             │                           │
             ▼                           ▼
        AI Generation                OAuth Adapters
             │                           │
             ▼                           ▼
           DRAFT                    Mastodon
             │
             ▼
      HUMAN REVIEW GATE
             │
      ┌──────┴──────┐
      │             │
   REJECT         APPROVE
      │             │
      ▼             ▼
   REJECTED      APPROVED
                    │
                    ▼
                SCHEDULED
                    │
                    ▼
             Database Scheduler
                    │
                    ▼
             PostgreSQL Claim
                    │
                    ▼
             Redis Main Queue
                    │
                    ▼
          Redis Processing Queue
                    │
                    ▼
             Publisher Worker
                    │
                    ▼
              Mastodon API
                    │
             ┌──────┴──────┐
             │             │
          SUCCESS       FAILURE
             │             │
             ▼             ▼
         PUBLISHED    Retry Decision
                           │
                    ┌──────┴──────┐
                    │             │
                 Permanent     Transient
                    │             │
                    ▼             ▼
                 FAILED      Delayed Retry
                                  │
                                  ▼
                           Retry Promoter
                                  │
                                  ▼
                             Main Queue

                    Recovery Worker
                           │
                           ▼
                    Stale Job Recovery
```

PostgreSQL remains the source of truth for application state.

Redis is used for queueing and worker coordination.

------------------------------------------------------------------------

# 23. Why We Kept Generic SocialAccount Logic

A major architectural decision was to avoid making the application
Mastodon-specific.

The reusable portion is:

```text
SocialAccount
SocialAccountCreate
SocialAccountUpdate
SocialAccountResponse
SocialAccountService
SocialAccountRepository
```

Platform-specific code lives in:

```text
integrations/mastodon/
integrations/instagram/
future integrations/linkedin/
future integrations/x/
```

The same principle is now being applied to publishing.

The intended future publishing structure is:

```text
Post
  ↓
Publishing Service
  ↓
Platform Publisher Interface
  ↓
Platform Adapter
  ↓
External API
```

------------------------------------------------------------------------

# 24. Security Considerations

## 24.1 Access Tokens Are Sensitive

The Mastodon access token was visible during development testing.

This is acceptable as a temporary debugging event, but it must **never**
be committed to Git.

Tokens must not appear in:

```text
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

# 25. Security Issue Fixed

The original generic response schema exposed:

```text
access_token
refresh_token
```

through normal social-account API responses.

This was identified as inappropriate for production.

The API response was subsequently hardened so that normal social-account
responses do not expose OAuth access tokens.

The intended public-facing account information is:

```text
id
platform
account_name
account_id
is_active
created_at
updated_at
```

while sensitive credentials remain server-side.

Verification confirmed that:

```text
GET /social-accounts
```

does not expose the access token.

This security fix is considered completed.

------------------------------------------------------------------------

# 26. Where the Application Can Fail

The current system has multiple failure points.

## 26.1 User Is Not Authenticated

Request:

```text
GET /social-accounts/mastodon/connect
```

without a valid JWT.

Possible result:

```text
401 Not Authenticated
```

------------------------------------------------------------------------

## 26.2 JWT Is Invalid

If:

- JWT is expired
- signature is invalid
- subject is missing
- user ID is invalid
- user does not exist
- user is inactive

authentication fails.

Expected behavior:

```text
401 Could not validate credentials
```

------------------------------------------------------------------------

## 26.3 Mastodon Client ID Missing

If:

```text
mastodon_client_id
```

is not configured, the OAuth flow cannot begin.

------------------------------------------------------------------------

## 26.4 Mastodon Client Secret Missing

If:

```text
mastodon_client_secret
```

is missing, authorization-code exchange cannot succeed.

------------------------------------------------------------------------

## 26.5 Wrong Redirect URI

If the redirect URI configured in Mastodon does not exactly match:

```text
http://localhost:8000/social-accounts/mastodon/callback
```

OAuth authorization can fail.

This is especially easy to break by changing:

```text
localhost
```

to:

```text
127.0.0.1
```

or changing the port.

------------------------------------------------------------------------

## 26.6 OAuth State Missing or Invalid

If the callback does not contain a valid:

```text
state
```

the callback should fail.

This protects the OAuth flow from being accepted without proper
correlation.

------------------------------------------------------------------------

## 26.7 Authorization Code Missing

If Mastodon returns no:

```text
code
```

the callback cannot exchange credentials.

------------------------------------------------------------------------

## 26.8 User Denies Authorization

Mastodon can return an OAuth error.

The callback handles:

```text
error
error_description
```

and returns an HTTP error instead of attempting to continue.

------------------------------------------------------------------------

## 26.9 Authorization Code Exchange Failure

The token exchange can fail because of:

- Invalid client ID
- Invalid client secret
- Expired authorization code
- Reused authorization code
- Wrong redirect URI
- Incorrect OAuth parameters
- Mastodon outage
- Network failure

------------------------------------------------------------------------

## 26.10 Mastodon API Failure

Account verification or publication can fail because:

- Mastodon is unavailable
- Network connection fails
- Access token is invalid
- Token was revoked
- API endpoint changes
- Rate limits are reached

------------------------------------------------------------------------

## 26.11 Database Failure

Account creation, scheduling, or publishing-state updates can fail because:

- PostgreSQL is down
- database connection is unavailable
- migration has not been applied
- schema is outdated
- constraint violation occurs
- transaction fails

------------------------------------------------------------------------

## 26.12 Duplicate Account

A user could try to connect the same Mastodon account multiple times.

The repository lookup:

```text
get_by_platform_and_account_id()
```

was added specifically to support duplicate detection.

------------------------------------------------------------------------

## 26.13 Token Expiration / Revocation

The current Mastodon account stores:

```text
token_expires_at
```

and:

```text
refresh_token
```

but Mastodon returned:

```text
refresh_token: null
token_expires_at: null
```

during the tested connection.

Therefore future implementations must not assume that every platform behaves
like a traditional expiring OAuth token system.

------------------------------------------------------------------------

# 27. Important Development Use Cases

## Use Case 1 --- Connect Mastodon

```text
User
→ Connect Mastodon
→ OAuth authorization
→ account saved
```

------------------------------------------------------------------------

## Use Case 2 --- Multiple Social Accounts

One SocialPilot user could eventually have:

```text
Mastodon @socialpilot_ai
Instagram @brand_account
LinkedIn Company Page
```

The same generic `SocialAccount` system can represent them.

------------------------------------------------------------------------

## Use Case 3 --- Generate Content With AI

```text
Brand
  ↓
Campaign
  ↓
AI generation
  ↓
Platform-aware draft
  ↓
Post created as DRAFT
```

The generated post is not automatically published.

------------------------------------------------------------------------

## Use Case 4 --- Human Approval

```text
DRAFT
  ↓
PENDING_REVIEW
  ↓
Human Review
  ├── REJECTED
  └── APPROVED
```

This is a permanent architecture boundary.

AI generation must not bypass human approval.

------------------------------------------------------------------------

## Use Case 5 --- Schedule Content

```text
APPROVED
   ↓
SCHEDULED
   ↓
Database-backed scheduler
   ↓
Redis queue
   ↓
Publisher worker
   ↓
Mastodon
```

------------------------------------------------------------------------

## Use Case 6 --- Retry Failed Scheduled Publication

For transient platform failures:

```text
PUBLISHING
   ↓
Transient Failure
   ↓
Retry Decision
   ↓
Delayed Retry Queue
   ↓
Retry Promoter
   ↓
Main Queue
   ↓
Publisher
```

The current retry policy allows a maximum of five attempts with exponential
backoff.

------------------------------------------------------------------------

## Use Case 7 --- Recover Crashed Worker

If a publisher worker crashes while a job remains in the processing queue:

```text
Processing Queue
       ↓
Stale Job Detected
       ↓
Recovery Worker
       ↓
Check PostgreSQL State
       ↓
Recover Specific Redis Job
       ↓
Main Queue
```

The recovery process is deliberately database-aware.

------------------------------------------------------------------------

## Use Case 8 --- Prevent Duplicate Publication

This is the next major reliability use case.

The current risk is:

```text
Publisher
   ↓
Mastodon successfully publishes
   ↓
Worker crashes
   ↓
Database still says PUBLISHING
   ↓
Redis job is recovered
   ↓
Publisher retries
   ↓
Potential duplicate post
```

Publishing idempotency is therefore the next reliability milestone.

------------------------------------------------------------------------

# 28. What We Deliberately Did NOT Build Yet

The project has now progressed significantly beyond the original account
connection milestone.

The following are still not fully completed:

```text
Publishing idempotency
Advanced platform error classification
HTTP 429 Retry-After handling
Retry jitter
Dead-letter queue
Multi-platform publishing
Instagram publishing
X production integration
Post analytics
Frontend approval UI
Frontend calendar UI
AI quality/safety layer
Advanced agentic workflow
```

The following are already implemented:

```text
Mastodon OAuth
Mastodon publishing
Post lifecycle
Human-in-the-Loop approval
Database-backed scheduling
Redis queue
Redis processing queue
Redis acknowledgement
Retry infrastructure
Delayed retry queue
Retry promoter
Stale-job recovery
Real scheduled Mastodon E2E publishing
```

------------------------------------------------------------------------

# 29. Change of Development Strategy

The development strategy changed from:

```text
Try to get every major platform working immediately
```

to:

```text
Build one complete integration correctly
        ↓
Validate architecture
        ↓
Build reliable scheduling/publishing
        ↓
Harden failure handling
        ↓
Build reusable publishing abstraction
        ↓
Add additional platforms
```

Mastodon is therefore serving as the first complete reference implementation.

This is preferable because it lets us test the architecture before
duplicating the same mistakes across several platforms.

------------------------------------------------------------------------

# 30. Git / Version Control Milestones

The project is being developed on:

```text
dev
```

Major completed development checkpoints include:

```text
feat: add Redis scheduled publishing workers

feat: add reliable Redis job acknowledgement

feat: add stale Redis job recovery

7622c38 feat: add scheduled publishing retries
```

The retry infrastructure milestone was committed as:

```text
7622c38 feat: add scheduled publishing retries
```

Git checkpoints are used to preserve stable development states before moving
to the next major architectural milestone.

------------------------------------------------------------------------

# 31. Mastodon Publishing Implementation

Mastodon publishing was implemented through:

```text
app/integrations/mastodon/oauth.py
```

The publishing function sends the post content to the Mastodon status
endpoint using the connected account's access token.

The internal publishing flow is:

```text
Approved Post
      ↓
PUBLISHING
      ↓
Mastodon Publisher
      ↓
Mastodon API
      ↓
Successful response
      ↓
PUBLISHED
      ↓
published_at recorded
```

The implementation verifies that Mastodon returns a status ID before
considering the publication successful.

If publication fails, the service records the appropriate failure state
according to whether the operation is a manual publication or a scheduled
worker publication.

------------------------------------------------------------------------

# 32. Post Lifecycle and Human-in-the-Loop Architecture

The post lifecycle was formalized using explicit states:

```text
DRAFT
PENDING_REVIEW
APPROVED
REJECTED
SCHEDULED
PUBLISHING
PUBLISHED
FAILED
```

The intended workflow is:

```text
DRAFT
  ↓
PENDING_REVIEW
  ↓
APPROVED
  ↓
SCHEDULED
  ↓
PUBLISHING
  ↓
PUBLISHED
```

Alternative review path:

```text
PENDING_REVIEW
  ↓
REJECTED
  ↓
Edit
  ↓
PENDING_REVIEW
```

The Human-in-the-Loop boundary is a core security and product requirement.

AI generation can create drafts, but AI does not receive direct authority
to publish.

------------------------------------------------------------------------

# 33. Database-Backed Scheduling

Scheduling was implemented using PostgreSQL as the source of truth.

The scheduler searches for posts whose state is:

```text
SCHEDULED
```

and whose:

```text
scheduled_at <= current UTC time
```

A scheduled post is atomically claimed using a database update:

```text
SCHEDULED
    ↓
PUBLISHING
```

before it is placed onto the Redis queue.

This prevents multiple scheduler workers from independently claiming the
same scheduled post.

The scheduling state transition is therefore:

```text
APPROVED
   ↓
SCHEDULED
   ↓
PUBLISHING
```

------------------------------------------------------------------------

# 34. Redis Scheduled Publishing Infrastructure

Redis was introduced as the background queue/coordination layer.

The system uses:

```text
socialpilot:scheduled_posts
```

as the main scheduled-post queue.

A processing queue is also used:

```text
socialpilot:scheduled_posts:processing
```

The basic flow is:

```text
Post Scheduler
      ↓
Redis Main Queue
      ↓
Redis Processing Queue
      ↓
Publisher Worker
      ↓
Mastodon
```

PostgreSQL remains the source of truth.

Redis is not treated as the authoritative database for post state.

------------------------------------------------------------------------

# 35. Reliable Redis Queue and Acknowledgement

The initial queue implementation used blocking Redis operations and
encountered timeout behavior when the queue was empty.

The Redis client was changed to use:

```text
socket_timeout=None
socket_connect_timeout=5
```

This allows the publisher to safely wait for new jobs.

Reliable processing was then implemented using a main queue and a processing
queue.

The publisher moves a job into processing before attempting publication.

On successful completion:

```text
Processing Queue
      ↓
Acknowledgement
      ↓
Job Removed
```

This provides substantially better crash/recovery behavior than immediately
removing a job from the queue before publication succeeds.

------------------------------------------------------------------------

# 36. Retry and Exponential Backoff

Transient publishing failures were identified as an important reliability
problem.

A scheduled publishing failure should not immediately become a permanent
failure when the underlying issue may be temporary.

The system therefore introduced retry metadata:

```text
attempts
next_retry_at
claimed_at
```

The current retry policy is:

```text
Maximum attempts: 5

Initial backoff: 30 seconds

Retry delays:

Attempt 1 → 30 seconds
Attempt 2 → 60 seconds
Attempt 3 → 120 seconds
Attempt 4 → 240 seconds

Final failure → FAILED
```

The architecture distinguishes between:

```text
Transient failure
     ↓
Retry

Permanent failure
     ↓
FAILED
```

The `ScheduledPublishError` exception carries whether a scheduled
publication failure is retryable.

------------------------------------------------------------------------

# 37. Delayed Retry Queue and Retry Promoter

Retry metadata alone was not sufficient because the main Redis queue would
otherwise immediately receive a retry.

A delayed retry mechanism was therefore introduced.

The architecture is:

```text
Redis Main Queue
      ↓
Processing Queue
      ↓
Transient Failure
      ↓
Delayed Retry Sorted Set
      ↓
Retry Promoter
      ↓
Redis Main Queue
      ↓
Publisher
```

The delayed retry queue is implemented using a Redis sorted set whose score
represents the retry timestamp.

The retry promoter periodically checks for jobs whose retry timestamp has
been reached.

This prevents a retry from being processed before its intended backoff
period.

------------------------------------------------------------------------

# 38. Stale Job Recovery

A worker can crash after taking ownership of a Redis job.

Without recovery, the job could remain permanently stuck in the processing
queue.

A dedicated recovery worker was therefore introduced:

```text
app/worker/recovery.py
```

The recovery worker:

1. Finds processing jobs.
2. Checks their `claimed_at` timestamp.
3. Determines whether the job is stale.
4. Loads the corresponding post from PostgreSQL.
5. Checks the authoritative database state.
6. Recovers only the specific eligible Redis job.

The recovery worker does not blindly requeue every stale Redis job.

The PostgreSQL state check is important because the external publication may
already have succeeded even if the worker that performed it later crashed.

------------------------------------------------------------------------

# 39. Atomic Redis State Transitions

A potential reliability issue was identified in the transition between
Redis queues.

If a job were removed from the processing queue and the application crashed
before inserting it into the next queue, the job could be lost.

Retry requeue and stale-job recovery were therefore changed to use Redis
transactional pipelines.

Conceptually:

```text
Processing Queue
      │
      ├── remove job
      │
      └── add job to next queue
```

These transitions are executed through a Redis transaction so the processing
to next-state operation is substantially safer.

This was an important step toward production-grade background processing.

------------------------------------------------------------------------

# 40. Real Scheduled Mastodon End-to-End Test

A complete real-world scheduled publishing test was successfully performed.

The test post was:

```text
Testing SocialPilot AI scheduled publishing with Redis! 🚀 #SocialPilotAI #Redis
```

The post passed through the actual workflow:

```text
DRAFT
  ↓
PENDING_REVIEW
  ↓
APPROVED
  ↓
SCHEDULED
  ↓
Database Scheduler
  ↓
PUBLISHING
  ↓
Redis Main Queue
  ↓
Redis Processing Queue
  ↓
Publisher Worker
  ↓
Mastodon API
  ↓
PUBLISHED
```

The resulting post was visibly present on the connected Mastodon account.

This was important because it verified the **external side effect**, not
merely an internal database status.

The test therefore confirmed that the scheduled publishing infrastructure
works end-to-end with a real external social platform.

------------------------------------------------------------------------

# 41. Retry Infrastructure Testing

The retry infrastructure was tested independently before and alongside the
real E2E workflow.

The validation covered:

```text
Redis connectivity
        ↓
Main queue insertion
        ↓
Processing queue movement
        ↓
Attempt metadata
        ↓
Retry metadata
        ↓
Delayed retry storage
        ↓
Retry promotion
        ↓
Publisher consumption
        ↓
Acknowledgement
        ↓
Queue cleanup
```

The following checks were run:

```powershell
python -m py_compile .\app\integrations\queue\redis.py
python -m py_compile .\app\worker\publisher.py
python -m py_compile .\app\worker\recovery.py
python -m py_compile .\app\worker\retry_promoter.py
python -m pytest -v
```

The existing automated test suite returned:

```text
4 passed
```

Dedicated Redis retry tests also verified:

- Retry attempt metadata is preserved.
- Delayed jobs are not promoted before their retry timestamp.
- Due retry jobs are promoted into the main queue.
- The publisher can receive a promoted retry.
- Successfully processed retry jobs can be acknowledged.
- Processing and delayed queues can be cleaned after successful completion.

------------------------------------------------------------------------

# 42. Current Failure Classification

Scheduled publication failures are currently classified into two broad
categories:

```text
Retryable
```

and:

```text
Permanent
```

Retryable failures include transient conditions such as:

```text
Network failures
Timeouts
HTTP 429
HTTP 5xx
```

Permanent failures include conditions such as:

```text
Unsupported platform
Missing social account
Inactive social account
Invalid scheduled state
```

The current implementation still has room for improvement because some
classification logic relies partly on exception-message parsing.

Future work should introduce typed platform exceptions and explicit
`httpx` exception handling.

------------------------------------------------------------------------

# 43. Current Architecture Rules

The following architectural rules should be preserved going forward.

## Rule 1 --- PostgreSQL Is the Source of Truth

Redis is for:

```text
queueing
coordination
temporary job metadata
```

PostgreSQL remains authoritative for:

```text
post status
campaign ownership
brand ownership
social-account ownership
publication state
```

------------------------------------------------------------------------

## Rule 2 --- Human Approval Is Mandatory

AI must not directly publish content.

The boundary remains:

```text
AI
 ↓
DRAFT
 ↓
HUMAN REVIEW
 ↓
APPROVED
 ↓
SCHEDULED
 ↓
PUBLISH
```

------------------------------------------------------------------------

## Rule 3 --- Platform Logic Must Stay Isolated

Mastodon-specific HTTP/API logic should remain inside the Mastodon
integration layer.

The core application should not contain platform-specific API details.

------------------------------------------------------------------------

## Rule 4 --- Workers Must Be Recoverable

A worker crash must not permanently lose a scheduled job.

This is why the architecture includes:

```text
processing queue
retry mechanism
delayed retry queue
recovery worker
```

------------------------------------------------------------------------

## Rule 5 --- External Side Effects Need Idempotency

The system must eventually assume that:

```text
External API succeeds
```

and:

```text
Internal database update succeeds
```

are not one atomic transaction.

Therefore publication idempotency is required before claiming the system is
fully production-safe.

------------------------------------------------------------------------

# 44. Production Hardening Checklist

Before production, address at least:

- [x] Avoid exposing access tokens through normal API responses
- [ ] Encrypt sensitive tokens at rest
- [ ] Rotate/revoke exposed development credentials
- [x] Validate OAuth state
- [ ] Store OAuth state securely with expiration
- [x] Add OAuth error handling
- [ ] Add comprehensive database transaction error handling
- [x] Add HTTP timeout handling
- [x] Add basic retry behavior
- [ ] Improve typed retry/error classification
- [ ] Handle platform rate limits with `Retry-After`
- [ ] Add retry jitter
- [x] Add background publishing workers
- [x] Add stale-job recovery
- [ ] Add publishing idempotency
- [ ] Add dead-letter queue
- [ ] Add database-level publication attempt tracking
- [ ] Add platform-specific content validation
- [ ] Add structured logging
- [ ] Add monitoring/metrics
- [ ] Add audit logging
- [ ] Add production secret management
- [ ] Review permissions/scopes requested from each platform
- [ ] Add multi-platform publishing
- [ ] Add analytics

------------------------------------------------------------------------

# 45. Current Verified Status

The current project status is:

```text
Authentication                         ✅ VERIFIED
User ownership                         ✅ VERIFIED
Brands                                 ✅ VERIFIED
Campaigns                              ✅ VERIFIED
Posts / lifecycle                      ✅ VERIFIED
Human-in-the-Loop approval             ✅ VERIFIED
AI content generation                  ✅ VERIFIED
Ollama local LLM integration           ✅ VERIFIED
Mastodon OAuth                         ✅ VERIFIED
Mastodon publishing                    ✅ VERIFIED
Database-backed scheduler              ✅ VERIFIED
Redis main queue                       ✅ VERIFIED
Redis processing queue                 ✅ VERIFIED
Redis acknowledgement                  ✅ VERIFIED
Stale-job recovery worker              ✅ VERIFIED
Retry/backoff metadata                 ✅ VERIFIED
Delayed retry queue                    ✅ VERIFIED
Retry promoter worker                  ✅ VERIFIED
Real scheduled Mastodon E2E            ✅ VERIFIED
Publishing idempotency                 ⏳ NEXT
AI quality/safety checks               ⏳
Frontend review/calendar UI            ⏳
Multi-platform publishing              ⏳
Analytics                              ⏳
Advanced agentic workflow              ⏳
```

------------------------------------------------------------------------

# 46. Development Milestones

## Milestone 1 — Social Account Foundation

Implemented:

- Model
- Repository
- Service
- Schemas
- Routes
- Migration
- User relationship

------------------------------------------------------------------------

## Milestone 2 — Mastodon OAuth

Implemented:

- Configuration
- Authorization URL
- Callback
- Token exchange
- Account verification
- State handling
- Account persistence

Fixed:

- Missing client ID
- Missing repository lookup method
- OAuth callback/account lookup issues

------------------------------------------------------------------------

## Milestone 3 — Post Lifecycle

Implemented:

- Explicit status enum
- Editable-state rules
- Review submission
- Approval
- Rejection
- Scheduling state
- Publishing state
- Failure state

------------------------------------------------------------------------

## Milestone 4 — Human-in-the-Loop

Verified:

```text
DRAFT
  ↓
PENDING_REVIEW
  ↓
APPROVED
```

The approval boundary is now a permanent part of the architecture.

------------------------------------------------------------------------

## Milestone 5 — Real Mastodon Publishing

Implemented:

- Mastodon status publisher
- Publishing service logic
- `/publish` endpoint
- Mastodon API integration

Verified:

```text
APPROVED
  ↓
PUBLISHING
  ↓
PUBLISHED
```

The actual post appeared on Mastodon.

------------------------------------------------------------------------

## Milestone 6 — Security Hardening

Implemented:

- Removal of OAuth tokens from normal API responses.

Verified:

```text
GET /social-accounts
```

does not expose the access token.

------------------------------------------------------------------------

## Milestone 7 — Redis Scheduled Publishing Infrastructure and Retries

### Goal

Move scheduled publication out of the API process into reliable background
workers while handling transient publishing failures without immediately
losing the post.

### Files involved

```text
app/integrations/queue/redis.py
app/services/post.py
app/worker/scheduler.py
app/worker/publisher.py
app/worker/recovery.py
app/worker/retry_promoter.py
```

### Architecture

```text
PostgreSQL
    ↓
Scheduler
    ↓
Atomic SCHEDULED → PUBLISHING claim
    ↓
Redis Main Queue
    ↓
Processing Queue
    ↓
Publisher
    ↓
Mastodon
```

Transient failures:

```text
Publisher
    ↓
Transient Failure
    ↓
Delayed Retry Sorted Set
    ↓
Retry Promoter
    ↓
Main Queue
```

Recovery:

```text
Processing Queue
    ↓
Recovery Worker
    ↓
PostgreSQL State Check
    ↓
Specific Job Recovery
```

### Retry policy

```text
Maximum attempts: 5

30s
60s
120s
240s
Final failure → FAILED
```

### Problems solved

1. Redis empty-queue timeout behavior.
2. Reliable processing queue.
3. Redis job acknowledgement.
4. Delayed retry scheduling.
5. Unsafe generic stale-job recovery.
6. Retry metadata preservation.
7. Atomic Redis retry/recovery transitions.

------------------------------------------------------------------------

## Milestone 8 — Real Scheduled Publishing Verification

### Goal

Verify that the entire scheduled publishing system works with a real
external social platform.

### Result

A real Mastodon post successfully travelled through:

```text
DRAFT
  ↓
PENDING_REVIEW
  ↓
APPROVED
  ↓
SCHEDULED
  ↓
PUBLISHING
  ↓
Redis
  ↓
Publisher Worker
  ↓
Mastodon API
  ↓
PUBLISHED
```

The post was visibly present on the connected Mastodon account.

This confirms the complete scheduled publishing vertical slice.

### Significance

This was the first verification that the system could perform a real
scheduled external publication through the complete background-worker
architecture.

------------------------------------------------------------------------

# 47. Current Known Limitations

The current implementation is a strong development-stage publishing
pipeline, but it is not yet fully production-grade.

## 47.1 Idempotency

The largest remaining reliability issue is duplicate external publication.

Potential scenario:

```text
Mastodon API
    ↓
Publication succeeds
    ↓
Worker crashes before DB acknowledgement
    ↓
Recovery/retry
    ↓
Publication attempted again
```

The next milestone should solve this.

------------------------------------------------------------------------

## 47.2 Retry Classification

The current retry classification relies partly on parsing exception
messages and HTTP status codes.

This should eventually be replaced with typed exceptions such as:

```text
httpx.TimeoutException
httpx.NetworkError
PlatformAPIError
RateLimitError
PermanentPlatformError
```

This will make retry behavior more deterministic.

------------------------------------------------------------------------

## 47.3 Redis Claim Timestamp

The current Redis claim operation moves the job and subsequently updates
its `claimed_at` metadata.

The timestamp update is not currently one single atomic operation.

This should be hardened later if required by the production architecture.

------------------------------------------------------------------------

## 47.4 Retry-After

HTTP 429 responses should eventually respect the platform's:

```text
Retry-After
```

header rather than always relying on the internal exponential backoff.

------------------------------------------------------------------------

## 47.5 Retry Jitter

Multiple workers could otherwise retry at similar times.

Randomized jitter should eventually be added to reduce synchronized retry
bursts.

------------------------------------------------------------------------

## 47.6 Dead-Letter Queue

After all retry attempts are exhausted, the system currently transitions
the post to:

```text
FAILED
```

A future production implementation should additionally support a
dead-letter queue for operational investigation and manual replay.

------------------------------------------------------------------------

# 48. Next Major Milestone — Publishing Idempotency

Publishing idempotency is now the next reliability milestone.

## Problem

External API publication and internal database state updates are separate
operations.

Therefore:

```text
Publisher
   ↓
Mastodon
   ↓
SUCCESS
   ↓
Worker crashes
   ↓
Database not updated
   ↓
Job recovered
   ↓
Publisher retries
   ↓
DUPLICATE POST
```

## Target Architecture

```text
Redis Job
    ↓
Publisher
    ↓
Idempotency Check
    ↓
Already published?
    │
   ┌┴──────────────┐
   │               │
  YES              NO
   │               │
   ▼               ▼
Reuse/confirm   Mastodon API
existing result     │
                    ▼
              Record publication
                    │
                    ▼
                PUBLISHED
                    │
                    ▼
              ACK Redis Job
```

## Planned implementation areas

Investigate:

- Unique internal publication identifier
- External Mastodon status ID storage
- Database uniqueness constraints
- Safe retry detection
- Worker crash recovery
- Duplicate job delivery
- Interaction between retries and idempotency
- Interaction between stale recovery and idempotency
- Platform-specific idempotency capabilities

The goal is to ensure that repeating a publishing operation cannot create
duplicate external posts.

------------------------------------------------------------------------

# 49. Future Multi-Platform Publishing Architecture

Once Mastodon publishing is sufficiently hardened, additional platforms
should be introduced through a common publishing interface.

Target architecture:

```text
                    SocialPilot Post
                           │
                           ▼
                  Publishing Service
                           │
                 Platform Interface
                           │
          +----------------+----------------+
          │                │                │
          ▼                ▼                ▼
      Mastodon          Instagram        LinkedIn
       Adapter            Adapter          Adapter
          │                │                │
          ▼                ▼                ▼
      Mastodon             Meta         LinkedIn
         API                API             API
```

X can later be added when the production cost/API strategy is acceptable.

The core application should not need to know the low-level details of each
platform API.

------------------------------------------------------------------------

# 50. Future AI Architecture

The long-term objective is to evolve the content-generation system into an
agentic workflow.

Potential architecture:

```text
Campaign Context
       ↓
Research / Context Agent
       ↓
Content Generation Agent
       ↓
Quality / Safety Checker
       ↓
HUMAN REVIEW GATE
       ↓
Platform Adapter
       ↓
Scheduler
       ↓
Publisher
       ↓
Analytics / Feedback
```

The Human-in-the-Loop gate remains mandatory.

The advanced agentic layer must not remove human authority over publication.

Potential future technologies include:

```text
LangGraph
Local / hosted LLMs
Structured tool calling
Platform-specific agents
Content quality evaluators
Analytics feedback loops
```

These should be introduced only after the underlying publishing
infrastructure is reliable.

------------------------------------------------------------------------

# 51. Frontend Roadmap

The backend publishing infrastructure should eventually be exposed through
a frontend workflow.

Target interface:

```text
Dashboard
   ↓
Brands
   ↓
Campaigns
   ↓
Generated Posts
   ↓
Approval Queue
   ↓
Review / Edit
   ├── Reject
   └── Approve
         ↓
      Schedule
         ↓
      Calendar
         ↓
   Publication Status
```

The frontend should clearly expose:

- Drafts
- Pending review
- Approved posts
- Scheduled posts
- Published posts
- Failed posts
- Retry status
- Connected accounts
- Publishing errors

The frontend should not bypass the backend's authorization and
Human-in-the-Loop rules.

------------------------------------------------------------------------

# 52. Analytics Roadmap

Future analytics should track:

```text
Publication status
Platform response
External post ID
Engagement
Reach
Impressions
Clicks
Errors
Publication timing
Retry count
```

Eventually:

```text
Content Generation
       ↓
Publication
       ↓
Engagement
       ↓
Analytics
       ↓
AI Feedback
       ↓
Improved Content
```

This creates the long-term feedback loop required for a more advanced
agentic social-media system.

------------------------------------------------------------------------

# 53. Recommended Development Sequence

The current recommended order is:

```text
1. Publishing Idempotency
          ↓
2. Stronger Error Classification
          ↓
3. Retry-After + Jitter
          ↓
4. Dead-Letter Queue
          ↓
5. Multi-Platform Publisher Interface
          ↓
6. Instagram Integration
          ↓
7. Frontend Approval Queue
          ↓
8. Frontend Calendar
          ↓
9. Analytics
          ↓
10. AI Quality/Safety Layer
          ↓
11. Advanced Agentic Workflow
          ↓
12. X Production Integration
```

This order intentionally prioritizes reliability before increasing platform
or agentic complexity.

------------------------------------------------------------------------

# 54. Current Project Definition of Done

The current development milestone should be considered complete when:

```text
[✓] User authentication
[✓] User ownership
[✓] Brand management
[✓] Campaign management
[✓] Post CRUD
[✓] Post lifecycle
[✓] Human-in-the-Loop approval
[✓] AI content generation
[✓] Generic SocialAccount system
[✓] Mastodon OAuth
[✓] Mastodon account persistence
[✓] Mastodon publishing
[✓] Secure social-account responses
[✓] Database-backed scheduling
[✓] Redis main queue
[✓] Redis processing queue
[✓] Redis acknowledgement
[✓] Retry metadata
[✓] Delayed retry queue
[✓] Retry promoter
[✓] Stale-job recovery
[✓] Real scheduled Mastodon E2E
```

The next definition-of-done target is:

```text
[ ] Publishing idempotency
[ ] Strong typed failure classification
[ ] Production-grade retry semantics
[ ] Dead-letter handling
```

------------------------------------------------------------------------

# 55. Final Architecture Principle

The most important architectural principle established throughout this
development is:

```text
AI should generate and assist.

Humans should retain approval authority.

Backend services should enforce ownership and state.

PostgreSQL should remain the source of truth.

Redis should coordinate background work.

Platform adapters should isolate external APIs.

Workers should be recoverable.

External side effects should eventually be idempotent.
```

The long-term SocialPilot AI architecture therefore remains:

```text
                         USER
                          │
                          ▼
                    SOCIALPILOT AI
                          │
        ┌─────────────────┼──────────────────┐
        │                 │                  │
        ▼                 ▼                  ▼
      BRANDS          SOCIAL ACCOUNTS      CAMPAIGNS
        │                 │                  │
        └─────────────────┼──────────────────┘
                          │
                          ▼
                    AI GENERATION
                          │
                          ▼
                        DRAFT
                          │
                          ▼
                  HUMAN REVIEW GATE
                          │
                    ┌─────┴─────┐
                    │           │
                 REJECT       APPROVE
                    │           │
                    │           ▼
                    │       SCHEDULED
                    │           │
                    │           ▼
                    │      DB SCHEDULER
                    │           │
                    │           ▼
                    │      REDIS QUEUE
                    │           │
                    │           ▼
                    │      PUBLISHER
                    │           │
                    │           ▼
                    │    PLATFORM ADAPTER
                    │           │
                    │           ▼
                    │     EXTERNAL API
                    │           │
                    │           ▼
                    │       PUBLISHED
                    │           │
                    │           ▼
                    │       ANALYTICS
                    │
                    └──→ REVISE / REGENERATE
```

This architecture should be preserved as the project grows.

The system should become **more automated and agentic without becoming less
controlled**.

Human-in-the-Loop remains a permanent architecture boundary.