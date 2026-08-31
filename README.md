SocialPilot AI
AI Social Media Agent with Human-in-the-Loop Approval
> An agentic AI-powered social media management platform that automates campaign planning, content generation, content review, scheduling, publishing, and analytics while keeping humans in control of consequential publishing decisions.
> **Revision note:** This version keeps the original V1 scope (Section 32) and background-processing stack (Redis/Celery/Celery Beat, Section 13) unchanged. Changes in this revision are: (1) LangGraph-native human-in-the-loop instead of a fully custom approval queue, (2) closing several security/reliability gaps — approval staleness on edit, a regeneration attempt cap, prompt-injection defense for uploaded brand documents, and explicit encryption for stored OAuth tokens, (3) recommending X (or another low-friction platform) over LinkedIn for the V1 platform, and (4) making the content reviewer's factuality check a concrete, checkable mechanism rather than a self-reported LLM score.
---
1. Project Overview
SocialPilot AI is an agentic AI-based social media management system designed to automate repetitive social media workflows while maintaining human oversight and control.
The system allows a user to define a brand and campaign objective. AI agents then create a campaign strategy, generate platform-specific content, review the generated content against brand guidelines and quality requirements, and present the content to a human for approval.
Only approved content can be scheduled and published.
After publishing, the system can collect available performance metrics and use historical performance to generate recommendations for future campaigns.
The project focuses on controlled AI automation, rather than completely autonomous publishing.
---
2. Problem Statement
Social media management involves several repetitive and time-consuming activities:
Campaign planning
Content generation
Platform-specific adaptation
Brand consistency checking
Content review
Scheduling
Publishing
Performance monitoring
Analytics
Future campaign planning
Although generative AI can automate much of this workflow, unrestricted AI automation creates several risks:
Hallucinated information
Unsupported claims
Incorrect tone
Brand inconsistencies
Repetitive content
Platform-inappropriate formatting
Unsafe content
Accidental publishing
Incorrect recommendations
Prompt injection from untrusted uploaded content (e.g. brand documents used for RAG)
SocialPilot AI addresses these challenges through an Agentic AI + Human-in-the-Loop architecture.
The AI performs repetitive cognitive tasks, while the human retains final authority over publishing.
---
3. Core Project Idea
The complete system follows this workflow:
    USER
      |
      v
    Create / Select Brand
      |
      v
    Create Campaign
      |
      v
    Campaign Objective
      |
      v
    AI Campaign Planner
      |
      v
    Campaign Strategy
      |
      v
    AI Content Generator
      |
      v
    Platform-Specific Content
      |
      v
    AI Content Reviewer
      |
      v
    Brand / Safety Validation
      |
      v
    Quality Threshold
       /        \
     FAIL       PASS
      |           |
      v           v
    Regenerate  Human Approval
                  /       \
              Reject     Approve
                |           |
                v           v
            Regenerate    Schedule
                              |
                              v
                        Approval Check
                              |
                              v
                        Authentication
                              |
                              v
                        Platform Adapter
                              |
                              v
                        Social Media API
                           /       \
                      SUCCESS      FAILURE
                         |            |
                         v            v
                     Published      Retry
                         |
                         v
                     Analytics
                         |
                         v
                 Performance Analysis
                         |
                         v
                  Recommendations
                         |
                         v
                  Future Campaigns

---
4. Project Objectives
The main objectives of SocialPilot AI are:
Build an AI-powered social media management platform.
Implement an agentic workflow using LangGraph, using LangGraph's native interrupt/checkpoint mechanism for human-in-the-loop pauses.
Automatically generate campaign strategies.
Generate platform-specific social media content.
Automatically review AI-generated content.
Enforce configurable brand guidelines.
Detect potentially unsupported or risky claims using a concrete, checkable mechanism, not only a self-reported LLM score.
Provide explainability for AI decisions.
Introduce mandatory human approval before publishing, re-validated any time content changes after approval.
Allow rejected content to be regenerated, within a bounded number of attempts.
Schedule approved posts.
Publish posts through authenticated social media APIs.
Handle publishing failures and retries.
Maintain campaign and content history.
Collect available social media performance metrics.
Analyze historical content performance.
Generate recommendations for future campaigns.
Keep the LLM provider replaceable.
Make the system testable without depending on paid AI APIs.
Build the system using modular and extensible architecture.
Treat uploaded brand/product documents as untrusted input and defend against prompt injection before they reach the LLM.
---
5. Functional Scope
5.1 User Management
The application will provide basic user authentication.
Users will be able to:
Register
Login
Logout
Manage their profile
Access their own campaigns
Access their own generated content
Connect their social media accounts
Application authentication will be separate from social media OAuth authentication.
---
5.2 Brand Management
Users will be able to create and configure a brand profile.
The brand profile can contain:
Brand name
Brand description
Target audience
Preferred tone
Writing style
Preferred terminology
Restricted terminology
Brand rules
Content preferences
Product information
Example
    Brand:
    CyberShield AI

    Tone:
    Professional + Educational

    Target Audience:
    Cybersecurity Professionals

    Preferred Terms:
    AI Security
    Threat Detection
    Explainable AI

    Avoid:
    Guaranteed
    100% secure
    Perfect protection

These rules will be provided to the AI during content generation and review.
---
5.3 Campaign Management
Users will be able to create campaigns.
A campaign may contain:
Campaign name
Campaign objective
Main topic
Target audience
Campaign duration
Target platforms
Number of posts
Preferred tone
Call-to-action style
Example
    Campaign:
    AI Cybersecurity Awareness

    Objective:
    Increase awareness about Explainable AI

    Target Audience:
    Cybersecurity Professionals

    Duration:
    7 Days

    Platforms:
    LinkedIn
    Instagram

---
5.4 AI Campaign Planner
The AI Campaign Planner converts a campaign objective into a structured content strategy.
Example
    Campaign Objective
            |
            v
    AI Campaign Planner
            |
            v
    +-----------------------------+
    | Day 1 → Problem Awareness   |
    | Day 2 → Educational Content |
    | Day 3 → Product Introduction|
    | Day 4 → Use Case            |
    | Day 5 → Technical Insight   |
    | Day 6 → Customer Problem    |
    | Day 7 → Call to Action      |
    +-----------------------------+

The planner considers:
Campaign objective
Target audience
Brand tone
Platform
Desired frequency
Previous content
Campaign duration
The output should be structured so downstream agents can consume it reliably.
---
5.5 AI Content Generator
The Content Generator produces social media posts based on the campaign plan.
The system should not simply copy the same post to every platform.
Instead, platform-specific variants should be generated.
    Campaign Plan
          |
          v
    Content Generator
          |
          +----> LinkedIn Version
          |
          +----> Instagram Version
          |
          +----> X Version

