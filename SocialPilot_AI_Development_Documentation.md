SocialPilot AI — Development Documentation

Living document: update this file after every major milestone. It
records the architecture, decisions, problems, fixes, tests, security
issues, and future plan so a new developer can understand the entire
project.

Project goal

SocialPilot AI is being developed as an agentic AI social-media
management platform.

The long-term workflow is:

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

The core architectural principle is:

AI may generate and recommend content, but a human remains the
approval boundary before externally visible publication.

Backend architecture

The backend uses FastAPI with a layered structure:

API Routes
↓
Services
↓
Repositories
↓
SQLAlchemy Models
↓
PostgreSQL

External social platforms are isolated in an integration layer:

Application
↓
Integration layer
↓
Mastodon / Instagram / future platforms

This keeps HTTP concerns, business rules, database operations, and
third-party API logic separate.

Existing foundation

The project already has:

FastAPI

SQLAlchemy async database access

PostgreSQL

Alembic migrations

JWT authentication

Pydantic schemas

User/brand/campaign hierarchy

Repository/service architecture

Redis configuration

LLM configuration for Ollama/OpenAI

Instagram integration scaffolding

Mastodon integration

Important configuration is centralized in:

app/core/config.py

It contains database, Redis, JWT, frontend/backend URL, LLM, Instagram,
and Mastodon settings.

Authentication and ownership

Authentication is implemented in:

app/api/dependencies/auth.py

The flow is:

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

Resources are owned through:

User
├── Brand
│    └── Campaign
│         └── Post
└── SocialAccount

This ownership model is used to prevent one user from accessing another
user’s campaigns/posts/accounts.

Social account implementation

The social-account model is:

app/models/social_account.py

It stores:

id

user_id

platform

account_name

account_id

access_token

refresh_token

token_expires_at

is_active

timestamps

The database must retain OAuth credentials because the backend needs
them to communicate with social platforms.

However, those credentials must never be unnecessarily exposed to the
frontend.

Mastodon OAuth

Mastodon support was implemented through:

app/api/routes/mastodon.py
app/integrations/mastodon/oauth.py

The configured instance is:

https://mastodon.social

The OAuth flow is:

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

The authorization request uses:

client ID

redirect URI

response_type=code

scopes

OAuth state

Current scopes include:

read write

OAuth problems and fixes

Problem: missing client_id

Mastodon initially displayed:

Missing required parameter: client_id.

Cause

The authorization request was not correctly providing the configured
Mastodon client ID.

Fix

The authorization URL builder was corrected to explicitly include:

client_id
redirect_uri
response_type
scope
state

OAuth authorization subsequently succeeded.

Problem: missing repository method

The Mastodon connection flow initially failed with:

SocialAccountRepository has no attribute
get_by_platform_and_account_id

Cause

The connection workflow expected a repository lookup method that had not
yet been implemented.

Fix

The repository was extended with:

get_by_platform_and_account_id()

Verification:

python -c "from app.repositories.social_account import SocialAccountRepository; print(hasattr(SocialAccountRepository, 'get_by_platform_and_account_id'))"

Result:

True

A second lookup method was also verified:

get_by_platform_for_user()

OAuth state and user association

OAuth state helpers were implemented:

_create_oauth_state()
_verify_oauth_state()

Verification:

python -c "from app.api.routes.mastodon import _create_oauth_state, _verify_oauth_state; s=_create_oauth_state(2); print('State created:', bool(s)); print('Recovered user:', _verify_oauth_state(s))"

Result:

State created: True
Recovered user: 2

This establishes that OAuth state can carry the local user context
through the authorization flow.

Successful Mastodon connection

After fixing the OAuth and repository issues, a real Mastodon account
was connected.

The successful response contained:

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

This proved:

OAuth authorization works.

Authorization code exchange works.

Mastodon account verification works.

The external account can be stored against the local user.

Security issue: OAuth tokens exposed

Initially, SocialAccountResponse included:

access_token
refresh_token

Therefore:

GET /social-accounts

could expose an OAuth credential to the frontend.

This was considered a serious security problem.

The desired architecture is:

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

The frontend should only receive account metadata.

Security fix

The file:

app/schemas/social_account.py

was changed so SocialAccountResponse no longer exposes OAuth
credentials.

The safe response contains:

id
user_id
platform
account_name
account_id
token_expires_at
is_active
created_at
updated_at

Verification:

python -c "from app.schemas.social_account import SocialAccountResponse; print('Schema OK'); print(list(SocialAccountResponse.model_fields.keys()))"

Result:

Schema OK
['id', 'user_id', 'platform', 'account_name', 'account_id', 'token_expires_at', 'is_active', 'created_at', 'updated_at']

The real endpoint was also tested and returned the account without
access_token or refresh_token.

Brand → campaign → post hierarchy

Posts belong to campaigns:

User
↓
Brand
↓
Campaign
↓
Post

The post service checks campaign ownership before creating a post.

This means knowing a campaign ID is not sufficient to create a post
under somebody else’s campaign.

Campaign testing problem

An initial post test used:

campaign_id = 1

and returned:

{"detail":"Campaign not found"}

The campaign API was inspected.

There is no:

GET /campaigns

route, so testing that URL returned:

405 Method Not Allowed

The existing campaign routes include:

POST   /campaigns
GET    /campaigns/brand/{brand_id}
GET    /campaigns/{campaign_id}
PATCH  /campaigns/{campaign_id}
DELETE /campaigns/{campaign_id}

The user’s brand was then checked and the correct campaign was found:

brand_id = 2
campaign_id = 2

The post was then successfully created under campaign 2.

PowerShell JSON testing problem

Inline JSON was initially sent using PowerShell/curl and caused JSON
parsing and shell escaping errors.

Example failure:

JSON decode error

and curl attempted to interpret pieces of the content as separate hosts.

Decision

Use a temporary file:

test-post.json

and send:

--data-binary "@test-post.json"

This worked reliably.

This is a useful Windows development practice for non-trivial JSON API
tests.

The temporary test file should not become production application data.

Post model

The post model is:

app/models/post.py

Important fields:

id
campaign_id
content
platform
status
scheduled_at
published_at
created_at
updated_at

A PostStatus enum was introduced:

draft
pending_review
approved
rejected
scheduled
publishing
published
failed

Verification produced:

Statuses:
['draft', 'pending_review', 'approved', 'rejected',
'scheduled', 'publishing', 'published', 'failed']

Why explicit lifecycle states were introduced

A publishing platform needs to know exactly where each post is.

For example:

draft

means the content is still being prepared.

pending_review

means it is waiting for a human.

approved

means the human has approved the exact content.

scheduled

means it is waiting for its publication time.

publishing

means an external publication request is in progress.

published

means publication succeeded.

failed

means publication failed and requires handling/retry/review.

Explicit states make the workflow auditable and prevent unsafe
transitions.

Editable states

The service defines:

EDITABLE_STATUSES = {
"draft",
"rejected",
}

Therefore normal editing is only permitted for:

DRAFT
REJECTED

An approved/scheduled/published post should not silently change after
human approval.

This protects the meaning of the approval step.

Human-in-the-Loop

Human-in-the-Loop is a core architecture decision.

The intended flow is:

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

The AI must not automatically approve or publish its own generated
content.

The human approval endpoint is therefore an explicit control boundary
before an external side effect.

Post service

Business logic is in:

app/services/post.py

It currently handles:

creation

retrieval

campaign post retrieval

editing

submit for review

approval

rejection

scheduling

publishing

deletion

The service enforces state transitions rather than allowing arbitrary
status changes.

Post routes

Current post routes are:

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

Router and OpenAPI registration were verified.

First successful post

A test post was created with:

{
"campaign_id": 2,
"content": "This is a test post for the SocialPilot AI human review workflow.",
"platform": "mastodon"
}

The API returned:

id = 2
campaign_id = 2
platform = mastodon
status = draft

This verified post creation and ownership validation.

Human review test

The post was submitted using:

POST /posts/2/submit-review

Result:

status = pending_review

Verified transition:

DRAFT
↓
PENDING_REVIEW

Human approval test

The post was approved using:

POST /posts/2/approve

Result:

status = approved

Verified transition:

PENDING_REVIEW
↓
HUMAN APPROVAL
↓
APPROVED

This is the first fully verified Human-in-the-Loop boundary.

Mastodon publishing integration

The Mastodon integration was extended with:

publish_mastodon_status()

Import verification:

python -c "from app.integrations.mastodon.oauth import publish_mastodon_status; print('Mastodon publishing integration OK')"

Result:

Mastodon publishing integration OK

The post service was also verified after publishing functionality was
added.

