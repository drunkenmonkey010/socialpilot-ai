# SocialPilot AI — Development Documentation

> **Living document:** update this file after every major milestone. It
> records the architecture, decisions, problems, fixes, tests, security
> issues, and future plan so a new developer can understand the entire
> project.

## 1. Project goal

SocialPilot AI is being developed as an **agentic AI social-media
management platform**.

The long-term workflow is:

``` text
Campaign brief
    ↓
AI content generation
    ↓
DRAFT
    ↓
Human review
    ├── Edit / Reject → revise → review again
    └── Approve
          ↓
      SCHEDULED
          ↓
      PUBLISHING
          ↓
      PUBLISHED
          ↓
      Analytics / feedback
```

The core architectural principle is:

> **AI may generate and recommend content, but a human remains the
> approval boundary before externally visible publication.**

------------------------------------------------------------------------

## 2. Backend architecture

The backend uses FastAPI with a layered structure:

``` text
API Routes
    ↓
Services
    ↓
Repositories
    ↓
SQLAlchemy Models
    ↓
PostgreSQL
```

External social platforms are isolated in an integration layer:

``` text
Application
    ↓
Integration layer
    ↓
Mastodon / Instagram / future platforms
```

This keeps HTTP concerns, business rules, database operations, and
third-party API logic separate.

------------------------------------------------------------------------

## 3. Existing foundation

The project already has:

- FastAPI
- SQLAlchemy async database access
- PostgreSQL
- Alembic migrations
- JWT authentication
- Pydantic schemas
- User/brand/campaign hierarchy
- Repository/service architecture
- Redis configuration
- LLM configuration for Ollama/OpenAI
- Instagram integration scaffolding
- Mastodon integration

Important configuration is centralized in:

``` text
app/core/config.py
```

It contains database, Redis, JWT, frontend/backend URL, LLM, Instagram,
and Mastodon settings.

------------------------------------------------------------------------

# 4. Authentication and ownership

Authentication is implemented in:

``` text
app/api/dependencies/auth.py
```

The flow is:

``` text
Authorization: Bearer <JWT>
        ↓
decode_access_token()
        ↓
extract "sub"
        ↓
convert to user ID
        ↓
load User
        ↓
verify active user
        ↓
authenticated request
```

Resources are owned through:

``` text
User
 ├── Brand
 │    └── Campaign
 │         └── Post
 └── SocialAccount
```

This ownership model is used to prevent one user from accessing another
user’s campaigns/posts/accounts.

------------------------------------------------------------------------

# 5. Social account implementation

The social-account model is:

``` text
app/models/social_account.py
```

It stores:

- `id`
- `user_id`
- `platform`
- `account_name`
- `account_id`
- `access_token`
- `refresh_token`
- `token_expires_at`
- `is_active`
- timestamps

The database must retain OAuth credentials because the backend needs
them to communicate with social platforms.

However, those credentials must never be unnecessarily exposed to the
frontend.

------------------------------------------------------------------------

# 6. Mastodon OAuth

Mastodon support was implemented through:

``` text
app/api/routes/mastodon.py
app/integrations/mastodon/oauth.py
```

The configured instance is:

``` text
https://mastodon.social
```

The OAuth flow is:

``` text
User
 ↓
GET /social-accounts/mastodon/connect
 ↓
Create OAuth state
 ↓
Mastodon authorization URL
 ↓
User authorizes application
 ↓
Mastodon callback
 ↓
Authorization code
 ↓
Exchange code for access token
 ↓
Verify Mastodon account
 ↓
Persist SocialAccount
```

The authorization request uses:

- client ID
- redirect URI
- `response_type=code`
- scopes
- OAuth state

Current scopes include:

``` text
read:accounts write:statuses
```

------------------------------------------------------------------------

# 7. OAuth problems and fixes

## Problem: missing client_id

Mastodon initially displayed:

``` text
Missing required parameter: client_id.
```

### Cause

The authorization request was not correctly providing the configured
Mastodon client ID.

### Fix

The authorization URL builder was corrected to explicitly include:

``` text
client_id
redirect_uri
response_type
scope
state
```