Generation may consider:
Platform-specific length
Platform formatting
Audience
Tone
Hashtags
Call-to-action
Content type
Brand rules
Campaign objective
---
5.6 AI Content Reviewer
Every generated post should be reviewed before reaching the human approval stage.
The reviewer can evaluate:
Brand alignment
Readability
Platform suitability
Engagement potential
Factuality
Safety
Unsupported claims
Repetition
Spam-like behavior
Tone consistency
Factuality and unsupported-claims check (concrete mechanism)
A single LLM grading its own output on "factuality" is not a reliable signal — self-evaluation is exactly where hallucination tends to hide. The reviewer should instead combine:
Absolute-claim detection. A keyword/regex pass flags high-risk phrasing regardless of LLM score (e.g. "guaranteed," "100%," "always," "never fails," "completely secure," "risk-free"). Any match forces at least a warning, independent of the LLM's own assessment.
Grounding against source documents. Where brand/product documentation has been provided (Section 5.11), specific factual claims in the draft (numbers, capabilities, comparisons) are checked for support in the retrieved context. Claims with no matching source passage are flagged as unsupported rather than assumed true.
LLM judgment as a secondary signal. The reviewer LLM's own factuality/safety score is still used, but as one input alongside 1 and 2 — not the sole basis for a PASS decision.
Example Review
    Brand Alignment:       93/100
    Platform Fit:          89/100
    Readability:           95/100
    Engagement Potential:  84/100
    Risk:                  LOW

    Overall Score:         91/100

    Issue:
    An unsupported product capability was detected
    (no matching source passage; absolute-claim pattern matched: "guaranteed").

    Recommendation:
    Remove or rephrase the claim.

    Decision:
    PASS

---
5.7 AI Regeneration
If the generated content does not meet the required quality threshold, it can be sent back for regeneration.
    Generate
       |
       v
    Review
       |
       v
    Score < Threshold?
       |
       +---- YES ----> Regenerate
       |
       +---- NO -----> Human Approval

Human feedback can also be used during regeneration.
Example
    Human Feedback:

    "Too promotional."

            |
            v

    AI Regeneration

            |
            v

    More educational version

The system should maintain version history so previous versions are not lost.
Regeneration attempt cap
The generate → review → fail → regenerate loop must be bounded. A per-post `regeneration_attempts` counter is tracked in state; once it reaches a configured maximum (e.g. 3), the workflow stops auto-regenerating and routes the post to human review with the review issues attached, rather than looping indefinitely. This bounds LLM cost and prevents a persistently unsatisfiable brand-rule/prompt combination from looping forever.
---
5.8 Human-in-the-Loop Approval
Human approval is one of the core features of SocialPilot AI.
AI-generated content must enter an approval queue before publishing.
Possible content states:
    DRAFT
      |
      v
    AI_REVIEWED
      |
      v
    PENDING_APPROVAL
      |
      +----> REJECTED
      |          |
      |          v
      |      REGENERATE
      |
      +----> APPROVED
                 |
                 v
              SCHEDULED

The human can:
Approve
Reject
Edit
Request regeneration
Provide feedback
Implementation: LangGraph-native interrupt, not a separate custom queue
Rather than building the approval "pause" as fully custom application logic sitting outside the graph, the LangGraph workflow node responsible for human approval should use LangGraph's built-in `interrupt()` and checkpointing support. The graph pauses at the approval node, its full state is persisted automatically, and the workflow resumes from that exact point when the human's decision (approve/reject/edit/feedback) is submitted. Benefits over a fully custom queue:
State persistence and resumability come from the framework, not hand-rolled queue/polling logic.
The approval queue (what the frontend lists as "pending") becomes a query over checkpointed, interrupted graph runs, rather than a second, independently-maintained table that must stay in sync with graph state.
Regeneration or edit-and-resume flows are just resuming the interrupted graph with new input, keeping the state machine (Section 20) and the graph's actual execution state as a single source of truth instead of two.
Approval must not survive an edit
If a human edits a post's content, the post's `approval_status` must be reset to `PENDING_APPROVAL` (or the edit must be treated as a new draft requiring re-approval) before it can be scheduled. Otherwise the backend's approval check (Section 5.9 / 23) would be validating an approval that was granted for different content than what is about to be published.
---
5.9 Approval Enforcement
Human approval must be enforced at the backend level.
Publishing should require:
    approval_status == APPROVED
    AND content_hash(post) == content_hash(approved_version)

The second condition ensures approval is tied to the exact approved content, not merely to the post ID — so a post edited after approval cannot slip through on a stale approval flag.
Example:
    Publishing Request
            |
            v
    Approval Check
            |
            +---- NOT APPROVED ----> Publishing Blocked
            |
            +---- CONTENT CHANGED SINCE APPROVAL ----> Publishing Blocked
            |
            +---- APPROVED & UNCHANGED --------> Continue

The frontend approval button must not be the only security mechanism.
The backend must independently verify approval before scheduling or publishing.
---
5.10 Explainability
SocialPilot AI will provide explainability for important AI decisions.
The system should not expose private chain-of-thought or hidden reasoning.
Instead, the user will receive understandable decision information such as:
Campaign objective
Target audience
Brand rules considered
Content strategy
Review scores
Detected issues
Evidence or sources where applicable
Reason for regeneration
Recommendation
Final decision
Example
    AI CONTENT EXPLANATION

    Campaign Objective:
    Product Awareness

    Target Audience:
    Cybersecurity Professionals

    Content Strategy:
    Problem → Insight → Product → CTA

    Brand Tone:
    Professional + Educational

    Brand Compliance:
    93%

    Platform Fit:
    91%

    Risk:
    LOW

    Detected Issues:
    None

    Decision:
    Suitable for human approval.

This makes the AI workflow auditable and understandable.
---
5.11 Brand Memory and RAG
The system can allow users to upload brand-related information such as:
Brand guidelines
Product documentation
Marketing documents
Product descriptions
Previous campaigns
Company information
Product specifications
These documents can be embedded and stored using a vector database capability such as pgvector.
The AI can retrieve relevant information before generating content.
    Brand Documents
           |
           v
    Document Processing
           |
           v
    Embeddings
           |
           v
    PostgreSQL + pgvector
           |
           v
    Relevant Context
           |
           v
    LLM
           |
           v
    Generated Content

RAG can help improve:
Brand consistency
Factuality
Product accuracy
Context awareness
Hallucination resistance
Treat uploaded documents as untrusted input
Uploaded brand/product documents are user-supplied content that gets injected into LLM prompts via retrieval. They should be treated the same way as any other untrusted input, not as trusted system configuration:
Before embedding, run ingested text through a sanitization pass that strips or neutralizes instruction-like content (e.g. "ignore previous instructions," role-play directives, embedded system-prompt-style text).
Retrieved chunks should be inserted into prompts with clear structural separation from the actual system/developer instructions (e.g. explicitly delimited and labeled as "reference material," not as instructions), so a poisoned document has a harder time being interpreted as a command.
The Content Reviewer (Section 5.6) should still apply brand/safety checks to output even when it was RAG-grounded — grounding reduces hallucination risk but does not make output automatically trustworthy.
---
5.12 Scheduling
Approved posts can be scheduled for future publication.
Example
    Post:
    "AI is changing cybersecurity..."

    Platform:
    X

    Date:
    05 September 2026

    Time:
    07:30 PM

    Status:
    SCHEDULED

The scheduler will periodically identify posts whose scheduled time has arrived.
---
5.13 Publishing
Approved and scheduled content will be published through platform APIs.
    Scheduled Post
          |
          v
    Approval Check (status + content hash, see 5.9)
          |
          v
    Authentication Check
          |
          v
    Platform Adapter
          |
          v
    Social Media API
          |
          +---- SUCCESS ----> Published
          |
          +---- FAILURE ----> Retry / Failed

Publishing results will be stored in the database.
---
5.14 OAuth Integration
OAuth 2.0 will be used to connect social media accounts.
General flow:
    User
     |
     v
    Connect Account
     |
     v
    Social Platform OAuth
     |
     v
    User Authorization
     |
     v
    Authorization Code
     |
     v
    Backend
     |
     v
    Access / Refresh Token
     |
     v
    Encrypted Storage