Real Mastodon publication

The approved post was published with:

POST /posts/2/publish

The API returned:

{
"id": 2,
"campaign_id": 2,
"content": "This is a test post for the SocialPilot AI human review workflow.",
"platform": "mastodon",
"status": "published",
"published_at": "2026-09-03T10:52:18.765522Z"
}

A subsequent:

GET /posts/2

confirmed:

status = published
published_at = populated

Most importantly, the post was visible on the real Mastodon account:

@socialpilot_ai@mastodon.social

The profile showed the post publicly.

This is the first complete external end-to-end proof of SocialPilot.

Current proven vertical slice

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

This is no longer a mocked integration: a real external social-media
post was successfully created.

Current architecture

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

Future AI architecture

The AI layer should be integrated into the existing workflow, not create
a parallel publishing system.

Target:

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

This means AI-generated posts automatically benefit from the existing
security, ownership, state-machine, and publishing logic.

Planned AI capabilities

The AI layer may eventually use:

brand description

campaign objective

target audience

platform

tone

product/service information

keywords

call-to-action requirements

content type

The output may include:

post content
platform-specific adaptation
hashtags
call to action
quality/recommendation metadata

But the initial saved state should remain:

DRAFT

not APPROVED or PUBLISHED.

Planned scheduler

The future scheduler will implement:

APPROVED
↓
SCHEDULED
↓
wait for scheduled_at
↓
PUBLISHING
↓
PUBLISHED

This will likely require background processing/queue infrastructure.

Redis is already configured and can be incorporated into the future
worker architecture.

Important scheduler concerns:

timezone handling

jobs becoming due

retries

duplicate execution

worker crashes

database locking

idempotency

Failure and crash points

The application can fail at many boundaries.

OAuth

Possible failures:

invalid client ID

invalid client secret

redirect URI mismatch

user denies authorization

expired authorization code

invalid OAuth state

Mastodon unavailable

Database

Possible failures:

PostgreSQL unavailable

transaction failure

connection pool exhaustion

migration/schema mismatch

AI

Possible failures:

Ollama unavailable

external LLM unavailable

timeout

malformed AI output

empty response

content exceeding platform limits

inappropriate or inaccurate content

AI failure must never result in accidental publication.

Publishing

Possible failures:

network timeout

Mastodon server unavailable

rate limiting

invalid credentials

revoked credentials

invalid content

insufficient permission

account disabled

Scheduling

Possible failures:

worker unavailable

Redis unavailable

duplicate worker execution

timezone mistakes

scheduled job lost

race condition

Duplicate publication risk

This is one of the most important future problems.

Consider:

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

Therefore future publishing needs an idempotency strategy and/or
external publication identifier tracking.

Concurrency risk

Two workers could potentially select the same scheduled post:

Worker A → post #5
Worker B → post #5

Both could attempt publication.

Future scheduling must atomically claim a post before publishing, using
an appropriate database/queue locking strategy.

Security considerations

Already implemented:

JWT authentication

active-user validation

user ownership checks

campaign ownership checks

OAuth state handling

OAuth credentials hidden from API responses

Future security work:

encrypt OAuth credentials at rest

secure secret management

token revocation/rotation

avoid tokens in logs

rate limiting

stronger validation

audit logs

secure error handling

review OAuth state storage/expiration

prevent accidental secret exposure in debugging

Multi-platform design

The publishing layer should eventually use a common abstraction:

Publisher
├── MastodonPublisher
├── InstagramPublisher
└── FuturePublisher

The post service should request publication without knowing
platform-specific HTTP details.

Example concept:

PostService
↓
PublisherFactory
↓
MastodonPublisher
↓
Mastodon API

This will make adding future platforms significantly easier.

Testing strategy

Development has used several levels of verification.

Import checks

Examples:

python -c "from app.models.post import Post, PostStatus; print('Post model OK')"

python -c "from app.schemas.post import PostCreate, PostUpdate, PostResponse; print('Post schemas OK')"

python -c "from app.services.post import PostService; print('Post service OK')"

python -c "from app.integrations.mastodon.oauth import publish_mastodon_status; print('Mastodon publishing integration OK')"

Router checks

python -c "from app.api.routes.post import router; print([(r.path, sorted(r.methods)) for r in router.routes])"

OpenAPI checks

python -c "from app.main import app; schema=app.openapi(); print([p for p in schema['paths'] if p.startswith('/posts')])"

End-to-end API tests

The actual workflow was tested with curl:

create post
↓
submit review
↓
approve
↓
publish
↓
retrieve post

The final publication was then verified on the actual Mastodon website.

Major challenges encountered

Challenge

Cause

Resolution

Mastodon said Missing required parameter: client_id

OAuth URL missing required client ID

Corrected authorization URL

Missing get_by_platform_and_account_id

Repository incomplete

Added repository method

Campaign not found

Wrong campaign ID used during test

Queried owned brand/campaign

GET /campaigns returned 405

No global GET campaigns route exists

Used /campaigns/brand/{brand_id}

PowerShell JSON errors

Shell quoting/escaping

Used test-post.json

OAuth tokens exposed in API

Response schema included credentials

Removed tokens from response schema

Publishing needed external integration

CRUD alone cannot publish

Added Mastodon publisher

Ollama model produced poor/reasoning-heavy output during experimentation

Model behavior was unsuitable for concise social-post output

Selected Llama 3 and constrained generation

Redis TimeoutError while queue was empty

Blocking Redis connection had a socket timeout

Configured async Redis client with socket_timeout=None

Redis job could be lost between processing and requeue

Separate remove/push operations were not atomic

Added Redis transactional pipelines

Stale processing jobs could remain after worker failure

Worker can terminate after claiming a job

Added claimed_at, recovery worker, and DB-aware stale-job recovery

Retryable publishing failure needed to remain retryable

Existing publishing logic marked every failure as FAILED

Added scheduled-publication error classification

Retries needed delayed execution

Immediate requeue would cause rapid repeated attempts

Added delayed retry metadata/promoter architecture and exponential backoff

Scheduled publishing needed duplicate-worker protection

Multiple workers may observe the same due post

Added atomic PostgreSQL claim: SCHEDULED → PUBLISHING

External publication can succeed before worker/database acknowledgement

Network/process failure can happen after Mastodon accepts the post

Idempotency remains the next major hardening milestone

Current verified feature status

Feature

Status

FastAPI backend

✅

JWT authentication

✅

User ownership

✅

Brands

✅

Campaigns

✅

Social account model

✅

Social account repository

✅

Mastodon OAuth

✅

OAuth state

✅

Mastodon account verification

✅

Account persistence

✅

Tokens hidden from API

✅

Post model

✅

Post lifecycle

✅

Post creation

✅

Post ownership

✅

Human review

✅

Human approval

✅

Human rejection

✅

Scheduling state

✅

Mastodon publisher

✅

Real Mastodon publication

✅

AI generation

✅

Grounded AI prompts

✅

Background scheduler

✅

Redis scheduled-post queue

✅

Redis processing queue

✅

Reliable Redis acknowledgement

✅

Stale-job recovery

✅

Delayed retry infrastructure

✅

Retry promoter

✅

Exponential retry/backoff

✅

Scheduled publishing E2E

✅

Publishing idempotency

⏳

AI quality/safety checks

⏳

Frontend review UI

⏳

Multi-platform publishing

⏳

Analytics

⏳

Advanced agents

⏳

Development milestones

Milestone 1 — Social account foundation

Implemented:

model

repository

service

schemas

routes

migration

user relationship

Milestone 2 — Mastodon OAuth

Implemented:

configuration

authorization URL

callback

token exchange

account verification

state handling

account persistence

Fixed:

missing client ID

missing repository lookup method

Milestone 3 — Post lifecycle

Implemented:

explicit status enum

editable-state rules

review submission

approval

rejection

scheduling state

publishing state

failure state

Milestone 4 — Human-in-the-Loop

Verified:

DRAFT → PENDING_REVIEW → APPROVED

The human approval step remains a mandatory boundary before external publication.

Milestone 5 — Real Mastodon publishing

Implemented:

Mastodon status publisher

publishing service logic

/publish endpoint

Verified:

APPROVED → PUBLISHING → PUBLISHED

and the actual post appeared on Mastodon.

Milestone 6 — Security hardening

Implemented:

removal of OAuth tokens from normal API responses

verification that /social-accounts does not expose access tokens

Milestone 7 — AI-assisted content generation

Implemented:

Ollama-based local LLM integration

Llama 3 model selection

brand/campaign-grounded prompts

platform-aware generation

AI-generated posts saved as DRAFT