OAuth authorization subsequently succeeded.

------------------------------------------------------------------------

## Problem: missing repository method

The Mastodon connection flow initially failed with:

``` text
SocialAccountRepository has no attribute
get_by_platform_and_account_id
```

### Cause

The connection workflow expected a repository lookup method that had not
yet been implemented.

### Fix

The repository was extended with:

``` text
get_by_platform_and_account_id()
```

Verification:

``` powershell
python -c "from app.repositories.social_account import SocialAccountRepository; print(hasattr(SocialAccountRepository, 'get_by_platform_and_account_id'))"
```

Result:

``` text
True
```

A second lookup method was also verified:

``` text
get_by_platform_for_user()
```

------------------------------------------------------------------------

# 8. OAuth state and user association

OAuth state helpers were implemented:

``` text
_create_oauth_state()
_verify_oauth_state()
```

Verification:

``` powershell
python -c "from app.api.routes.mastodon import _create_oauth_state, _verify_oauth_state; s=_create_oauth_state(2); print('State created:', bool(s)); print('Recovered user:', _verify_oauth_state(s))"
```

Result:

``` text
State created: True
Recovered user: 2
```

This establishes that OAuth state can carry the local user context
through the authorization flow.

------------------------------------------------------------------------

# 9. Successful Mastodon connection

After fixing the OAuth and repository issues, a real Mastodon account
was connected.

The successful response contained:

``` json
{
  "status": "connected",
  "message": "Mastodon account connected successfully.",
  "account": {
    "id": 2,
    "platform": "mastodon",
    "account_name": "socialpilot_ai",
    "account_id": "117203384978868329",
    "is_active": true
  }
}
```

This proved:

- OAuth authorization works.
- Authorization code exchange works.
- Mastodon account verification works.
- The external account can be stored against the local user.

------------------------------------------------------------------------

# 10. Security issue: OAuth tokens exposed

Initially, `SocialAccountResponse` included:

``` text
access_token
refresh_token
```

Therefore:

``` text
GET /social-accounts
```

could expose an OAuth credential to the frontend.

This was considered a serious security problem.

The desired architecture is:

``` text
Database
   │
   ├── access_token 🔒
   └── refresh_token 🔒
          │
          ↓
       Backend
          │
          ↓
   Mastodon API
```

The frontend should only receive account metadata.

------------------------------------------------------------------------

# 11. Security fix

The file:

``` text
app/schemas/social_account.py
```

was changed so `SocialAccountResponse` no longer exposes OAuth
credentials.

The safe response contains:

``` text
id
user_id
platform
account_name
account_id
token_expires_at
is_active
created_at
updated_at
```

Verification:

``` powershell
python -c "from app.schemas.social_account import SocialAccountResponse; print('Schema OK'); print(list(SocialAccountResponse.model_fields.keys()))"
```

Result:

``` text
Schema OK
['id', 'user_id', 'platform', 'account_name', 'account_id', 'token_expires_at', 'is_active', 'created_at', 'updated_at']
```

The real endpoint was also tested and returned the account without
`access_token` or `refresh_token`.

------------------------------------------------------------------------

# 12. Brand → campaign → post hierarchy

Posts belong to campaigns:

``` text
User
 ↓
Brand
 ↓
Campaign
 ↓
Post
```

The post service checks campaign ownership before creating a post.

This means knowing a campaign ID is not sufficient to create a post
under somebody else’s campaign.

------------------------------------------------------------------------

# 13. Campaign testing problem

An initial post test used:

``` text
campaign_id = 1
```

and returned:

``` json
{"detail":"Campaign not found"}
```

The campaign API was inspected.

There is no:

``` text
GET /campaigns
```

route, so testing that URL returned:

``` text
405 Method Not Allowed
```

The existing campaign routes include:

``` text
POST   /campaigns
GET    /campaigns/brand/{brand_id}
GET    /campaigns/{campaign_id}
PATCH  /campaigns/{campaign_id}
DELETE /campaigns/{campaign_id}
```

The user’s brand was then checked and the correct campaign was found:

``` text
brand_id = 2
campaign_id = 2
```

The post was then successfully created under campaign `2`.

------------------------------------------------------------------------

# 14. PowerShell JSON testing problem

Inline JSON was initially sent using PowerShell/curl and caused JSON
parsing and shell escaping errors.

Example failure:

``` text
JSON decode error
```

and curl attempted to interpret pieces of the content as separate hosts.

### Decision

Use a temporary file:

``` text
test-post.json
```

and send:

``` powershell
--data-binary "@test-post.json"
```

This worked reliably.

This is a useful Windows development practice for non-trivial JSON API
tests.

The temporary test file should not become production application data.

------------------------------------------------------------------------

# 15. Post model

The post model is:

``` text
app/models/post.py
```

Important fields:

``` text
id
campaign_id
content
platform
status
scheduled_at
published_at
created_at
updated_at
```

A `PostStatus` enum was introduced:

``` text
draft
pending_review
approved
rejected
scheduled
publishing
published
failed
```

Verification produced:

``` text
Statuses:
['draft', 'pending_review', 'approved', 'rejected',
 'scheduled', 'publishing', 'published', 'failed']
```

------------------------------------------------------------------------

# 16. Why explicit lifecycle states were introduced

A publishing platform needs to know exactly where each post is.

For example:

``` text
draft
```

means the content is still being prepared.

``` text
pending_review
```

means it is waiting for a human.

``` text
approved
```

means the human has approved the exact content.

``` text
scheduled
```

means it is waiting for its publication time.

``` text
publishing
```

means an external publication request is in progress.

``` text
published
```

means publication succeeded.

``` text
failed
```

means publication failed and requires handling/retry/review.

Explicit states make the workflow auditable and prevent unsafe
transitions.

------------------------------------------------------------------------

# 17. Editable states

The service defines:

``` python
EDITABLE_STATUSES = {
    "draft",
    "rejected",
}
```

Therefore normal editing is only permitted for:

``` text
DRAFT
REJECTED
```

An approved/scheduled/published post should not silently change after
human approval.

This protects the meaning of the approval step.

------------------------------------------------------------------------

# 18. Human-in-the-Loop

Human-in-the-Loop is a core architecture decision.

The intended flow is:

``` text
AI generated content
        ↓
      DRAFT
        ↓
PENDING_REVIEW
        ↓
   HUMAN DECISION
      ↙       ↘
  REJECT      APPROVE
     ↓           ↓
  revise      APPROVED
                 ↓
             schedule
                 ↓
             publish
```

The AI must not automatically approve or publish its own generated
content.

The human approval endpoint is therefore an explicit control boundary
before an external side effect.

------------------------------------------------------------------------

# 19. Post service

Business logic is in:

``` text
app/services/post.py
```

It currently handles:

- creation
- retrieval
- campaign post retrieval
- editing
- submit for review
- approval
- rejection
- scheduling
- publishing
- deletion

The service enforces state transitions rather than allowing arbitrary
status changes.

------------------------------------------------------------------------

# 20. Post routes

Current post routes are:

``` text
POST   /posts
GET    /posts/{post_id}
GET    /posts/campaign/{campaign_id}
PATCH  /posts/{post_id}
POST   /posts/{post_id}/submit-review
POST   /posts/{post_id}/approve
POST   /posts/{post_id}/reject
POST   /posts/{post_id}/schedule
POST   /posts/{post_id}/publish
DELETE /posts/{post_id}
```

Router and OpenAPI registration were verified.

------------------------------------------------------------------------

# 21. First successful post

A test post was created with:

``` json
{
  "campaign_id": 2,
  "content": "This is a test post for the SocialPilot AI human review workflow.",
  "platform": "mastodon"
}
```

The API returned:

``` text
id = 2
campaign_id = 2
platform = mastodon
status = draft
```

This verified post creation and ownership validation.

------------------------------------------------------------------------

# 22. Human review test

The post was submitted using:

``` text
POST /posts/2/submit-review
```

Result:

``` text
status = pending_review
```

Verified transition:

``` text
DRAFT
  ↓
PENDING_REVIEW
```