The application will not request or store social media passwords.
Access tokens should never be exposed to the frontend.
Token storage must be encrypted at rest, explicitly
"Secure storage" means, concretely: access and refresh tokens are encrypted at rest (e.g. via envelope encryption backed by a KMS key, or symmetric encryption such as Fernet with the key held in a secrets manager, not in application config/env files checked into source control). Storing tokens as plaintext columns — even in a database that itself requires authentication — is not sufficient, since it means a database-level compromise (backup leak, SQL injection, misconfigured replica) directly exposes live platform credentials.
---
5.15 Social Platform Integration
The initial version should focus on a limited number of platforms.
Recommended V1 Platform
    X (or another low-friction platform such as Bluesky/Mastodon — see Section 33)

Future versions may support:
    LinkedIn
    Instagram
    Facebook
    Threads
    YouTube
    TikTok

Actual functionality will depend on the APIs, permissions, rate limits, and developer access provided by each platform.
The project should therefore avoid assuming that every platform provides identical publishing or analytics capabilities.
---
5.16 Platform Adapter Architecture
The backend will use a platform adapter architecture.
    SocialPlatform
          |
          +----> XAdapter
          |
          +----> LinkedInAdapter
          |
          +----> InstagramAdapter
          |
          +----> FacebookAdapter

The AI workflow should not directly depend on individual social media APIs.
Instead:
    AI Workflow
         |
         v
    Platform Interface
         |
         v
    Platform Adapter
         |
         v
    External API

This makes it easier to add additional platforms without changing the AI workflow. Because the AI workflow only ever talks to the Platform Interface, swapping the V1 platform later (e.g. adding LinkedIn once app-review access is granted) costs an adapter, not a redesign.
---
5.17 Analytics
Where supported by platform APIs, the system can collect metrics such as:
Impressions
Likes
Comments
Shares
Engagement
Clicks
Reach
The exact metrics will depend on the capabilities and permissions of each platform.
Historical metrics will be stored for analysis.
---
5.18 AI Performance Analysis
The system can analyze historical content performance.
Example
    Previous 30 Posts

    Educational Posts:
    Average Engagement = 8.2%

    Promotional Posts:
    Average Engagement = 3.6%

    Question-Based Posts:
    Average Engagement = 9.1%

The AI could generate:
    Recommendation:

    Increase educational and
    question-based content.

    Reduce purely promotional posts.

This creates a feedback loop between historical performance and future campaign planning.
---
5.19 Audit Logging
Important user and AI actions should be recorded.
Example
    12:31:04
    AI generated Post #421

    12:31:07
    AI review completed

    12:31:07
    Score: 91/100

    12:35:20
    Human rejected post

    Reason:
    Too promotional

    12:37:11
    AI regenerated post

    12:40:32
    Human approved post

    12:41:00
    Post scheduled

    18:00:03
    Publishing started

    18:00:05
    Publishing successful

Audit logs provide:
Traceability
Debugging information
Accountability
Security visibility
Workflow history
---
6. Complete System Workflow
The complete end-to-end workflow is:
    USER
      |
      v
    Create / Login
      |
      v
    Create Brand
      |
      v
    Create Campaign
      |
      v
    Campaign Objective
      |
      v
    AI CAMPAIGN PLANNER
      |
      v
    Campaign Strategy
      |
      v
    AI CONTENT GENERATOR
      |
      v
    Platform-Specific Posts
      |
      v
    AI CONTENT REVIEWER
      |
      v
    Brand / Safety Validation
      |
      v
    Quality Threshold
       /        \
    FAIL        PASS
      |            |
      v            v
    Regenerate   Human Approval
                   /       \
                Reject     Approve
                  |           |
                  v           v
              Regenerate    Schedule
                                |
                                v
                         Approval Check
                                |
                                v
                         Authentication
                                |
                                v
                         Platform Adapter
                                |
                                v
                         Social Media API
                            /       \
                       SUCCESS      FAILURE
                          |            |
                          v            v
                      Published      Retry
                          |
                          v
                      Analytics
                          |
                          v
                 Performance Analysis
                          |
                          v
                  Recommendations
                          |
                          v
                   Future Campaigns

---
7. Agent Workflow
The initial LangGraph workflow will contain several logical nodes.
    START
      |
      v
    Campaign Planner
      |
      v
    Content Generator
      |
      v
    Content Reviewer
      |
      v
    Brand/Safety Validator
      |
      v
    Human Approval   (interrupt() — graph pauses & checkpoints here, see 5.8)
      |
      v
    Scheduler
      |
      v
    Publisher
      |
      v
    Analytics
      |
      v
    END

Conditional transitions will be used where necessary.
Reviewer Decision
    Reviewer
       |
       +---- Poor Quality, attempts < max ----> Content Generator
       |
       +---- Poor Quality, attempts >= max ----> Human Approval (with issues attached)
       |
       +---- Good Quality ----> Human Approval

Human Decision
    Human Approval
       |
       +---- Rejected ----> Content Generator
       |
       +---- Edited ----> PENDING_APPROVAL (re-approval required, see 5.8)
       |
       +---- Approved ----> Scheduler

---
8. LangGraph State
The workflow can maintain a shared state containing information such as:
    campaign_id
    brand_id
    campaign_objective
    target_audience
    platform
    campaign_plan
    generated_content
    content_version
    content_hash
    review_score
    review_issues
    regeneration_attempts
    brand_validation
    human_feedback
    approval_status
    approved_content_hash
    scheduled_time
    publishing_status
    platform_post_id
    analytics

The state allows different nodes to communicate without tightly coupling their implementation. Because the Human Approval node is a LangGraph `interrupt()` point (Section 5.8), this state is checkpointed automatically at that pause and restored on resume, rather than needing a separately maintained "approval queue" table.
---
9. LLM Architecture
The application should not be tightly coupled to a single LLM provider.
An LLM abstraction layer will be implemented.
    LangGraph
        |
        v
    LLM Interface
        |
        +-------------+-------------+
        |             |             |
        v             v             v
      Mock          Ollama       Cloud LLM
     Testing       Development     Demo

---
9.1 Development Mode
Use a locally hosted model through Ollama.
Advantages:
No API cost
No API token limits
Faster experimentation
Offline inference after model download
Suitable for development
---
9.2 Testing Mode
Use a deterministic Mock LLM.
Advantages:
No API calls
No token cost
Deterministic results
Faster tests
Easy failure simulation
Suitable for CI/CD
Example:
    class MockLLM:

        def generate(self, prompt):
            return {
                "content": "Test social media post",
                "score": 92
            }

---
9.3 Demo / Production Mode
Use a hosted LLM such as OpenAI or another suitable provider when higher-quality generation is required.
The agent workflow should remain unchanged.
---
10. Why We Should Not Depend Entirely on OpenAI
A multi-agent or multi-node workflow can make multiple LLM calls for a single campaign.
For example:
    User Request
          |
          v
    Planner          → LLM Call
          |
          v
    Generator        → LLM Call
          |
          v
    Reviewer         → LLM Call
          |
          v
    Brand Checker    → LLM Call
          |
          v
    Regeneration     → LLM Call
          |
          v
    Final Reviewer   → LLM Call

During development, repeated execution can consume API credits quickly.
Therefore:
    Testing
       ↓
    Mock LLM

    Development
       ↓
    Ollama

    Final Demo
       ↓
    Hosted LLM