generation through the existing Campaign/Post service architecture

Important decision:

AI generation does not bypass Human-in-the-Loop approval. Generated content enters the existing draft/review workflow.

Milestone 8 — Database-backed scheduled publishing

Implemented:

scheduled post querying

due-post detection

atomic database claim from SCHEDULED → PUBLISHING

scheduler/worker architecture

Redis integration for scheduled publishing jobs

The database remains the source of truth for post state.

Milestone 9 — Reliable Redis publishing queue

Implemented:

main scheduled-post queue

processing queue

job metadata

acknowledgement after successful completion

handling for already-published/invalid jobs

blocking Redis consumption without repeated empty-queue socket timeouts

The queue architecture is:

SCHEDULED POST
→ PostgreSQL claim
→ Redis main queue
→ Redis processing queue
→ publisher
→ Mastodon
→ database update
→ Redis acknowledgement

Milestone 10 — Stale-job recovery

Implemented:

processing-job inspection

claimed_at metadata

stale-job detection

database-aware recovery

job-specific recovery

recovery worker

atomic processing → main queue recovery transition

Recovery checks PostgreSQL before requeueing a stale Redis job so that already-published or already-failed posts are not blindly republished.

Milestone 11 — Scheduled publishing retries

Implemented:

retryable vs permanent scheduled-publication errors

maximum retry attempts

exponential backoff

retry metadata

delayed retry storage/promotion

retry promoter worker

recovery integration

Redis atomic processing → retry transitions

Current retry policy:

Attempt 1 → 30 seconds

Attempt 2 → 60 seconds

Attempt 3 → 120 seconds

Attempt 4 → 240 seconds

Maximum attempts → 5

A retryable failure keeps the post in PUBLISHING so the scheduled worker can retry. Permanent failures transition the post to FAILED.

Milestone 12 — Real scheduled publishing E2E

Verified end-to-end:

APPROVED
→ SCHEDULED
→ database scheduler
→ Redis queue
→ Redis processing queue
→ publisher worker
→ Mastodon API
→ PUBLISHED
→ Redis acknowledgement

A real scheduled post was successfully published to Mastodon and the resulting database state was verified.

Immediate development roadmap

Phase 1 — Publishing reliability

The core scheduled publishing path is now implemented.

Completed:

PUBLISHING before external publication

PUBLISHED only after confirmed success

permanent failure handling

retryable failure classification

Redis processing/acknowledgement

stale-job recovery

delayed retries

exponential backoff

Next hardening:

publishing idempotency

explicit typed platform errors

stronger HTTP exception classification

Retry-After support for rate limits

retry jitter

configurable retry policy

optional dead-letter queue

Phase 2 — AI generation

Completed:

AI content service

Ollama integration

Llama 3 model

brand/campaign context

platform-aware generation

generated content saved as DRAFT

integration with the existing Human-in-the-Loop workflow

Next:

AI output quality validation

content safety checks

platform-specific limits

hallucination/grounding checks

structured generation metadata

Phase 3 — Human review UI

Build:

Drafts
↓
Pending Review
↓
Review/Edit
├── Reject
└── Approve

The backend workflow already supports the required states; the frontend should expose this safely.

Phase 4 — Scheduling

Completed backend infrastructure:

APPROVED → SCHEDULED → PUBLISHING → PUBLISHED

Implemented with:

PostgreSQL as source of truth

due-post scheduler

Redis main queue

Redis processing queue

publisher worker

stale-job recovery

delayed retry promotion

exponential retry/backoff

Remaining:

frontend scheduling/calendar UI

timezone-aware user experience

production worker deployment

operational monitoring

Phase 5 — Multi-platform publishing

Introduce a common publisher interface and platform-specific implementations:

Mastodon publisher

Instagram publisher

future X publisher

future LinkedIn publisher

Mastodon remains the reference implementation.

Phase 6 — Analytics

Track:

publication status

platform response

engagement

reach

errors

timing

campaign performance

Phase 7 — Advanced agentic system

Potential agents:

campaign planning agent

research/context agent

content generation agent

content critic/quality agent

platform adaptation agent

scheduling recommendation agent

analytics agent

optimization/recommendation agent

Target architecture:

Campaign Context
↓
Research/Context Agent
↓
Content Generation Agent
↓
Quality/Safety Checker
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

Architectural rules going forward

Every new automated feature should answer:

What can AI do automatically?

Examples:

Generate
Analyze
Recommend
Rewrite
Adapt
Summarize

What requires a human?

Examples:

Approve externally visible content
Override recommendations
Publish sensitive content
Change campaign strategy

What happens if it fails?

Every important operation should have:

success
failure
retry
recovery

Can it execute twice?

If yes, design for idempotency.

Does it affect an external system?

If yes, add stricter validation, state management, and auditability.

Definition of done

A feature should not be considered complete simply because an endpoint
returns 200.

For an externally connected feature:

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

Current milestone summary

The first complete real-world vertical slice is now working:

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

The next major transition is:

MANUALLY PROVIDED TEST CONTENT
↓
AI-GENERATED CONTENT

while preserving:

AI
↓
DRAFT
↓
HUMAN REVIEW
↓
APPROVAL
↓
PUBLISH

Living-document update format

For every future milestone, append/update:

Milestone X — <Feature>

Goal

What were we trying to accomplish?

Files changed

Which files were added/modified?

Architecture decision

What did we decide and why?

Problems encountered

What failed?

Resolution

How was it fixed?

Tests

What commands/tests proved it works?

Security considerations

What new risks were considered?

Known limitations

What is still imperfect?

Next steps

What comes next?

Final current status

╔════════════════════════════════════════════════════════════╗
║              SOCIALPILOT AI CURRENT STATUS               ║
╠════════════════════════════════════════════════════════════╣
║ Authentication                         ✅ VERIFIED        ║
║ User ownership                         ✅ VERIFIED        ║
║ Brands                                 ✅ VERIFIED        ║
║ Campaigns                              ✅ VERIFIED        ║
║ Social accounts                        ✅ VERIFIED        ║
║ Mastodon OAuth                         ✅ VERIFIED        ║
║ OAuth state                            ✅ VERIFIED        ║
║ Secure API responses                   ✅ VERIFIED        ║
║ Post lifecycle                         ✅ VERIFIED        ║
║ Human-in-the-Loop approval             ✅ VERIFIED        ║
║ Mastodon publishing                    ✅ VERIFIED        ║
║ Real external post                     ✅ VERIFIED        ║
║ AI generation                          ✅ VERIFIED        ║
║ Grounded AI generation                 ✅ VERIFIED        ║
║ Database-backed scheduler              ✅ VERIFIED        ║
║ Redis scheduled-post queue             ✅ VERIFIED        ║
║ Redis processing/acknowledgement       ✅ VERIFIED        ║
║ Stale-job recovery                     ✅ VERIFIED        ║
║ Scheduled publishing retries           ✅ IMPLEMENTED    ║
║ Delayed retry promotion                ✅ IMPLEMENTED    ║
║ Scheduled publishing E2E               ✅ VERIFIED        ║
║ Publishing idempotency                 ⏳ NEXT            ║
║ AI quality/safety checks               ⏳ NEXT            ║
║ Frontend review UI                     ⏳                 ║
║ Multi-platform publishing              ⏳                 ║
║ Analytics                              ⏳                 ║
║ Advanced agents                        ⏳                 ║
╚════════════════════════════════════════════════════════════╝

Current proven end-to-end architecture:

Campaign
↓
AI generation
↓
DRAFT
↓
PENDING_REVIEW
↓
HUMAN APPROVAL
↓
APPROVED
↓
SCHEDULED
↓
PostgreSQL scheduler
↓
Atomic claim
↓
Redis main queue
↓
Redis processing queue
↓
Publisher worker
↓
Mastodon API
↓
PUBLISHED
↓
Redis acknowledgement

For transient failures:

Publisher
↓
Retryable failure
↓
Retry metadata
↓
Delayed retry
↓
Retry promoter
↓
Redis main queue
↓
Publisher

For worker crashes:

Redis processing queue
↓
claimed_at becomes stale
↓
Recovery worker
↓
Check PostgreSQL state
├── PUBLISHED → remove job
├── FAILED    → remove job
├── invalid   → remove job
└── PUBLISHING → recover/requeue

The database remains the source of truth for post state. Redis is used for queueing, processing coordination, retry scheduling, and recovery.

Current verified status — September 5, 2026

The earlier status sections are retained as historical documentation. The current implementation has progressed beyond the original manual-publishing milestone.

Verified scheduled publishing

A real scheduled post completed the following path:

APPROVED
↓
SCHEDULED
↓
Database scheduler detected due post
↓
Atomic claim: SCHEDULED → PUBLISHING
↓
Redis scheduled-post queue
↓
Redis processing queue
↓
Publisher worker
↓
Mastodon API
↓
PUBLISHED
↓
Redis acknowledgement

The resulting post was verified in the database and on the real Mastodon account.

Redis reliability improvements

The queue system now contains:

socialpilot
socialpilot

The processing queue allows a job to remain visible while a worker is handling it.

Successful jobs are explicitly acknowledged and removed.

Stale jobs can be recovered after a worker crash.

Retry transitions use Redis transactions so a job is not lost between removal from the processing queue and insertion into the next queue.

Retry system

Scheduled publishing distinguishes between:

Permanent failure
↓
FAILED

and:

Transient failure
↓
Retry
↓
Delayed retry
↓
Publisher

Current maximum attempts:

5 attempts

Current exponential backoff:

30s
60s
120s
240s

The fifth failed attempt results in:

FAILED

The retry system is intentionally limited to scheduled publishing. Manual publishing retains its existing behavior and transitions a failed manual publication to FAILED.

Recovery system

A dedicated recovery worker checks stale Redis processing jobs.

Before recovering a job, it checks PostgreSQL.

This prevents blindly retrying a post that has already reached:

PUBLISHED

or:

FAILED

Recovery is job-specific rather than globally requeueing every stale Redis entry.

AI generation

AI generation is now part of the backend workflow.

The intended flow is:

Brand + Campaign
↓
AI content generation
↓
DRAFT
↓
Human review
↓
APPROVED
↓
Schedule / Publish

The AI does not receive permission to bypass the Human-in-the-Loop boundary.

Current architecture after scheduling and retry work

             USER
               │
               ▼
         FastAPI API
               │

┌────────────────┼────────────────┐
│                │                │
▼                ▼                ▼
Auth       Brand/Campaign          Posts
│
▼
PostService
│
┌───────────────────┼───────────────────┐
│                   │                   │
▼                   ▼                   ▼
AI                 Review             Schedule
generation           / approval              │
│                   │                   ▼
└──────────► DRAFT / APPROVED     PostgreSQL
│
▼
Atomic claim
│
▼
Redis queue
│
▼
Redis processing queue
│
▼
Publisher worker
│
┌─────────────────┴───────────────┐
│                                 │
▼                                 ▼
Success                            Failure
│                                 │
▼                                 ▼
PUBLISHED                    classify failure
│                         │          │
│                    permanent    retryable
│                         │          │
│                         ▼          ▼
│                      FAILED    delayed retry
│                                    │
│                                    ▼
│                              retry promoter
│                                    │
│                                    ▼
└──────────────────────────── Redis queue

This architecture preserves the separation between:

application state

queue state

external side effects

AI generation

human approval

Known limitations after the retry milestone

The retry system is functional but not yet the final production implementation.

Known limitations:

Publishing idempotency is not yet implemented.

If Mastodon accepts a post but the worker crashes before the database/Redis acknowledgement completes, a later retry could potentially publish the same content again.

Retry classification should be hardened.

The current implementation uses platform error information to distinguish retryable and permanent failures. A future version should use explicit typed exceptions rather than relying primarily on parsing error-message strings.

HTTP 429 handling should use Retry-After.

The current retry policy uses the project's backoff calculation. Production behavior should respect platform-provided retry timing when available.

Retry jitter should be added.

Jitter will reduce synchronized retry bursts when many jobs fail at the same time.

Dead-letter handling is not yet implemented.

Permanently exhausted jobs could eventually be moved to a dedicated dead-letter queue with an operator-facing recovery mechanism.

Attempt state is currently carried in Redis job metadata.

A future production implementation may also persist important retry/audit information in PostgreSQL.

The Redis claim timestamp update is not fully atomic with the initial queue move.

The current design moves the job into processing and then updates its metadata. This is acceptable for the current stage but should be hardened for production.

Multi-platform partial success is not yet modeled.

Once one logical post can target several platforms, publication status should be tracked per platform.

Production hardening roadmap

Before production, address:

publishing idempotency

external publication identifiers

typed platform exceptions

explicit HTTP/network exception classification

Retry-After support

retry jitter

configurable retry policy

dead-letter queue

persistent retry/audit metadata

encrypted OAuth credentials at rest

production secret management

token rotation/revocation

structured logging

credential-safe logs

rate limiting

monitoring and alerts

frontend approval queue

scheduling/calendar UI

per-platform publication state

analytics

comprehensive failure-path tests

production worker deployment strategy

Next major milestone — Publishing idempotency

The next backend reliability milestone should be idempotency.

The problem:

Worker
↓
Mastodon accepts post
↓
Post is publicly visible
↓
Worker crashes before confirming success
↓
Recovery/retry
↓
Same post may be published again

The target design should introduce an internal publication/idempotency identifier so the system can determine whether an external publication has already been completed.

The goal is:

ONE SOCIALPILOT POST
↓
ONE INTENDED EXTERNAL PUBLICATION

even when:

workers restart

network responses are lost

Redis jobs are recovered

retries occur

multiple workers are active

This should be implemented before considering the publishing infrastructure production-ready.

Recommended next development order

Publishing idempotency
↓

Harden retry/error classification
↓

AI quality + safety checks
↓

Frontend human-review queue
↓

Frontend scheduling/calendar
↓

Generic publisher interface
↓

Additional platform adapters
↓

Analytics
↓

Advanced agentic workflow

The Human-in-the-Loop boundary must remain intact throughout all phases.

Git checkpoint

The scheduled publishing/retry work should be treated as a separate development checkpoint from the earlier Mastodon-only publishing milestone.

The intended checkpoint includes:

Redis queue infrastructure

processing/acknowledgement

stale-job recovery

recovery worker

scheduled publishing

retry classification

exponential backoff

delayed retry promotion

documentation update

Before starting the next major feature, verify:

git status
git log --oneline -5
python -m pytest -v
python -m py_compile <changed Python files>

Do not mark a Git checkpoint as confirmed until the actual terminal output shows a clean/synced working tree and the expected commit exists.

Final project direction

The project has moved from a simple CRUD/social-account prototype toward a real asynchronous social-media publishing system.

The current architecture is:

            SOCIALPILOT AI

                 USER
                  ↓
           Campaign context
                  ↓
            AI generation
                  ↓
                DRAFT
                  ↓
           HUMAN REVIEW
                  ↓
               APPROVE
                  ↓
              SCHEDULE
                  ↓
         PostgreSQL scheduler
                  ↓
            Redis queue
                  ↓
          Publisher worker
                  ↓
         Retry / recovery
                  ↓
          Platform adapter
                  ↓
             Mastodon
                  ↓
            PUBLISHED
                  ↓
          Analytics/feedback

The long-term agentic architecture remains:

Campaign Context
↓
Research/Context Agent
↓
Content Generation Agent
↓
Quality/Safety Checker
↓
HUMAN REVIEW GATE
↓
Platform Adaptation
↓
Scheduler
↓
Publisher
↓
Analytics
↓
Optimization / Feedback

The key architectural rule remains unchanged:

AI can generate, analyze, recommend, rewrite, adapt, and optimize — but it must not silently cross the Human-in-the-Loop approval boundary to create an externally visible side effect.

Living-document maintenance rule

After every major milestone, update this document with:

What was implemented.

Files changed.

Architecture decisions.

Problems encountered.

Exact resolution.

Tests performed.

Failure cases considered.

Security implications.

Known limitations.

Git checkpoint.

Updated project status.

Next recommended milestone.

Historical sections should not be rewritten merely to make the project look cleaner. If the implementation changed direction, preserve the original decision/problem and document the new decision afterward.

Last confirmed major milestone: September 5, 2026 — scheduled Mastodon publishing infrastructure was implemented and the scheduled publishing path was verified end-to-end, including PostgreSQL scheduling, Redis queue processing, publisher execution, successful external publication, acknowledgement, stale-job recovery, and retry infrastructure.

Instagram integration — OAuth milestone

Confirmed: September 10, 2026

Instagram integration was completed far enough to prove the complete OAuth connection flow against the real Instagram/Meta environment.

Goal

Connect an Instagram professional account to SocialPilot AI through Instagram Login, associate it with the authenticated SocialPilot user, obtain a long-lived access token, verify the external account, and persist the connection through the existing SocialAccount architecture.

Architecture

The implementation follows the generic platform integration design rather than adding Instagram-specific logic to the application core:

FastAPI Instagram Route
↓
Instagram OAuth helpers
↓
InstagramClient
↓
Instagram Graph API
↓
SocialAccountService
↓
SocialAccountRepository
↓
PostgreSQL

The publishing architecture remains:

PostService
↓
PublicationService
↓
PlatformRegistry
↓
PlatformPublisher
├── MastodonAdapter
└── InstagramAdapter

This keeps platform-specific API behavior inside the adapter/client boundary.

Files added or changed

app/integrations/instagram/oauth.py
app/integrations/instagram/client.py
app/integrations/instagram/adapter.py
app/api/routes/instagram.py
app/services/social_account.py
app/integrations/platforms/setup.py

The Instagram client owns HTTP communication and converts HTTP/network failures into the generic platform exception types. The adapter implements the generic PlatformPublisher contract and exposes Instagram capabilities without requiring changes to PostService or PublicationService.

OAuth state

Instagram OAuth state was implemented as a signed payload containing the local user ID and a random nonce. The state is signed using the application's JWT secret so the callback can recover the intended SocialPilot user without trusting an unsigned query parameter.

Verification performed:

State generated: True
User ID: 1
Tampered state rejected: YES

Meta configuration problem

The first Instagram OAuth attempt failed with:

Invalid Request: Request parameters are invalid: Invalid redirect_uri

A plain localhost callback was also rejected by Meta when configuring the Instagram business login redirect URL.

Resolution

Local development was placed behind an HTTPS ngrok tunnel. The callback was configured as:

https://<ngrok-host>/social-accounts/instagram/callback

The exact HTTPS callback URI was configured both in the application's .env and in Meta's Instagram business login configuration.

The ngrok agent was initially too old (3.3.1). It was upgraded to 3.39.11, which resolved the ngrok agent compatibility problem.

Swagger OAuth testing problem

Calling /social-accounts/instagram/connect through Swagger displayed:

Failed to fetch
Possible Reasons:
CORS
Network Failure
URL scheme must be "http" or "https" for CORS request.

This was not an application failure. The endpoint correctly returned an OAuth redirect, but Swagger's browser request was not an appropriate way to drive the cross-site OAuth authorization flow.

Resolution

The OAuth authorization URL was obtained using an authenticated PowerShell request and opened directly in the browser.

Real OAuth verification

The complete flow was successfully executed:

Authenticated SocialPilot user
↓
GET /social-accounts/instagram/connect
↓
Instagram authorization
↓
Instagram Tester account authorization
↓
HTTPS ngrok callback
↓
/ social-accounts/instagram/callback
↓
Authorization code exchange
↓
Long-lived token exchange
↓
Instagram /me verification
↓
Create/update SocialAccount
↓
Connected

The successful API response confirmed:

status       = connected
platform     = instagram
account_name = socialpilot_ai

This proves that the real Meta/Instagram OAuth callback, token exchange, account verification, and persistence path work end-to-end.

Instagram account verification

The Instagram Graph API was independently verified using the authenticated token and returned the connected account's ID and username. The same verification is now performed by InstagramClient.get_account() during the OAuth callback.

Instagram publishing limitation

Instagram publishing is intentionally not yet enabled for the existing text-only Post model. Instagram content publishing requires media, while the current Post model contains text content but no media URL/asset reference.

The adapter therefore deliberately rejects the generic text-only publish() path with a PlatformValidationError instead of pretending that Instagram supports a text-only publication.

A dedicated publish_image() path has been implemented in the adapter and is ready to be connected once media support is introduced into the publication model/workflow.

This is an intentional boundary, not a failed integration.

Security considerations

OAuth tokens remain backend-only and are not returned through SocialAccountResponse.

OAuth state is signed and tampering is rejected.

The connected Instagram account is associated with the local SocialPilot user.

Access tokens must never be committed to Git or printed in logs.

OAuth state expiration/replay protection remains future security-hardening work.

OAuth credentials are currently stored in the database but are not yet encrypted at rest; this remains a production hardening item.

Tests

The complete automated test suite remained green after the Instagram integration changes:

70 passed in 49.70s

Python compilation checks also passed for the new/changed Instagram modules.

Milestone result

Instagram OAuth connection       ✅ VERIFIED
Instagram account verification  ✅ VERIFIED
Instagram persistence            ✅ VERIFIED
Generic adapter registration      ✅ VERIFIED
Instagram text publishing        ⏳ MEDIA SUPPORT REQUIRED

Current verified status — September 10, 2026

The project has progressed beyond the earlier scheduled-Mastodon-only checkpoint. The current verified backend state is:

Authentication                         ✅ VERIFIED
User/brand/campaign ownership          ✅ VERIFIED
Post lifecycle                         ✅ VERIFIED
Human-in-the-Loop approval             ✅ VERIFIED
AI generation                          ✅ VERIFIED
Mastodon OAuth                         ✅ VERIFIED
Mastodon real publication              ✅ VERIFIED
Scheduled publishing                   ✅ VERIFIED
Redis processing/recovery              ✅ VERIFIED
Delayed retry/backoff                  ✅ VERIFIED
Publishing persistence                 ✅ VERIFIED
Generic platform registry              ✅ VERIFIED
Platform publisher contract            ✅ VERIFIED
Instagram OAuth                        ✅ VERIFIED
Instagram account persistence          ✅ VERIFIED
Instagram API account verification     ✅ VERIFIED
Instagram text-only publishing         ⏳ MEDIA SUPPORT REQUIRED
Publishing idempotency                 ⏳ HARDENING
DLQ / failure management               ⏳
Security hardening                     ⏳
API error standardization              ⏳
Observability                          ⏳
Comprehensive V1 tests                 ⏳
Health/readiness/API cleanup           ⏳
Deployment                             ⏳

Current architecture

                 USER
                   │
                   ▼
             FastAPI API
                   │
  ┌────────────────┼────────────────┐
  ▼                ▼                ▼
Auth        Brand/Campaign        Posts
                                     │
                                     ▼
                               PostService
                                     │
            ┌────────────────────────┼──────────────────────┐
            ▼                        ▼                      ▼
       AI generation          HITL review             Scheduling
            │                        │                      │
            └──────────────► DRAFT / APPROVED             ▼
                                                          PostgreSQL
                                                              │
                                                              ▼
                                                       Redis queues
                                                              │
                                                              ▼
                                                       Publisher worker
                                                              │
                                                              ▼
                                                     PublicationService
                                                              │
                                                              ▼
                                                      PlatformRegistry
                                                              │
                                     ┌────────────────────────┴──────────────┐
                                     ▼                                       ▼
                              MastodonAdapter                         InstagramAdapter
                                     │                                       │
                                     ▼                                       ▼
                               Mastodon API                           Instagram API

The Human-in-the-Loop boundary remains mandatory:

AI generation
↓
DRAFT
↓
PENDING_REVIEW
↓
HUMAN APPROVAL
↓
APPROVED
↓
SCHEDULE / PUBLISH

AI does not receive authority to approve or publish its own generated content.

Next major milestone

The next backend milestone remains scheduling and publishing hardening, beginning with publishing idempotency and durable per-publication state/recovery improvements. Instagram media support can then be integrated without weakening the generic platform architecture.

Git checkpoint — Instagram integration

The Instagram OAuth milestone should be committed as a separate development checkpoint.

Before committing, verify:

git status
python -m pytest -v
python -m py_compile app/integrations/instagram/oauth.py app/integrations/instagram/client.py app/integrations/instagram/adapter.py app/api/routes/instagram.py app/services/social_account.py app/integrations/platforms/setup.py

Expected test result:

70 passed

Recommended commit message:

feat: complete Instagram OAuth integration

After the commit, verify:

git status
git log --oneline -3

The working tree should be clean before moving to the next milestone.

Development direction after Instagram

The immediate order remains:

Instagram OAuth                         ✅
↓
Publishing idempotency                  NEXT
↓
Scheduling/retry hardening              NEXT
↓
Dead-letter/failure management           NEXT
↓
Security hardening                       NEXT
↓
API error standardization                NEXT
↓
Observability                            NEXT
↓
Comprehensive V1 tests                   NEXT
↓
Health/readiness/API cleanup             NEXT
↓
Deployment                               NEXT

X/Twitter remains intentionally deferred during development because of API cost/access considerations. Additional platforms, analytics, autonomous posting, and frontend work should not displace the reliability and safety milestones above.

The project continues to prioritize: modular architecture, low coupling, durable state, failure recovery, platform abstraction, and Human-in-the-Loop safety.

Last confirmed major milestone: September 10, 2026 — Instagram OAuth was connected and verified end-to-end using the real Meta/Instagram environment, including HTTPS callback handling, authorization-code exchange, long-lived token exchange, account verification, and SocialAccount persistence. The automated test suite remained green at 70 passing tests.