------------------------------------------------------------------------

# 23. Human approval test

The post was approved using:

``` text
POST /posts/2/approve
```

Result:

``` text
status = approved
```

Verified transition:

``` text
PENDING_REVIEW
       ↓
HUMAN APPROVAL
       ↓
APPROVED
```

This is the first fully verified Human-in-the-Loop boundary.

------------------------------------------------------------------------

# 24. Mastodon publishing integration

The Mastodon integration was extended with:

``` text
publish_mastodon_status()
```

Import verification:

``` powershell
python -c "from app.integrations.mastodon.oauth import publish_mastodon_status; print('Mastodon publishing integration OK')"
```

Result:

``` text
Mastodon publishing integration OK
```

The post service was also verified after publishing functionality was
added.

------------------------------------------------------------------------

# 25. Real Mastodon publication

The approved post was published with:

``` text
POST /posts/2/publish
```

The API returned:

``` json
{
  "id": 2,
  "campaign_id": 2,
  "content": "This is a test post for the SocialPilot AI human review workflow.",
  "platform": "mastodon",
  "status": "published",
  "published_at": "2026-09-03T10:52:18.765522Z"
}
```

A subsequent:

``` text
GET /posts/2
```

confirmed:

``` text
status = published
published_at = populated
```

Most importantly, the post was visible on the real Mastodon account:

``` text
@socialpilot_ai@mastodon.social
```

The profile showed the post publicly.

This is the first complete external end-to-end proof of SocialPilot.

------------------------------------------------------------------------

# 26. Current proven vertical slice

``` text
Authenticated user
        ↓
Connect Mastodon through OAuth
        ↓
Persist social account
        ↓
Create campaign post
        ↓
DRAFT
        ↓
Submit review
        ↓
PENDING_REVIEW
        ↓
Human approval
        ↓
APPROVED
        ↓
Mastodon publishing integration
        ↓
PUBLISHED
        ↓
Real post on Mastodon
```

This is no longer a mocked integration: a real external social-media
post was successfully created.

------------------------------------------------------------------------

# 27. Current architecture

``` text
                         USER
                           │
                           ↓
                     FastAPI API
                           │
             ┌─────────────┼─────────────┐
             ↓             ↓             ↓
           Auth      Brand/Campaign     Posts
             │             │             │
             │             │        PostService
             │             │             │
             │             └─────────────┤
             │                           ↓
             │                    PostRepository
             │                           │
             └───────────────────────────┤
                                         ↓
                                    PostgreSQL
                                         │
                              ┌──────────┴──────────┐
                              ↓                     ↓
                       SocialAccount              Posts
                              │
                              ↓
                    Mastodon Integration
                              │
                              ↓
                         Mastodon API
```

------------------------------------------------------------------------

# 28. Future AI architecture

The AI layer should be integrated into the existing workflow, not create
a parallel publishing system.

Target:

``` text
Brand + Campaign + brief
          ↓
    AI Content Agent
          ↓
       PostService
          ↓
        DRAFT
          ↓
   PENDING_REVIEW
          ↓
    HUMAN REVIEW
      ↙       ↘
  REJECT      APPROVE
    ↓            ↓
 regenerate    APPROVED
                 ↓
              schedule
                 ↓
              publish
```

This means AI-generated posts automatically benefit from the existing
security, ownership, state-machine, and publishing logic.

------------------------------------------------------------------------

# 29. Planned AI capabilities

The AI layer may eventually use:

- brand description
- campaign objective
- target audience
- platform
- tone
- product/service information
- keywords
- call-to-action requirements
- content type

The output may include:

``` text
post content
platform-specific adaptation
hashtags
call to action
quality/recommendation metadata
```

But the initial saved state should remain:

``` text
DRAFT
```

not `APPROVED` or `PUBLISHED`.

------------------------------------------------------------------------

# 30. Planned scheduler

The future scheduler will implement:

``` text
APPROVED
   ↓
SCHEDULED
   ↓
wait for scheduled_at
   ↓
PUBLISHING
   ↓
PUBLISHED
```

This will likely require background processing/queue infrastructure.