This prevents development from being dependent on a limited free API quota.
---
11. Recommended AI Model Strategy
The project should use a provider-independent architecture.
Instead of:
    LangGraph → OpenAI

the architecture should be:
    LangGraph
        |
        v
    LLM Service
        |
        +---- Mock Model
        |
        +---- Ollama Model
        |
        +---- OpenAI
        |
        +---- Other Hosted Model

This allows the project to switch models without rewriting the agents.
Potential local models can include suitable instruction-following models available through Ollama.
The exact model should be selected based on:
Available RAM/VRAM
Response quality
Structured-output capability
Latency
Context length
Hardware available during development
---
12. Testing Architecture
Testing should not require real LLM APIs or real social media accounts.
12.1 Unit Testing
Test individual functions such as:
Campaign validation
Approval validation
Approval invalidation on edit (post-approval content change resets status)
Scheduling logic
Score thresholds
Regeneration attempt cap enforcement
Retry logic
Authentication
Authorization
State transitions
Example:
    approval_status = "APPROVED"

    should_publish() → TRUE

    # then content is edited
    approval_status = "PENDING_APPROVAL"  # reset automatically

    should_publish() → FALSE

---
12.2 Agent Testing
Use deterministic mock responses.
    Mock Planner
          |
          v
    Mock Generator
          |
          v
    Mock Reviewer

This allows the workflow to be tested repeatedly without API costs. Test cases should include a scenario that exercises the regeneration cap (repeated low-quality mock output) to confirm the workflow escalates to human review instead of looping forever.
---
12.3 Platform Testing
Use mock social media APIs.
    Application
          |
          v
    Mock X API
          |
          v
    Simulated Response

Test cases should include:
Successful publishing
API failure
Timeout
Rate limit
Invalid token
Expired token
Duplicate request
Retry
---
12.4 Integration Testing
Test interactions between:
    FastAPI
       |
       v
    LangGraph
       |
       v
    PostgreSQL

Include a test that resumes an interrupted LangGraph run (Section 5.8) from a checkpoint after simulated human input, to confirm state restores correctly.
---
12.5 End-to-End Testing
Using Playwright:
    Login
      ↓
    Create Brand
      ↓
    Create Campaign
      ↓
    Generate Content
      ↓
    Review
      ↓
    Approve
      ↓
    Schedule
      ↓
    Verify Status

---
13. Background Processing
Long-running and scheduled operations should not block normal API requests.
Recommended components:
    Redis
    Celery
    Celery Beat

Redis
Responsibilities:
Message broker
Queue management
Temporary task state
Celery
Responsibilities:
Background tasks
Publishing jobs
Analytics jobs
Retry operations
Celery Beat
Responsibilities:
Periodic jobs
Scheduled publishing
Periodic analytics collection
---
14. Database Architecture
The initial database can contain:
    users
    brands
    campaigns
    posts
    post_versions
    reviews
    approvals
    social_accounts
    scheduled_posts
    publishing_logs
    analytics
    audit_logs
    documents

Relationship
    User
     |
     +---- Brand
            |
            +---- Campaign
                    |
                    +---- Posts
                           |
                           +---- Versions
                           |
                           +---- Review
                           |
                           +---- Approval
                           |
                           +---- Schedule
                           |
                           +---- Publishing Log
                           |
                           +---- Analytics
     |
     +---- Social Accounts

---
15. Technology Stack
15.1 Frontend
    Next.js
    React
    TypeScript
    Tailwind CSS

Responsibilities
Dashboard
Campaign creation
Content editor
Approval interface
Calendar
Analytics
Account management
---
15.2 Backend
    Python
    FastAPI

Responsibilities
REST APIs
Authentication
Authorization
Business logic
Database interaction
Agent execution
Scheduling integration
Social media integration
---
15.3 AI / Agent Layer
    LangGraph
    LangChain
    Ollama
    Cloud LLM Provider

Responsibilities
Campaign planning
Content generation
Content review
Regeneration
Decision routing
Human-in-the-loop workflow (via LangGraph `interrupt()` / checkpointing, see 5.8)
---
15.4 Database
    PostgreSQL
    pgvector
    SQLAlchemy
    Alembic

Responsibilities
User data
Campaigns
Content
Reviews
Approvals
Scheduling
Publishing history
Analytics
Audit logs
Vector embeddings
Database migrations
---
15.5 Background Processing
    Redis
    Celery
    Celery Beat

Responsibilities
Background jobs
Scheduling
Publishing
Analytics collection
Retry handling
---
15.6 External Integration
    OAuth 2.0
    Social Media APIs

Responsibilities
Social account connection
Authentication
Publishing
Analytics retrieval
---
15.7 Testing
    Pytest
    Playwright
    Mock LLM
    Mock APIs

---
15.8 Deployment
    Docker
    Docker Compose
    Git
    GitHub

Docker will provide consistent development and deployment environments.
---
16. Technology Stack — Where Each Technology Is Used
Technology	Layer	Role
Next.js	Frontend	Web application
React	Frontend	UI components
TypeScript	Frontend	Type-safe development
Tailwind CSS	Frontend	Styling
Python	Backend/AI	Core application language
FastAPI	Backend	REST API
LangGraph	AI	Agent workflow orchestration + native HITL interrupts/checkpointing
LangChain	AI	LLM tooling and integrations
Ollama	AI	Local LLM development
OpenAI / Other LLM	AI	High-quality generation/demo
PostgreSQL	Database	Persistent application data
pgvector	Database	Vector search/RAG
SQLAlchemy	Backend	ORM
Alembic	Backend	Database migrations
Redis	Infrastructure	Queue/broker
Celery	Infrastructure	Background jobs
Celery Beat	Infrastructure	Scheduled jobs
OAuth 2.0	Integration	Social account authentication (tokens encrypted at rest)
Social APIs	Integration	Publishing/analytics
Pytest	Testing	Backend/unit/integration testing
Playwright	Testing	Frontend/E2E testing
Docker	DevOps	Containerization
Git	DevOps	Version control
GitHub	DevOps	Repository/CI/CD
---
17. Recommended Project Architecture
    socialpilot-ai/
    │
    ├── frontend/
    │   ├── app/
    │   ├── components/
    │   ├── hooks/
    │   ├── services/
    │   ├── types/
    │   └── lib/
    │
    ├── backend/
    │   ├── app/
    │   │   ├── api/
    │   │   ├── core/
    │   │   ├── models/
    │   │   ├── schemas/
    │   │   ├── services/
    │   │   ├── repositories/
    │   │   ├── agents/
    │   │   ├── integrations/
    │   │   ├── tasks/
    │   │   └── main.py
    │   │
    │   ├── migrations/
    │   └── tests/
    │
    ├── ai/
    │   ├── prompts/
    │   ├── evaluators/
    │   ├── providers/
    │   └── workflows/
    │
    ├── docs/
    │
    ├── docker/
    │
    ├── docker-compose.yml
    ├── .env.example
    ├── README.md
    └── .gitignore

---
18. Agent Directory Structure
A possible AI architecture:
    backend/app/agents/

    ├── planner/
    │   ├── agent.py
    │   ├── prompts.py
    │   └── schemas.py
    │
    ├── generator/
    │   ├── agent.py
    │   ├── prompts.py
    │   └── schemas.py
    │
    ├── reviewer/
    │   ├── agent.py
    │   ├── prompts.py
    │   ├── claim_detector.py    # absolute-claim keyword/regex pass, see 5.6
    │   └── schemas.py
    │
    ├── brand/
    │   ├── agent.py
    │   └── rules.py
    │
    ├── analytics/
    │   ├── agent.py
    │   └── prompts.py
    │
    └── workflow/
        ├── graph.py
        ├── state.py
        └── nodes.py