Publishing idempotency — completed

Confirmed: September 11, 2026

Publishing idempotency was implemented as part of the durable publication
architecture.

The system now uses a stable publication key so that one logical
SocialPilot post -> social-account publication has a durable identity.

The Post model contains:

publication_key
external_post_id
publication_attempts

The durable Publication model contains:

post_id
social_account_id
platform
publication_key
status
attempt_count
external_post_id
last_error
retry_after_seconds
first_attempt_at
last_attempt_at
published_at
publication_metadata

The Publication table also enforces uniqueness for:

post_id + social_account_id

and publication_key is unique.

This provides a durable identity for external publication attempts and
prevents the application from treating every retry as a completely new
publication operation.

The publication flow is now conceptually:

Post
↓
PublicationService
↓
stable publication_key
↓
Publication record
↓
PUBLISHING
↓
PlatformPublisher
↓
external platform
↓
external_post_id
↓
PUBLISHED

This is an important reliability boundary because external publication can
succeed even when the worker does not receive or persist the response.

Scheduling and retry hardening — completed

Confirmed: September 11, 2026

The scheduler/retry system was hardened beyond the earlier baseline.

Completed reliability work includes:

PostgreSQL remains the source of truth for post state.

Scheduled posts are atomically claimed using:
SCHEDULED → PUBLISHING.

Redis contains separate pending, processing, delayed, and dead-letter
states.

Redis jobs retain stable job IDs across transitions.

Worker crashes can leave jobs in the processing queue for recovery.

Stale processing jobs are checked against PostgreSQL before recovery.

Already-published and already-failed posts are not blindly requeued.

Retryable failures use delayed retry instead of immediate repeated
execution.

Exponential backoff is supported.

Retry jitter is supported.

Platform-provided Retry-After values are respected when available.

Retry behavior is configurable through RetryPolicy.

Failed jobs can be moved to the dead-letter queue after permanent failure
or retry exhaustion.

The recovery rule is intentionally conservative:

RECONCILIATION
│
├── publication found
│       ↓
│    persist PUBLISHED
│
├── publication not found / unsupported
│       ↓
│    recovery may requeue
│
└── reconciliation error
↓
DO NOT REPUBLISH
↓
preserve ambiguous state

This prevents a temporary inability to query the external platform from
being interpreted as proof that publication did not occur.

Known implementation limitation:

The initial Redis dequeue/claim flow moves a job into the processing queue
and then updates its claimed_at metadata. That metadata update is not fully
atomic with the initial queue move and remains a production-hardening item.

Dead-letter queue and failure management — completed

Confirmed: September 11, 2026

Publishing failures are now explicitly managed instead of being silently
lost after retry exhaustion or permanent platform failure.

Redis queues:

socialpilot
socialpilot
socialpilot
socialpilot

The publisher worker distinguishes:

Permanent failure
↓
FAILED
↓
DLQ

Retryable failure
↓
retry metadata
↓
delayed queue
↓
retry promoter
↓
main queue

Retry exhaustion follows:

maximum attempts reached
↓
FAILED
↓
DLQ

A stable job ID is preserved across pending, processing, delayed, recovery,
and dead-letter transitions.

The worker only acknowledges a job after the publication workflow has
completed. If the DLQ transition itself fails, the processing job remains
unacknowledged so the failure is not silently discarded.

Tests cover:

stable job IDs across queue transitions

retry transitions

delayed promotion

stale recovery

DLQ movement

permanent failures

retry exhaustion

DLQ acknowledgement

missing processing jobs

retryable rate-limit behavior

Security hardening — OAuth encryption and secret validation

Confirmed: September 11, 2026

OAuth credential security was hardened at the database persistence
boundary.

Previously, SocialAccount stored:

access_token
refresh_token

as plaintext database values.

The new architecture is:

OAuth provider
↓
SocialAccount ORM
↓
EncryptedToken
↓
Fernet encryption
↓
PostgreSQL / Supabase

The implementation uses:

app/core/encryption.py

and the SQLAlchemy:

EncryptedToken

TypeDecorator.

Application code continues to receive normal token strings, while the
database stores ciphertext.

The SocialAccount model now uses EncryptedToken for:

access_token
refresh_token

SocialAccountResponse continues to exclude both credentials from API
responses.

Security configuration was strengthened in:

app/core/config.py

JWT_SECRET is now required and must:

be configured;

contain at least 32 characters; and

not use the previous development-only-secret value.

TOKEN_ENCRYPTION_KEY is also required and is used as the Fernet encryption
key.

The cryptography dependency was added:

cryptography==50.0.1

Database logging was also hardened. SQLAlchemy echo logging was disabled
independently of application debug mode because SQL echo output can expose
bound parameter values.

Existing OAuth credentials

There were two existing connected SocialAccount records when encryption
was introduced.

The credentials were migrated to encrypted storage without changing the
external accounts.

An initial migration attempt exposed an important implementation issue:
manually encrypting the ORM value while also using the EncryptedToken
SQLAlchemy type caused double encryption.

This was detected and repaired before the milestone was closed. The
existing records were normalized so each persisted credential now has one
encryption layer.

The temporary repair script was deleted after migration.

Important rule:

OAuth credentials must never be committed to Git or printed in logs.

The project's .env file remains ignored by Git.

Security verification and regression status

Confirmed: September 11, 2026

Security hardening was committed and pushed successfully.

Git checkpoint:

c91cb3a feat: harden OAuth credential security

Previous reliability checkpoints:

49b761d feat: add publishing dead letter queue
89ed0af fix: harden scheduling recovery reconciliation

The verified Git state was:

On branch dev
Your branch is up to date with 'origin/dev'.

nothing to commit, working tree clean

This confirms that the security changes are committed and synchronized
with origin/dev.

The full automated regression suite remains:

79 passed in 56.07s

The security milestone therefore closed with:

OAuth credentials hidden from API responses       VERIFIED
OAuth credentials encrypted at rest               VERIFIED
Existing credentials migrated                     VERIFIED
JWT fallback secret removed                       VERIFIED
JWT secret minimum validation                     VERIFIED
Fernet key configuration validation                VERIFIED
SQLAlchemy SQL/value echo disabled                VERIFIED
Git working tree clean                            VERIFIED
Remote branch synchronized                        VERIFIED
79 automated tests                                PASSING

Current verified project status — September 11, 2026

The current backend has progressed substantially beyond the original
CRUD/social-account prototype.

Authentication                         VERIFIED
User/brand/campaign ownership          VERIFIED
Post lifecycle                         VERIFIED
Human-in-the-Loop approval             VERIFIED
AI generation                          VERIFIED
Mastodon OAuth                         VERIFIED
Mastodon real publication              VERIFIED
Scheduled publishing                   VERIFIED
Redis processing/recovery              VERIFIED
Delayed retry/backoff                  VERIFIED
Retry jitter                           VERIFIED
Retry-After handling                   VERIFIED
Publishing persistence                 VERIFIED
Publishing idempotency                 VERIFIED
Generic platform registry              VERIFIED
Platform publisher contract            VERIFIED
Instagram OAuth                        VERIFIED
Instagram account persistence          VERIFIED
Instagram API verification             VERIFIED
Dead-letter queue                      VERIFIED
Failure management                     VERIFIED
OAuth credential encryption            VERIFIED
JWT secret hardening                   VERIFIED
Credential-safe SQL logging            VERIFIED
Instagram text publishing              DEFERRED — MEDIA REQUIRED

Current next milestone:
API error standardization

Following milestones:

API error standardization
↓
Observability
↓
Comprehensive V1 tests
↓
Health/readiness/API cleanup
↓
Deployment

Instagram media support remains intentionally deferred until the reliability
and safety milestones are sufficiently complete.

X/Twitter remains intentionally deferred during development because of
API cost/access considerations. It should be added later without changing
the generic publisher architecture.

Current architecture — September 11, 2026

             USER
               │
               ▼
          FastAPI API
               │

┌────────────────┼────────────────┐
▼                ▼                ▼
Auth        Brand/Campaign        Posts
│
▼
PostService
│
┌────────────────────────┼──────────────────────┐
▼                        ▼                      ▼
AI generation          HITL review             Scheduling
│                        │                      │
▼                        ▼                      ▼
DRAFT                APPROVAL GATE          PostgreSQL
│                      │
▼                      ▼
APPROVED              Atomic claim
│
▼
Redis queues
│
┌─────────────────────────────┤
▼                             ▼
Delayed retry                 Processing queue
│                             │
▼                             ▼
Retry promoter               Publisher worker
│
▼
PublicationService
│
▼
PlatformRegistry
│
┌──────────────────────┴─────────────┐
▼                                    ▼
MastodonAdapter                       InstagramAdapter
│                                    │
▼                                    ▼
Mastodon API                         Instagram API
│
▼
PUBLISHED
│
▼
external_post_id