Redis is already configured and can be incorporated into the future
worker architecture.

Important scheduler concerns:

- timezone handling
- jobs becoming due
- retries
- duplicate execution
- worker crashes
- database locking
- idempotency

------------------------------------------------------------------------

# 31. Failure and crash points

The application can fail at many boundaries.

## OAuth

Possible failures:

- invalid client ID
- invalid client secret
- redirect URI mismatch
- user denies authorization
- expired authorization code
- invalid OAuth state
- Mastodon unavailable

## Database

Possible failures:

- PostgreSQL unavailable
- transaction failure
- connection pool exhaustion
- migration/schema mismatch

## AI

Possible failures:

- Ollama unavailable
- external LLM unavailable
- timeout
- malformed AI output
- empty response
- content exceeding platform limits
- inappropriate or inaccurate content

AI failure must never result in accidental publication.

## Publishing

Possible failures:

- network timeout
- Mastodon server unavailable
- rate limiting
- invalid credentials
- revoked credentials
- invalid content
- insufficient permission
- account disabled

## Scheduling

Possible failures:

- worker unavailable
- Redis unavailable
- duplicate worker execution
- timezone mistakes
- scheduled job lost
- race condition

------------------------------------------------------------------------

# 32. Duplicate publication risk

This is one of the most important future problems.

Consider:

``` text
Worker sends post to Mastodon
        ↓
Mastodon publishes it
        ↓
network response is lost
        ↓
worker thinks it failed
        ↓
worker retries
        ↓
duplicate post
```

Therefore future publishing needs an idempotency strategy and/or
external publication identifier tracking.

------------------------------------------------------------------------

# 33. Concurrency risk

Two workers could potentially select the same scheduled post:

``` text
Worker A → post #5
Worker B → post #5
```

Both could attempt publication.

Future scheduling must atomically claim a post before publishing, using
an appropriate database/queue locking strategy.

------------------------------------------------------------------------

# 34. Security considerations

Already implemented:

- JWT authentication
- active-user validation
- user ownership checks
- campaign ownership checks
- OAuth state handling
- OAuth credentials hidden from API responses

Future security work:

- encrypt OAuth credentials at rest
- secure secret management
- token revocation/rotation
- avoid tokens in logs
- rate limiting
- stronger validation
- audit logs
- secure error handling
- review OAuth state storage/expiration
- prevent accidental secret exposure in debugging

------------------------------------------------------------------------

# 35. Multi-platform design

The publishing layer should eventually use a common abstraction:

``` text
Publisher
   ├── MastodonPublisher
   ├── InstagramPublisher
   └── FuturePublisher
```

The post service should request publication without knowing
platform-specific HTTP details.

Example concept:

``` text
PostService
    ↓
PublisherFactory
    ↓
MastodonPublisher
    ↓
Mastodon API
```

This will make adding future platforms significantly easier.

------------------------------------------------------------------------

# 36. Testing strategy

Development has used several levels of verification.

## Import checks

Examples:

``` powershell
python -c "from app.models.post import Post, PostStatus; print('Post model OK')"
```

``` powershell
python -c "from app.schemas.post import PostCreate, PostUpdate, PostResponse; print('Post schemas OK')"
```

``` powershell
python -c "from app.services.post import PostService; print('Post service OK')"
```

``` powershell
python -c "from app.integrations.mastodon.oauth import publish_mastodon_status; print('Mastodon publishing integration OK')"
```

## Router checks

``` powershell
python -c "from app.api.routes.post import router; print([(r.path, sorted(r.methods)) for r in router.routes])"
```

## OpenAPI checks

``` powershell
python -c "from app.main import app; schema=app.openapi(); print([p for p in schema['paths'] if p.startswith('/posts')])"
```

## End-to-end API tests

The actual workflow was tested with curl:

``` text
create post
    ↓
submit review
    ↓
approve
    ↓
publish
    ↓
retrieve post
```

The final publication was then verified on the actual Mastodon website.

------------------------------------------------------------------------

# 37. Major challenges encountered