---
19. API Architecture
Example backend endpoints:
Authentication
    POST /api/auth/register
    POST /api/auth/login
    POST /api/auth/logout
    GET  /api/auth/me

Brands
    POST   /api/brands
    GET    /api/brands
    GET    /api/brands/{id}
    PUT    /api/brands/{id}
    DELETE /api/brands/{id}

Campaigns
    POST   /api/campaigns
    GET    /api/campaigns
    GET    /api/campaigns/{id}
    PUT    /api/campaigns/{id}
    DELETE /api/campaigns/{id}

AI
    POST /api/campaigns/{id}/plan
    POST /api/campaigns/{id}/generate
    POST /api/posts/{id}/review
    POST /api/posts/{id}/regenerate

Approval
    GET  /api/approvals
    POST /api/posts/{id}/approve
    POST /api/posts/{id}/reject
    POST /api/posts/{id}/feedback
    PUT  /api/posts/{id}          # edit — must reset approval_status server-side

Scheduling
    POST /api/posts/{id}/schedule
    GET  /api/scheduled-posts
    DELETE /api/scheduled-posts/{id}

Social Accounts
    GET  /api/social/{platform}/connect
    GET  /api/social/{platform}/callback
    DELETE /api/social/{id}

Publishing
    POST /api/posts/{id}/publish
    GET  /api/posts/{id}/publishing-status

Analytics
    GET /api/analytics
    GET /api/campaigns/{id}/analytics
    GET /api/posts/{id}/analytics

---
20. Content State Machine
The post lifecycle should be explicitly modeled.
                  ┌───────────────┐
                  │     DRAFT     │
                  └───────┬───────┘
                          |
                          v
                  ┌───────────────┐
                  │ AI_REVIEWED   │
                  └───────┬───────┘
                          |
                          v
               ┌─────────────────────┐
               │ PENDING_APPROVAL    │◄────────┐
               └─────────┬───────────┘         │
                         |                      │ edit after approval
                ┌────────┴────────┐             │ (forces re-approval,
                |                 |             │  see 5.8 / 5.9)
                v                 v             │
          ┌──────────┐      ┌──────────┐        │
          │ REJECTED │      │ APPROVED │────────┘
          └────┬─────┘      └────┬─────┘
               |                 |
               v                 v
         ┌────────────┐    ┌───────────┐
         │ REGENERATE │    │ SCHEDULED │
         └──────┬─────┘    └─────┬─────┘
                |                |
                └───────┐        v
                        |   ┌───────────┐
                        └──>│ PUBLISHING│
                            └─────┬─────┘
                                  |
                           ┌──────┴──────┐
                           |             |
                           v             v
                     ┌───────────┐ ┌────────┐
                     │ PUBLISHED │ │ FAILED │
                     └─────┬─────┘ └────┬───┘
                           |             |
                           v             v
                      ANALYTICS       RETRY

---
21. Data Model
A simplified database relationship:
    USER
     |
     +-------------------+
     |                   |
     v                   v
    BRAND           SOCIAL_ACCOUNT
     |
     v
    CAMPAIGN
     |
     v
    POST
     |
     +----------+-----------+------------+
     |          |           |            |
     v          v           v            v
    VERSION   REVIEW     APPROVAL    SCHEDULE
                                          |
                                          v
                                    PUBLISHING_LOG
                                          |
                                          v
                                       ANALYTICS

---
22. Important Security Rules
Because the application can publish content to real social media accounts, security must be treated as a core requirement.
The application should implement:
Secure token storage — encrypted at rest (KMS-backed or Fernet with key in a secrets manager, not plaintext columns or env files; see 5.14)
HTTPS in production
JWT expiration
OAuth state validation
Input validation
Authorization checks
API authentication
Rate limiting
Secret management
Audit logging
Backend approval enforcement, including invalidation of approval when content is edited (see 5.8 / 5.9)
Sanitization of uploaded documents used for RAG, to reduce prompt-injection risk (see 5.11)
Social media access tokens must never be exposed to the frontend.
---
23. Publishing Security Rule
The following rule is fundamental:
    IF
        approval_status != APPROVED
        OR content_hash(post) != approved_content_hash
    THEN
        publishing MUST fail

The backend should verify:
    1. User owns the post
    2. Post exists
    3. Post is approved
    4. Approved content matches current content (no post-approval edits)
    5. Post is scheduled correctly
    6. Social account is connected
    7. Token is valid
    8. Platform is supported

Only after these checks should the system call the external social media API.
---
24. LLM Provider Abstraction
A provider interface should be created.
Conceptually:
    class LLMProvider:

        def generate(self, prompt):
            raise NotImplementedError

Implementations:
    MockLLMProvider
    OllamaProvider
    OpenAIProvider
    OtherCloudProvider

The agents should depend on:
    LLMProvider

rather than:
    OpenAI

This makes the entire project easier to test and maintain.
---
25. Mock LLM Strategy
The Mock LLM should support deterministic scenarios.
Scenario 1 — Successful Generation
    Input:
    Create an X post about AI security.

    Output:
    Valid structured post.

Scenario 2 — Low Quality
    Input:
    Create a post.

    Output:
    Low review score.

Expected behavior:
    Generator
       ↓
    Reviewer
       ↓
    FAIL
       ↓
    Regenerate

Scenario 2b — Regeneration cap reached
    Input:
    Create a post that repeatedly fails review.

    Output:
    Low review score, 3 times in a row.

Expected behavior:
    Generator ↔ Reviewer  (loop, attempt count increments)
       ↓
    attempts >= max
       ↓
    Escalate to Human Approval with issues attached
    (not an infinite loop)

Scenario 3 — Human Rejection
    AI Generated
         ↓
    Human Rejects
         ↓
    Feedback
         ↓
    Regenerate

Scenario 3b — Edit after approval
    AI Generated
         ↓
    Human Approves
         ↓
    Human Edits Content
         ↓
    approval_status resets to PENDING_APPROVAL
         ↓
    Publishing blocked until re-approved

Scenario 4 — Publishing Failure
    Approved
       ↓
    Scheduled
       ↓
    Mock API Failure
       ↓
    Retry
       ↓
    Success

This allows the entire agentic workflow to be tested without using paid APIs.
---
26. Evaluation Strategy
AI quality should not be evaluated only by asking:
    "Does the generated text look good?"

Instead, measurable evaluation criteria should be introduced.
Content Evaluation
Possible metrics:
    Brand Alignment
    Platform Suitability
    Readability
    Factuality
    Safety
    Originality
    CTA Quality

Factuality specifically should not be a single self-reported LLM score — it should combine absolute-claim detection and source-grounding checks with the LLM's judgment, as described in Section 5.6, since an LLM grading its own factuality is a weak signal on its own.
Each can have a score.
Example:
    Brand Alignment       92
    Platform Suitability  90
    Readability            95
    Factuality             94   (grounded: 3/3 claims matched to source docs; 0 absolute-claim flags)
    Safety                100
    Originality             86
    CTA Quality             88
    --------------------------------
    Overall                92