The architecture maintains clear separation between:

API concerns

business logic

persistence

queueing

publication state

external platform adapters

AI generation

human approval

The Human-in-the-Loop boundary remains mandatory:

AI generation
↓
DRAFT
↓
PENDING_REVIEW
↓
HUMAN APPROVAL
↓
APPROVED
↓
SCHEDULE / PUBLISH

AI cannot approve or publish its own generated content.

Current production-hardening backlog

The major V1 reliability milestones are now substantially implemented.

Remaining work:

API error standardization

consistent error response schema

centralized exception handlers

safe error messages

request/correlation identifiers where appropriate

avoid leaking raw integration exceptions

Observability

structured logging

safe logging around OAuth and publishing

worker metrics

queue/retry metrics

publication failure visibility

Comprehensive V1 tests

encryption-specific tests

API error-handler tests

failure-path coverage

integration regression coverage

concurrency/recovery tests

Health/readiness/API cleanup

liveness endpoint

readiness checks

dependency health

API consistency

final OpenAPI cleanup

Deployment

production secrets

worker deployment

Redis deployment

PostgreSQL/Supabase configuration

environment separation

operational monitoring

Later work:

Instagram media model/workflow

frontend human-review queue

scheduling/calendar UI

additional platform adapters

analytics

advanced agentic workflows

X/Twitter remains deferred during development because of API cost/access
considerations.

Updated V1 roadmap

The current development order is:

Instagram OAuth                         COMPLETED
↓
Publishing idempotency                  COMPLETED
↓
Scheduling/retry hardening              COMPLETED
↓
Dead-letter/failure management          COMPLETED
↓
Security hardening                      COMPLETED
↓
API error standardization               NEXT
↓
Observability                           NEXT
↓
Comprehensive V1 tests                  NEXT
↓
Health/readiness/API cleanup            NEXT
↓
Deployment                              NEXT

The following are deliberately outside the immediate V1 reliability path:

X/Twitter integration

additional social platforms

analytics

autonomous posting

frontend implementation

Instagram media publishing

The project continues to prioritize:

modularity
low coupling
high cohesion
durable state
failure recovery
platform abstraction
security
auditability
Human-in-the-Loop safety

Latest Git checkpoint

Latest confirmed commit:

c91cb3a feat: harden OAuth credential security

Recent history:

c91cb3a feat: harden OAuth credential security
49b761d feat: add publishing dead letter queue
89ed0af fix: harden scheduling recovery reconciliation

The branch was confirmed synchronized:

dev = origin/dev

Working tree:

clean

Before every future milestone, verify:

git status
git log --oneline -5
python -m pytest -q
python -m py_compile <changed Python files>

A Git checkpoint should only be marked confirmed when the actual terminal
output shows both the expected commit and a clean/synchronized working tree.

Living-document rule — updated

After every major milestone, this document must record:

what was implemented;

exact files changed;

architecture decisions;

problems encountered;

exact resolution;

tests performed;

failure cases considered;

security implications;

known limitations;

Git checkpoint;

updated project status;

next recommended milestone.

Historical sections should remain intact. If a previous plan changes,
document the new decision afterward rather than rewriting history.

The current authoritative development state is the latest dated section of
this document.

Current project checkpoint

Date: September 11, 2026

SocialPilot AI has moved from a basic social-media CRUD prototype to a
durable asynchronous publishing backend with:

JWT authentication

ownership enforcement

campaign/post lifecycle management

mandatory Human-in-the-Loop approval

local AI generation through Ollama

Mastodon OAuth and real publishing

Instagram OAuth and account verification

generic platform abstraction

durable per-publication state

publishing idempotency

PostgreSQL-backed scheduling

Redis queue processing

stale-job recovery

delayed retries

exponential backoff

retry jitter

Retry-After support

dead-letter failure management

OAuth credential encryption at rest

JWT secret validation

credential-safe database logging

79 passing automated tests

The next implementation target is:

API ERROR STANDARDIZATION

The key architectural invariant remains:

AI may generate, analyze, recommend, rewrite, adapt, and optimize.

AI must not silently cross the Human-in-the-Loop approval boundary to create
an externally visible side effect.

Current authoritative project update — September 12, 2026

This section supersedes earlier "current status", roadmap, and next-step
statements where they conflict with the implementation actually verified
after September 11, 2026. Historical sections above are intentionally
preserved.

Latest verified backend state:

Authentication                         COMPLETED
User/brand/campaign ownership          COMPLETED
Post lifecycle                         COMPLETED
Human-in-the-Loop approval             COMPLETED
AI generation                          COMPLETED
Mastodon OAuth                         COMPLETED
Mastodon real publishing               COMPLETED
Instagram OAuth                        COMPLETED
Instagram account verification         COMPLETED
Generic platform abstraction           COMPLETED
Publishing persistence                 COMPLETED
Publishing idempotency                 COMPLETED
PostgreSQL scheduling                  COMPLETED
Redis queue processing                 COMPLETED
Stale-job recovery                     COMPLETED
Delayed retries                        COMPLETED
Exponential backoff                    COMPLETED
Retry jitter                           COMPLETED
Retry-After support                    COMPLETED
Dead-letter failure management         COMPLETED
OAuth credential encryption            COMPLETED
JWT secret hardening                   COMPLETED
API error standardization              COMPLETED
Request correlation IDs                COMPLETED
Request timing/logging                 COMPLETED
Database/model alignment               COMPLETED
Alembic migration-chain verification   COMPLETED
Comprehensive V1 tests                 IN PROGRESS

Intentional limitation:

Instagram text-only publishing is not enabled because the current Post model
does not yet contain media/asset support. The generic Instagram adapter rejects
unsupported text-only publication rather than creating an invalid external
publication.

X/Twitter remains intentionally deferred during development because of API
cost/access considerations.

Additional platforms, analytics, autonomous posting, and frontend work remain
outside the immediate reliability path.

API error standardization — completed

Confirmed during the September 11, 2026 development checkpoint.

A centralized API error-handling layer was implemented.

Files:

app/api/errors.py
app/api/middleware.py
app/main.py
tests/test_auth.py
tests/test_observability.py

The standardized API error structure is:

{
"error": {
"code": "<MACHINE_READABLE_CODE>",
"message": "<SAFE_USER_FACING_MESSAGE>"
}
}

Validation errors additionally expose structured validation details.

Supported stable error categories include:

400 BAD_REQUEST
401 UNAUTHORIZED
403 FORBIDDEN
404 NOT_FOUND
409 CONFLICT
422 VALIDATION_ERROR
429 RATE_LIMITED
500 INTERNAL_SERVER_ERROR
502 BAD_GATEWAY
503 SERVICE_UNAVAILABLE
504 GATEWAY_TIMEOUT

Unexpected exceptions are logged server-side while the API returns a safe
generic 500 response without exposing internal implementation details.

Observability — completed

Confirmed during the September 11, 2026 development checkpoint.

The API now assigns a request correlation ID to every request.

Behavior:

Client supplies X-Request-ID
↓
API preserves the ID
↓
request.state.request_id
↓
request logging
↓
response includes X-Request-ID

If the client does not provide an ID, the application generates a UUID.

Request logs include:

request_id
HTTP method
path
status code
duration_ms

Unexpected API exceptions are also logged with exception information.

Files:

app/api/middleware.py
app/core/logging.py
app/api/errors.py
app/main.py
tests/test_observability.py

Verification includes:

request IDs are present;
client-provided IDs are preserved;
generated IDs differ across requests;
completed requests produce observability logs;
standardized error responses retain request correlation.

Security hardening — completed

Confirmed and committed as:

c91cb3a feat: harden OAuth credential security

Implemented security controls include:

Fernet-based OAuth token encryption at rest.

TOKEN_ENCRYPTION_KEY configuration.

JWT secret minimum-length validation.

Rejection of the known development-only JWT secret.

SQLAlchemy SQL echo disabled so sensitive values are not unnecessarily written
to logs.

Existing social-account records were migrated from plaintext credential
storage to encrypted storage.

A double-encryption issue encountered during migration was detected and
repaired before completion.

The API continues to exclude access_token and refresh_token from normal
SocialAccount responses.

Database migration and Alembic verification — completed

Confirmed September 12, 2026.