| Challenge                                             | Cause                                | Resolution                          |
|-------------------------------------------------------|--------------------------------------|-------------------------------------|
| Mastodon said `Missing required parameter: client_id` | OAuth URL missing required client ID | Corrected authorization URL         |
| Missing `get_by_platform_and_account_id`              | Repository incomplete                | Added repository method             |
| `Campaign not found`                                  | Wrong campaign ID used during test   | Queried owned brand/campaign        |
| `GET /campaigns` returned 405                         | No global GET campaigns route exists | Used `/campaigns/brand/{brand_id}`  |
| PowerShell JSON errors                                | Shell quoting/escaping               | Used `test-post.json`               |
| OAuth tokens exposed in API                           | Response schema included credentials | Removed tokens from response schema |
| Publishing needed external integration                | CRUD alone cannot publish            | Added Mastodon publisher            |

------------------------------------------------------------------------

# 38. Current verified feature status

| Feature                       | Status |
|-------------------------------|--------|
| FastAPI backend               | ✅     |
| JWT authentication            | ✅     |
| User ownership                | ✅     |
| Brands                        | ✅     |
| Campaigns                     | ✅     |
| Social account model          | ✅     |
| Social account repository     | ✅     |
| Mastodon OAuth                | ✅     |
| OAuth state                   | ✅     |
| Mastodon account verification | ✅     |
| Account persistence           | ✅     |
| Tokens hidden from API        | ✅     |
| Post model                    | ✅     |
| Post lifecycle                | ✅     |
| Post creation                 | ✅     |
| Post ownership                | ✅     |
| Human review                  | ✅     |
| Human approval                | ✅     |
| Human rejection               | ✅     |
| Scheduling state              | ✅     |
| Mastodon publisher            | ✅     |
| Real Mastodon publication     | ✅     |
| AI generation                 | ⏳     |
| AI quality checks             | ⏳     |
| Background scheduler          | ⏳     |
| Retry system                  | ⏳     |
| Idempotency                   | ⏳     |
| Frontend review UI            | ⏳     |
| Multi-platform publishing     | ⏳     |
| Analytics                     | ⏳     |
| Advanced agents               | ⏳     |

------------------------------------------------------------------------

# 39. Development milestones

## Milestone 1 — Social account foundation

Implemented:

- model
- repository
- service
- schemas
- routes
- migration
- user relationship

## Milestone 2 — Mastodon OAuth

Implemented:

- configuration
- authorization URL
- callback
- token exchange
- account verification
- state handling
- account persistence

Fixed:

- missing client ID
- missing repository lookup method

## Milestone 3 — Post lifecycle

Implemented:

- explicit status enum
- editable-state rules
- review submission
- approval
- rejection
- scheduling state
- publishing state
- failure state

## Milestone 4 — Human-in-the-Loop

Verified:

``` text
DRAFT → PENDING_REVIEW → APPROVED
```

## Milestone 5 — Real Mastodon publishing

Implemented:

- Mastodon status publisher
- publishing service logic
- `/publish` endpoint

Verified:

``` text
APPROVED → PUBLISHING → PUBLISHED
```

and the actual post appeared on Mastodon.

## Milestone 6 — Security hardening

Implemented:

- removal of OAuth tokens from normal API responses

Verified:

``` text
GET /social-accounts
```

does not expose the access token.

------------------------------------------------------------------------

# 40. Immediate development roadmap

## Phase 1 — Harden publishing

- Validate publisher errors.
- Set `PUBLISHING` before external publication.
- Set `PUBLISHED` only after confirmed success.
- Set `FAILED` on failure.
- Add safe retry behavior.
- Add idempotency protection.
- Avoid logging OAuth credentials.

## Phase 2 — AI generation

- Build AI content service.
- Pass brand/campaign context.
- Generate platform-aware drafts.
- Validate AI output.
- Save generated content as `DRAFT`.
- Allow human submission for review.

## Phase 3 — Human review UI

Build:

``` text
Drafts
 ↓
Pending Review
 ↓
Review/Edit
 ├── Reject
 └── Approve
```

## Phase 4 — Scheduling

Implement:

``` text
APPROVED → SCHEDULED → PUBLISHING → PUBLISHED
```

using background jobs.

## Phase 5 — Multi-platform publishing

Introduce a common publisher interface and platform-specific
implementations.

## Phase 6 — Analytics

Track:

- publication status
- platform response
- engagement
- reach
- errors
- timing

## Phase 7 — Advanced agentic system

Potential agents:

- content generation agent
- content critic/quality agent
- platform adaptation agent
- scheduling recommendation agent
- analytics agent
- campaign planning agent
- optimization/recommendation agent

------------------------------------------------------------------------

# 41. Architectural rules going forward

Every new automated feature should answer:

### What can AI do automatically?

Examples:

``` text
Generate
Analyze
Recommend
Rewrite
Adapt
Summarize
```

### What requires a human?

Examples:

``` text
Approve externally visible content
Override recommendations
Publish sensitive content
Change campaign strategy
```

### What happens if it fails?

Every important operation should have:

``` text
success
failure
retry
recovery
```

### Can it execute twice?

If yes, design for idempotency.

### Does it affect an external system?

If yes, add stricter validation, state management, and auditability.

------------------------------------------------------------------------

# 42. Definition of done

A feature should not be considered complete simply because an endpoint
returns `200`.

For an externally connected feature:

``` text
Implementation
    ↓
Import/unit validation
    ↓
API validation
    ↓
Database validation
    ↓
External integration test
    ↓
Failure-path test
    ↓
Security review
    ↓
Documentation update
    ↓
Git commit/push
```

------------------------------------------------------------------------

# 43. Current milestone summary

The first complete real-world vertical slice is now working:

``` text
User authentication
        ↓
Mastodon OAuth
        ↓
Social account persistence
        ↓
Campaign ownership
        ↓
Post creation
        ↓
DRAFT
        ↓
Human review
        ↓
PENDING_REVIEW
        ↓
Human approval
        ↓
APPROVED
        ↓
Mastodon API
        ↓
PUBLISHED
        ↓
Real Mastodon post
```

The next major transition is:

``` text
MANUALLY PROVIDED TEST CONTENT
              ↓
       AI-GENERATED CONTENT
```

while preserving:

``` text
AI
 ↓
DRAFT
 ↓
HUMAN REVIEW
 ↓
APPROVAL
 ↓
PUBLISH
```

------------------------------------------------------------------------

# 44. Living-document update format

For every future milestone, append/update:

``` text
## Milestone X — <Feature>

### Goal
What were we trying to accomplish?

### Files changed
Which files were added/modified?

### Architecture decision
What did we decide and why?

### Problems encountered
What failed?

### Resolution
How was it fixed?

### Tests
What commands/tests proved it works?

### Security considerations
What new risks were considered?

### Known limitations
What is still imperfect?

### Next steps
What comes next?
```

------------------------------------------------------------------------

# 45. Final current status

``` text
╔══════════════════════════════════════════════╗
║           SOCIALPILOT AI STATUS              ║
╠══════════════════════════════════════════════╣
║ Authentication                    ✅          ║
║ User ownership                    ✅          ║
║ Brands                            ✅          ║
║ Campaigns                         ✅          ║
║ Social accounts                   ✅          ║
║ Mastodon OAuth                    ✅          ║
║ OAuth state                       ✅          ║
║ Secure API responses              ✅          ║
║ Post lifecycle                    ✅          ║
║ Human review                      ✅          ║
║ Human approval                    ✅          ║
║ Mastodon publishing               ✅          ║
║ Real external post                ✅          ║
║ AI generation                     ⏳          ║
║ AI quality checks                 ⏳          ║
║ Scheduler                         ⏳          ║
║ Retry/idempotency                 ⏳          ║
║ Frontend review UI                ⏳          ║
║ Multi-platform publishing         ⏳          ║
║ Analytics                         ⏳          ║
║ Advanced agents                   ⏳          ║
╚══════════════════════════════════════════════╝
```

**Last confirmed milestone:** September 3, 2026 — a real post was
successfully published to the connected Mastodon account after passing
through the Human-in-the-Loop approval workflow.