---
27. Explainability Architecture
Explainability should be treated as a separate layer.
    AI Agent
       |
       v
    Decision
       |
       +---- Decision Factors
       |
       +---- Evaluation Scores
       |
       +---- Brand Rules
       |
       +---- Retrieved Evidence
       |
       +---- Detected Issues
       |
       +---- Recommended Action
       |
       v
    Human-Readable Explanation

Example:
    Decision:
    REGENERATE

    Why:
    The post uses a claim that is not supported
    by the available product documentation.

    Rules affected:
    - No unsupported product claims
    - Maintain educational tone

    Recommended action:
    Rewrite the claim using only verified
    product capabilities.

---
28. RAG Architecture
The future RAG pipeline can be:
    Documents (untrusted input, see 5.11)
        |
        v
    Sanitization Pass (strip/neutralize instruction-like content)
        |
        v
    Document Loader
        |
        v
    Text Chunking
        |
        v
    Embeddings
        |
        v
    pgvector
        |
        v
    Similarity Search
        |
        v
    Relevant Context (inserted into prompt as clearly-delimited
    reference material, not as instructions)
        |
        v
    Campaign / Content Agent
        |
        v
    Generated Content

RAG should be used primarily for grounding the model in user-provided information, rather than treating vector search as a replacement for the LLM. Because retrieved content originates from user uploads, it should be handled as untrusted input throughout this pipeline, not as trusted configuration.
---
29. Prompt Management
Prompts should not be hardcoded throughout the application.
Recommended structure:
    ai/prompts/

    ├── planner/
    │   └── system.txt
    │
    ├── generator/
    │   └── system.txt
    │
    ├── reviewer/
    │   └── system.txt
    │
    ├── regeneration/
    │   └── system.txt
    │
    └── analytics/
        └── system.txt

Prompt versions should be tracked.
Example:
    planner_v1
    planner_v2
    generator_v1
    reviewer_v1

This allows experiments and regression testing.
---
30. Major Difficulties We May Face
30.1 Social Media API Restrictions
One of the biggest challenges will be external platform APIs.
Different platforms have different:
Permissions
Rate limits
API versions
Publishing requirements
Authentication flows
App-review processes
Supported content types
Analytics capabilities
Some functionality may not be available to every developer account. This is a significant part of why V1 targets X (or Bluesky/Mastodon) rather than LinkedIn — LinkedIn's posting and analytics APIs generally require Marketing Developer Platform partnership approval, which is a slow and uncertain process for a new/independent developer account, and would put the entire end-to-end proof-of-concept at risk of being blocked on access rather than implementation (see Section 33).
Mitigation
Use:
    Platform Interface
           |
           +---- X Adapter
           +---- LinkedIn Adapter
           +---- Instagram Adapter

This isolates platform-specific implementation.
---
30.2 OAuth Complexity
OAuth can introduce problems involving:
Redirect URLs
Token expiration
Refresh tokens
Permission scopes
Development vs production environments
App configuration
Platform-specific authentication requirements
Mitigation
Implement OAuth as a dedicated backend service and store tokens encrypted at rest (Section 5.14).
---
30.3 LLM Cost and Availability
Hosted LLM APIs may introduce:
Free-credit limitations
Rate limits
API downtime
Pricing changes
Model availability changes
Mitigation
    Testing     → Mock LLM
    Development → Ollama
    Demo        → Hosted LLM

---
30.4 Local Model Quality
Local models may not always match larger hosted models in:
Writing quality
Reasoning
Structured output
Factuality
Instruction following
Therefore, the architecture should support replacing the local model with another model without changing the agent workflow.
---
30.5 Hallucination
AI may generate claims that are not supported by the brand's actual information.
Example
    Actual Product Capability:
    Detects suspicious activity

    AI Output:
    Provides 100% guaranteed threat prevention

This is dangerous and unacceptable.
Mitigation
    Brand Guidelines
           +
    Product Documentation
           ↓
    RAG (with input sanitization, see 5.11)
           ↓
    LLM
           ↓
    Reviewer (absolute-claim detection + source grounding, see 5.6)
           ↓
    Human Approval

---
30.6 Human Approval Reliability
The system must guarantee that unapproved posts — and posts edited after approval — cannot be published.
The backend should enforce:
    if approval_status != "APPROVED" or content_hash(post) != approved_content_hash:
        block_publish()

The system should prevent:
Direct publishing of drafts
Scheduling unapproved content
Publishing rejected posts
Publishing content edited after approval without re-approval
Unauthorized publishing requests
---
30.7 Scheduling Reliability
Scheduling can introduce:
Server downtime
Incorrect time zones
Duplicate jobs
API failures
Expired tokens
Network errors
Recommended states:
    DRAFT
    AI_REVIEWED
    PENDING_APPROVAL
    APPROVED
    SCHEDULED
    PUBLISHING
    PUBLISHED
    FAILED
    RETRYING
    REJECTED

---
30.8 Duplicate Publishing
A failed API request does not always mean that the platform did not receive the post.
Blindly retrying can potentially create duplicate posts.
The publishing layer should eventually support:
Idempotency
Publishing verification
Platform-specific status checking
Safe retry logic
---
30.9 Rate Limits
External APIs may limit:
Requests per minute
Requests per day
Publishing frequency
Analytics requests
The system should implement:
Rate-limit detection
Retry policies
Exponential backoff
Request logging
Queue-based execution
---
30.10 Platform-Specific Content
The same content does not necessarily work equally well across platforms.
Example:
    LinkedIn
    → Professional / educational / long-form

    Instagram
    → Visual / caption-oriented

    X
    → Concise / short-form

The generator should therefore create platform-specific variants.
---
30.11 Explainability Challenges
The system needs to explain AI decisions without exposing private model reasoning.
The explanation layer should focus on:
Decision factors
Scores
Brand rules checked
Evidence retrieved
Detected issues
Recommendations
Actions taken
This provides useful explainability without exposing hidden chain-of-thought.
---
30.12 Maintaining AI Consistency
LLM outputs can vary between runs.
The same prompt may produce different content.
This creates difficulties for testing and evaluation.
Mitigation
Use:
Structured output
Output schemas
Strong prompts
Validation
Mock LLMs
Evaluation datasets
Quality thresholds
Versioned prompts
Bounded regeneration attempts (see 5.7), so inconsistency cannot manifest as an infinite loop
---
30.13 Prompt Injection via Uploaded Brand Documents
Because brand/product documents are user-uploaded and later injected into generation prompts via RAG, a malicious or compromised document could attempt to override system instructions, exfiltrate other brands' data, or steer output toward unsafe content.
Mitigation
Sanitize uploaded documents before embedding (Section 5.11 / 28).
Structurally separate retrieved context from system instructions in the prompt.
Keep the Content Reviewer's brand/safety checks active on RAG-grounded output, not bypassed because the content is "sourced."
Scope retrieval strictly to the requesting user's own brand/documents.
---
31. Project Limitations
The initial system will have several limitations.
Platform Limitations
Publishing and analytics depend on what each platform's API allows.
AI Limitations
AI cannot guarantee perfect factual accuracy, even with grounding and claim detection.
Analytics Limitations
Different platforms expose different performance metrics.
Local Model Limitations
Local models may produce lower-quality content compared with larger hosted models.
Scheduling Limitations
Publishing depends on:
API availability
Valid authentication
Platform permissions
Network connectivity
Human Dependency
The system intentionally requires human approval before publishing.
This is not considered a weakness.
It is a deliberate safety and control mechanism.
---
32. V1 Scope
The first version should intentionally remain limited.
Authentication
User registration
Login
JWT authentication
Brand
Brand profile
Tone
Audience
Brand rules
Campaign
Campaign creation
Campaign objective
Target audience
Main topic
AI
Campaign planning
Content generation
Content review
Regeneration
Human Approval
Approval queue
Edit
Approve
Reject
Regenerate
Feedback
Backend approval enforcement
Scheduling
Date/time selection
Scheduled posts
Background scheduler
Platform
One real social platform
OAuth
Publishing
Tracking
Post status
Publishing logs
Audit logs
---
33. Recommended V1 Platform
The initial implementation should focus on:
    X (or another low-friction platform such as Bluesky or Mastodon)