Alembic is configured for the existing PostgreSQL database and uses:

migrations/env.py
target_metadata = Base.metadata

The migration history is a single linear chain with one head:

4b42d7984e51
↓
b997374496db
↓
7d0c6afb1202
↓
258587792be4
↓
9f31b34c1261
↓
6eb26de38e4e
↓
5f8a1c2d9e31
↓
6a91d4e7c2b0

Verified:

alembic current
6a91d4e7c2b0 (head)

alembic heads
6a91d4e7c2b0 (head)

There is exactly one migration head.

Model/schema alignment was required because Alembic initially detected type
and index differences between the live database and SQLAlchemy metadata.

The following models were aligned:

app/models/user.py
app/models/brand.py
app/models/campaign.py
app/models/post.py
app/models/social_account.py

Important alignment decisions:

User/Brand/Campaign fields that already exist as BIGINT in PostgreSQL were
modeled as BigInteger.

Existing named indexes such as:

idx_brands_user_id
idx_campaigns_brand_id

were preserved rather than replaced with automatically generated names.

posts.campaign_id remains INTEGER because the existing database column is
INTEGER.

social_accounts.user_id remains INTEGER because the existing database column
is INTEGER.

Final verification:

No new upgrade operations detected.

No additional schema-changing migration was required for these model
corrections.

Comprehensive V1 test baseline — in progress

The automated suite currently contains:

84 passing tests

Latest verification:

python -m pytest -q

Result:

84 passed

The suite remained green through the database-model alignment work.

The comprehensive V1 testing phase will expand coverage rather than rewrite
the existing suite.

Priority areas:

authentication;
authorization;
ownership isolation;
brand/campaign access;
post lifecycle;
Human-in-the-Loop enforcement;
publishing idempotency;
durable Publication state;
retry classification;
retry exhaustion;
dead-letter queue behavior;
stale-job recovery;
scheduling/reconciliation;
platform registry;
Mastodon adapter behavior;
Instagram OAuth;
encrypted credential behavior;
standardized API errors;
request correlation IDs;
AI generation failure handling;
health/readiness behavior.

The goal is to verify successful paths as well as failure, recovery, security,
concurrency, and duplicate-execution scenarios.

Current publication architecture

The current publication architecture is:

PostService
↓
PublicationService
↓
PlatformRegistry
↓
PlatformPublisher
├── MastodonAdapter
└── InstagramAdapter
↓
future adapters

The application core should not contain platform-specific HTTP branches.

Publication state is persisted separately from the logical Post so that one
logical post can eventually target multiple social accounts/platforms.

The Publication model contains durable state including:

post_id
social_account_id
platform
publication_key
status
attempt_count
external_post_id
last_error
retry_after_seconds
first_attempt_at
last_attempt_at
published_at
publication_metadata

The uniqueness rule for:

post_id + social_account_id

prevents duplicate durable publication records for the same logical
Post-to-SocialAccount relationship.

Current scheduling and failure architecture

PostgreSQL remains the source of truth for publication state.

The scheduled publishing flow is:

APPROVED
↓
SCHEDULED
↓
PostgreSQL due-post detection
↓
atomic SCHEDULED → PUBLISHING claim
↓
Redis scheduled-post queue
↓
Redis processing queue
↓
Publisher worker
↓
Platform adapter
↓
External platform
↓
PUBLISHED
↓
Redis acknowledgement

Failure paths:

Retryable failure
↓
retry metadata
↓
delayed Redis queue
↓
retry promoter
↓
main Redis queue
↓
publisher

Permanent failure / retry exhaustion
↓
Post FAILED
↓
Redis dead-letter queue

Worker crash:

processing queue
↓
stale claimed_at
↓
recovery worker
↓
check PostgreSQL state
├── PUBLISHED → remove/ack job
├── FAILED    → remove/ack job
├── invalid   → remove/ack job
└── PUBLISHING → recover/requeue

The recovery logic fails closed when reconciliation cannot determine the
external state. An unknown external state must not automatically trigger a
duplicate publication.

Current retry and DLQ policy

RetryPolicy currently supports:

maximum attempts: 5
initial backoff: 30 seconds
maximum backoff: 15 minutes
jitter ratio: 20 percent

Exponential backoff examples:

Attempt 1 → 30 seconds
Attempt 2 → 60 seconds
Attempt 3 → 120 seconds
Attempt 4 → 240 seconds

Platform-provided retry timing is respected when available, subject to the
configured maximum backoff.

Retryable failures are delayed rather than immediately requeued.

Permanent failures and exhausted retry attempts are moved to the dead-letter
queue with failure metadata.

Redis job IDs remain stable across queue transitions so retries, recovery, and
DLQ handling continue to refer to the same logical job.

Current Git checkpoint

Latest confirmed commit:

7959630 fix: align models with database schema

The commit was pushed successfully to:

origin/dev

Verification:

git status

Result:

On branch dev
Your branch is up to date with 'origin/dev'.
nothing to commit, working tree clean

Recent history includes:

7959630 fix: align models with database schema
a67d755 feat: standardize API errors and add observability
c91cb3a feat: harden OAuth credential security
49b761d feat: add publishing dead letter queue
89ed0af fix: harden scheduling recovery reconciliation
417345d feat: complete Instagram OAuth integration
af865bd feat: complete multi-platform publication architecture

Authoritative V1 roadmap

The implementation order is now:

Publishing idempotency                         COMPLETED

Durable publication/audit state                COMPLETED

Multi-platform publication architecture        COMPLETED

Instagram OAuth                                COMPLETED

Scheduling hardening/reconciliation             COMPLETED

DLQ/failure management                          COMPLETED

Security hardening                              COMPLETED

API error standardization                       COMPLETED

Observability                                   COMPLETED

DB/Alembic model and migration verification   COMPLETED

Comprehensive V1 tests                         NEXT

Health/readiness/version/API cleanup           PENDING

Deployment                                     PENDING

The following remain intentionally outside the immediate V1 reliability path:

X/Twitter integration
additional social platforms
analytics
autonomous posting
frontend implementation
Instagram media publishing

Current architecture invariant

The central safety boundary remains unchanged:

Campaign context
↓
AI generation
↓
DRAFT
↓
PENDING_REVIEW
↓
HUMAN REVIEW
├── REJECT → revise/regenerate
└── APPROVE
↓
APPROVED
↓
SCHEDULED
↓
PUBLISHING
↓
PUBLISHED

AI may:

generate;
analyze;
recommend;
rewrite;
adapt;
summarize;
optimize.

AI must not silently cross the Human-in-the-Loop approval boundary to create
an externally visible side effect.

Every externally visible operation must continue to have:

state management;
ownership checks;
validation;
failure handling;
retry/recovery behavior where appropriate;
idempotency considerations;
auditability.

Current definition of done

A feature is not considered complete merely because an endpoint returns 200.

For externally connected functionality:

Implementation
↓
Import/unit validation
↓
API validation
↓
Database validation
↓
External integration validation where applicable
↓
Failure-path testing
↓
Security review
↓
Documentation update
↓
Git commit/push
↓
Clean working tree

For database changes, additionally verify:

alembic current
alembic heads
alembic history --verbose
alembic check

No migration should be generated solely to silence Alembic. The intended
database schema and SQLAlchemy metadata must be understood first.

Next development checkpoint

The immediate next milestone is:

COMPREHENSIVE V1 TESTS

The first step is to inventory the existing test suite and map current tests
to the V1 reliability requirements.

Priority should be given to missing negative-path coverage rather than simply
adding more happy-path tests.

The next test work should specifically protect:

HITL approval as a mandatory boundary;
ownership isolation;
publication idempotency;
durable Publication state;
retry/DLQ transitions;
reconciliation safety;
OAuth credential secrecy;
API error contracts;
request correlation;
AI failure safety;
platform abstraction.

Latest verified checkpoint summary

Date: September 12, 2026

Tests:

84 passed

Alembic current:

6a91d4e7c2b0 (head)

Alembic heads:

6a91d4e7c2b0 (head)

Migration heads:

1

Alembic schema check:

No new upgrade operations detected.

Git:

7959630 fix: align models with database schema

Remote:

origin/dev synchronized

Working tree:

clean

Current next milestone:

Comprehensive V1 tests

The project is now a durable asynchronous social-media publishing backend
with AI-assisted content generation, mandatory Human-in-the-Loop approval,
platform abstraction, persistent publication state, scheduling, Redis
processing, retries, stale-job recovery, dead-letter handling, encrypted
OAuth credentials, standardized API errors, and request-level observability.

The key architectural rule remains:

AI can generate and recommend.

A human must approve before externally visible publication.