Why X instead of LinkedIn: LinkedIn's publishing and analytics endpoints generally sit behind their Marketing Developer Platform partnership program, which requires an approval process that is slow and not guaranteed for a new or independent developer — a real risk to proving the end-to-end workflow on schedule. X's developer API access (and Bluesky's/Mastodon's fully open APIs) is comparatively low-friction to obtain for a V1 build. Because publishing goes through the Platform Adapter architecture (Section 5.16), switching the "real" V1 platform, or adding LinkedIn once proper access is secured, is an adapter-level change — it does not touch the AI workflow, review logic, or approval enforcement.
Instead of immediately implementing:
    LinkedIn
    Instagram
    Facebook
    X
    Threads
    TikTok
    YouTube

The goal of V1 is to prove the complete end-to-end workflow:
    Generate
       ↓
    Review
       ↓
    Human Approval
       ↓
    Schedule
       ↓
    Publish
       ↓
    Track

Once this is stable, additional platforms can be added.
---
34. V1 Development Roadmap
Phase 1 — Foundation
    ✓ Repository setup
    ✓ Backend setup
    ✓ Frontend setup
    ✓ PostgreSQL
    ✓ Authentication
    ✓ Basic dashboard

---
Phase 2 — Database and Core APIs
    ✓ User model
    ✓ Brand model
    ✓ Campaign model
    ✓ Post model
    ✓ Review model
    ✓ Approval model
    ✓ Scheduling model
    ✓ API routes
    ✓ Database migrations

---
Phase 3 — AI Workflow
    ✓ LangGraph setup
    ✓ LLM abstraction
    ✓ Mock LLM
    ✓ Ollama integration
    ✓ Campaign planner
    ✓ Content generator
    ✓ AI reviewer (with absolute-claim detection + source grounding)
    ✓ Regeneration workflow (with attempt cap)

---
Phase 4 — Human Approval
    ✓ Approval via LangGraph interrupt()/checkpointing
    ✓ Approve
    ✓ Reject
    ✓ Edit (resets approval_status)
    ✓ Regenerate
    ✓ Feedback
    ✓ Backend approval enforcement (status + content-hash check)

---
Phase 5 — Scheduling
    ✓ Calendar
    ✓ Scheduled posts
    ✓ Celery
    ✓ Redis
    ✓ Celery Beat
    ✓ Retry mechanism

---
Phase 6 — Social Integration
    ✓ OAuth (tokens encrypted at rest)
    ✓ Platform adapter
    ✓ X integration
    ✓ Publishing
    ✓ Publishing logs

---
Phase 7 — Explainability and Brand Memory
    ✓ AI decision summaries
    ✓ Review explanations
    ✓ Brand rules
    ✓ Document upload (with sanitization pass)
    ✓ pgvector
    ✓ RAG
    ✓ Audit logs

---
Phase 8 — Analytics
    ✓ Performance collection
    ✓ Analytics dashboard
    ✓ Historical performance
    ✓ AI performance analysis
    ✓ Recommendations

---
Phase 9 — Testing
    ✓ Unit tests
    ✓ Agent tests
    ✓ API tests
    ✓ Database integration tests
    ✓ Mock platform tests
    ✓ Scheduling tests
    ✓ Publishing failure tests
    ✓ Playwright E2E tests

---
Phase 10 — Deployment
    ✓ Docker
    ✓ Docker Compose
    ✓ Environment configuration
    ✓ Production database
    ✓ CI/CD
    ✓ Logging
    ✓ Monitoring

---
35. Future Scope
35.1 Multi-Platform Expansion
Expand support to:
    LinkedIn
    Instagram
    X
    Facebook
    Threads
    YouTube
    TikTok

Each platform will have its own adapter.
---
35.2 Advanced Campaign Planning
Users could provide a simple instruction such as:
    "Promote our new product for the next month."

The AI could automatically generate:
    30-Day Campaign
          ↓
    Weekly Themes
          ↓
    Daily Content
          ↓
    Platform Variations
          ↓
    Approval Queue

---
35.3 Advanced RAG-Based Brand Memory
Users could upload:
Brand manuals
Product documentation
Marketing documents
Previous campaigns
Company information
Product specifications
The AI can retrieve relevant context before generating content.
This can improve:
Factuality
Brand consistency
Context awareness
Product accuracy
---
35.4 Historical Content Learning
The system can analyze previous posts.
Example:
    High Performing:
    Educational Posts
    Question-Based Posts

    Low Performing:
    Purely Promotional Posts

The AI can use these observations when planning future campaigns.
---
35.5 Advanced Analytics Agent
A dedicated Analytics Agent could answer questions such as:
    What type of content performs best?

    Which topics should we post more often?

    Which posting times seem most effective?

    Which platform performs best?

    Why did this campaign perform poorly?

---
35.6 AI Content A/B Testing
The system could generate multiple content variants.
    Variant A
    Educational

    Variant B
    Question-Based

    Variant C
    Product-Focused

After publishing, performance could be compared.
The system can then identify which content patterns perform better.
---
35.7 Automatic Trend Detection
The system could monitor relevant trends and identify topics related to the brand.
    Trend Monitoring
           ↓
    Relevant Topic Detection
           ↓
    Brand Relevance Check
           ↓
    Content Suggestion
           ↓
    Human Approval

The system should not automatically publish sensitive or controversial trend-related content without human approval.
---
35.8 Advanced Approval Workflows
Future versions could support multiple approval levels.
    AI Generated
          ↓
    Marketing Manager
          ↓
    Legal Review
          ↓
    Brand Manager
          ↓
    Approved
          ↓
    Publish

Different campaigns could have different approval requirements.
---
35.9 Role-Based Access Control
Future versions could support roles such as:
    Admin
    Marketing Manager
    Content Editor
    Reviewer
    Viewer

Each role would have different permissions.
---
35.10 Multi-Agent Architecture
The initial version should not unnecessarily create a large number of agents.
However, future versions could introduce specialized agents.
    Supervisor Agent
           |
    +------+-------+---------------+
    |              |               |
    v              v               v
    Strategy      Content        Analytics
    Agent         Agent          Agent
      |              |               |
      v              v               v
    Campaign      Social Posts    Performance
    Plan

The Supervisor Agent can coordinate specialized agents.
Multi-agent architecture should only be introduced where it provides a genuine architectural benefit.
---
35.11 Model Routing
Future versions could use different models for different tasks.
Example:
    Simple Classification
            ↓
    Small Local Model

    Content Generation
            ↓
    Medium Model

    Complex Campaign Planning
            ↓
    Large Hosted Model

This can reduce cost while maintaining quality.
---
35.12 Cost-Aware AI Routing
The system could track:
    Token Usage
    Model Cost
    Request Count
    Latency
    Quality Score

The system could then choose the cheapest model that meets the required quality level.
---
35.13 Autonomous Campaign Optimization
A future version could create a controlled feedback loop:
    Campaign
       ↓
    Generate
       ↓
    Human Approval
       ↓
    Publish
       ↓
    Measure
       ↓
    Analyze
       ↓
    Learn Patterns
       ↓
    Improve Next Campaign

The system becomes increasingly useful without removing human control.
---
35.14 AI Content Calendar Optimization
Future versions can use historical performance to recommend:
Best posting days
Best posting times
Optimal content frequency
Content type distribution
Platform allocation
Example:
    Historical Data
          ↓
    Performance Analysis
          ↓
    Optimal Posting Pattern
          ↓
    Future Campaign Planner

---
35.15 Advanced Brand Safety
Future versions could introduce specialized validation for:
Legal claims
Financial claims
Medical claims
Copyright-sensitive content
Competitor references
Sensitive topics
Regulatory requirements
The system could route risky posts to additional human review.
---
36. Research and Technical Contributions
The project can potentially demonstrate several important technical concepts.
Agentic AI
The system uses multiple AI-driven workflow stages rather than a single chatbot interaction.
Human-in-the-Loop AI
AI performs automation while humans retain final control over consequential actions, implemented via LangGraph's native interrupt/checkpoint mechanism rather than a parallel custom queue.
Explainable AI
AI decisions are converted into human-readable decision summaries.
RAG
Brand and product information can be retrieved before content generation, treated as untrusted input and sanitized against prompt injection.
LLM Provider Abstraction
The system can operate with:
    Mock
    Ollama
    OpenAI
    Other Providers

without changing the core workflow.
Reliable AI Workflows
The system explicitly models:
State
Validation
Approval (invalidated on post-approval edits)
Retry
Failure
Auditability
Bounded regeneration
AI Evaluation
Generated content can be evaluated using measurable quality dimensions — including a concrete factuality mechanism (claim detection + source grounding) — rather than subjective inspection or self-reported scores alone.
---
37. Key Design Principles
The project should follow these principles:
1. Human Control
AI should assist humans, not silently make consequential publishing decisions. Approval must reflect the actual content being published — an edit after approval requires re-approval.
2. Provider Independence
The application should not depend on one LLM provider.
3. Backend Enforcement
Security-critical rules must be enforced server-side, including approval status, content-hash matching, and encrypted credential storage.
4. Structured AI Output
Agents should produce structured outputs wherever possible.
5. Modular Architecture
AI, APIs, database, and social platforms should remain loosely coupled — including treating the V1 social platform choice as swappable via the adapter layer.
6. Testability
The application should be testable without paid external AI APIs.
7. Explainability
Important AI decisions should be understandable to users.
8. Auditability
Important actions should be recorded.
9. Reliability
External API failures should be expected and handled.
10. Incremental Development
V1 should prove the complete workflow before expanding into a large multi-agent system.
11. Untrusted Input Handling
Any content originating from outside the system's own instructions — including user-uploaded brand documents used for RAG — should be treated as untrusted and defended against prompt injection.
---
38. Final Architecture
The intended architecture can be summarized as:
                         ┌───────────────────┐
                         │      USER         │
                         └─────────┬─────────┘
                                   |
                                   v
                         ┌───────────────────┐
                         │   Next.js / React │
                         │    Frontend       │
                         └─────────┬─────────┘
                                   |
                              REST / HTTPS
                                   |
                                   v
                         ┌───────────────────┐
                         │      FastAPI      │
                         │      Backend      │
                         └─────────┬─────────┘
                                   |
              ┌────────────────────┼────────────────────┐
              |                    |                    |
              v                    v                    v
       ┌─────────────┐     ┌──────────────┐     ┌──────────────┐
       │ PostgreSQL  │     │   LangGraph  │     │    Redis     │
       │ + pgvector  │     │ AI Workflow  │     │ Queue/Broker │
       │ (tokens     │     │ (native      │     └──────┬───────┘
       │  encrypted) │     │  interrupt() │            |
       └─────────────┘     │  for HITL)   │            v
                            └───────┬──────┘       ┌─────────────┐
                                   |               │   Celery    │
                                   v               │  Workers    │
                            ┌─────────────┐        └──────┬──────┘
                            │ LLM Service │               |
                            └──────┬──────┘               v
                    ┌──────────────┼──────────────┐    Scheduler
                    |              |              |
                    v              v              v
                  Mock          Ollama        Cloud LLM
                                                 |
                                                 v
                                        Platform Adapters
                                                 |
                           ┌─────────────────────┼────────────────────┐
                           |                     |                    |
                           v                     v                    v
                           X                 Bluesky/            (future:
                       (V1 platform)         Mastodon            LinkedIn,
                                              (alt V1)            Instagram, ...)
                           |                     |                    |
                           └─────────────────────┼────────────────────┘
                                                 |
                                                 v
                                            Analytics
                                                 |
                                                 v
                                        AI Recommendations

---
39. Final Project Workflow
The final conceptual workflow is:
    USER
      |
      v
    BRAND CONFIGURATION
      |
      v
    CAMPAIGN OBJECTIVE
      |
      v
    AI CAMPAIGN PLANNING
      |
      v
    CONTENT GENERATION
      |
      v
    BRAND + SAFETY REVIEW (claim detection + source grounding + LLM score)
      |
      +----------------------+
      |                      |
      v                      v
    FAIL                   PASS
      |                      |
      v                      v
    REGENERATE          HUMAN APPROVAL
    (bounded by            /        \
     attempt cap)       REJECT      APPROVE
      |                  |            |
      |                  |            v
      +------------------+       SCHEDULED
                                       |
                                       v
                             BACKEND VALIDATION
                             (status + content hash)
                                    |
                                    v
                             PLATFORM ADAPTER
                                    |
                                    v
                             SOCIAL MEDIA API
                                    |
                             +------+------+
                             |             |
                             v             v
                         SUCCESS        FAILURE
                             |             |
                             v             v
                        PUBLISHED        RETRY
                             |
                             v
                         ANALYTICS
                             |
                             v
                    AI PERFORMANCE ANALYSIS
                             |
                             v
                     FUTURE RECOMMENDATIONS
                             |
                             v
                      NEXT CAMPAIGN

---
40. Definition of Done for V1
V1 can be considered complete when the following workflow works reliably:
    1. User registers
            ↓
    2. User creates a brand
            ↓
    3. User creates a campaign
            ↓
    4. AI generates a campaign plan
            ↓
    5. AI generates a social media post
            ↓
    6. AI reviews the post (claim detection + grounding + LLM score)
            ↓
    7. User sees the explanation
            ↓
    8. User can edit / reject / regenerate
            ↓
    9. User approves the post
            ↓
    10. User schedules the post
            ↓
    11. Background worker picks up the job
            ↓
    12. Backend verifies approval (status + content hash)
            ↓
    13. Platform adapter publishes the post
            ↓
    14. Publishing status is stored
            ↓
    15. Audit log is created
            ↓
    16. Analytics are collected where supported

The most important success criterion is:
    AI generates
          ↓
    AI reviews
          ↓
    HUMAN DECIDES
          ↓
    SYSTEM VALIDATES
          ↓
    SYSTEM PUBLISHES
          ↓
    SYSTEM LEARNS

This creates a practical Agentic AI Social Media Management System rather than simply another AI text-generation application.