# Diagram sources

Version 1.0 (Stage 2). These Mermaid diagrams are the sources of the figures that the SRS refers to. GitHub renders them. If a diagram changes, change it here in the same commit as the design it shows.

## 1. System context

```mermaid
flowchart LR
    user["End user (YouTube account owner)"] -->|chat| client["AI client (MCP host)"]
    client <-->|"MCP over stdio (JSON-RPC)"| server["ytmcp MCP server: tools, resources, skills"]
    server -->|"HTTPS REST"| yt["YouTube Data API v3"]
    server <-->|"OAuth 2.0 with PKCE"| oauth["Google OAuth 2.0 server"]
    server <-->|"read and write"| store[("SQLite: cache, quota ledger, proposals, audit log")]
    server -->|"refresh token"| keyring["OS keyring"]
    server -.->|"loopback approval page"| browser["User's browser"]
    ci["CI (GitHub Actions, fixtures only)"] -.->|tests| server
```

## 2. Layers

```mermaid
flowchart TD
    tools["tools and resources: thin MCP handlers"] --> services["services: quota guard, similarity, recommendation, engagement, playlist, confirmation gate"]
    tools -->|"sanitiser only"| domain["domain: pure functions"]
    services --> domain
    services --> providers["providers: YouTubeProvider interface"]
    services --> infra["infra: db, cache, ledger, tokens, oauth, rate limiter, audit log, clock, approval server"]
    providers --> infra
    providers --> domain
    domain --> models["models and errors"]
    services --> models
    infra --> models
    providers --> models
    tools --> models
    config["config"] -.-> infra
    config -.-> services
    config -.-> providers
```

## 3. Class diagram (providers and playlist services)

```mermaid
classDiagram
    class YouTubeProvider {
        <<abstract>>
        +get_videos(ids)
        +search(q, type, max_results, language, published_after)
        +get_channels(ids)
        +resolve_channel(ref)
        +recent_uploads(channel, n)
        +list_liked(cap)
        +list_subscriptions(cap)
        +list_playlists(cap)
        +list_playlist_items(playlist_id, cap)
        +video_categories(region)
        +my_channel()
        +create_playlist(title, description, visibility)
        +add_playlist_item(playlist_id, video_id)
    }
    class ApiTransport {
        <<interface>>
        +call(method, params)
        +post(method, params, body)
    }
    class ApiBackedProvider
    class FixtureYouTubeProvider {
        +created_playlists
        +added_items
        +add_attempts
    }
    class LiveYouTubeProvider
    class RecordingProvider
    class FixtureTransport
    class LiveTransport
    class RecordingTransport
    class QuotaGuard {
        +check(plan, request_id)
        +record(endpoint, units, request_id)
        +status()
    }
    class ConfirmationGate {
        +request_approval(proposal, ctx)
        +verify_and_consume(proposal_id)
    }
    class PlaylistService {
        +propose(request)
        +confirm(proposal_id)
    }
    class SimilarityService {
        +similar_videos(video, limit, filters)
        +similar_channels(channel, limit, exclude_subscribed)
    }
    class Proposal {
        +proposal_id
        +items_hash
        +state
        +expires_at
    }
    ApiBackedProvider --|> YouTubeProvider
    FixtureYouTubeProvider --|> ApiBackedProvider
    LiveYouTubeProvider --|> ApiBackedProvider
    RecordingProvider --|> ApiBackedProvider
    ApiBackedProvider --> ApiTransport : uses
    FixtureTransport ..|> ApiTransport
    LiveTransport ..|> ApiTransport
    RecordingTransport ..|> ApiTransport
    PlaylistService --> YouTubeProvider
    PlaylistService --> QuotaGuard
    PlaylistService --> ConfirmationGate
    PlaylistService ..> Proposal
    SimilarityService --> YouTubeProvider
    SimilarityService --> QuotaGuard
```

## 4. Sequence: similar videos (FR-1)

```mermaid
sequenceDiagram
    actor User
    participant Client as AI client
    participant Tool as find_similar_videos
    participant Svc as SimilarityService
    participant QG as QuotaGuard
    participant Cache
    participant Prov as YouTubeProvider
    participant Dom as domain ranker
    User->>Client: Find videos like this one
    Client->>Tool: find_similar_videos(video, limit, filters)
    Tool->>Svc: similar_videos(video, limit, filters)
    Svc->>Svc: normalise and validate the video ID
    Svc->>QG: check(plan)
    QG-->>Svc: estimate within budget
    Svc->>Cache: look up seed and candidates
    alt cache miss
        Svc->>Prov: get_videos(seed)
        Svc->>Prov: search(query from top terms)
        Svc->>Prov: get_videos(candidates in batches of 50)
        Prov-->>Svc: videos
        Svc->>QG: record(units spent)
        Svc->>Cache: store videos
    end
    Svc->>Dom: rank_videos(seed, candidates, weights, limit)
    Dom-->>Svc: scored videos
    Svc-->>Tool: results
    Tool->>Tool: sanitise and delimit YouTube text
    Tool-->>Client: envelope with results and quota report
    Client-->>User: ranked list
```

## 5. Sequence: recommendations (FR-3)

```mermaid
sequenceDiagram
    actor User
    participant Client as AI client
    participant Tool as recommend_videos
    participant Svc as RecommendationService
    participant QG as QuotaGuard
    participant Prov as YouTubeProvider
    participant Dom as domain taste profile and ranker
    User->>Client: Recommend videos for me
    Client->>Tool: recommend_videos(limit, sources, filters)
    Tool->>Svc: recommend(limit, sources, filters)
    Svc->>QG: check(plan)
    QG-->>Svc: estimate within budget
    Svc->>Prov: list_liked, list_subscriptions, list_playlists and items
    Prov-->>Svc: user signals
    Svc->>Dom: build_taste_profile(signals)
    Svc->>Prov: search(top profile terms) and recent_uploads of subscriptions
    Prov-->>Svc: candidate videos
    Svc->>Svc: exclude liked, in-playlist and excluded channels
    Svc->>Dom: rank by cosine to the profile and apply mmr_select
    Dom-->>Svc: top results with because lines
    Svc-->>Tool: recommendations
    Tool-->>Client: envelope with sanitised results
    Client-->>User: recommendations
```

## 6. Sequence: playlist creation with approval (FR-5)

```mermaid
sequenceDiagram
    actor User
    participant Client as AI client
    participant Tool as propose and confirm tools
    participant PS as PlaylistService
    participant QG as QuotaGuard
    participant Prov as YouTubeProvider
    participant Gate as ConfirmationGate
    participant DB as SQLite
    User->>Client: Two-hour playlist on X, no video over 20 minutes
    Client->>Tool: propose_playlist(topic, total_duration, max_video_duration, language)
    Tool->>PS: propose(request)
    PS->>PS: validate and sanitise input
    PS->>QG: check(plan)
    QG-->>PS: estimate within budget
    PS->>Prov: search twice, get_videos, my_channel
    Prov-->>PS: videos and channel
    PS->>PS: filter, rank, solve the constraint, order
    PS->>DB: store proposal in state PROPOSED with 15 minute expiry
    PS-->>Tool: proposal without any secret
    Tool-->>Client: numbered list and confirmation prompt
    Client-->>User: show the playlist and ask to confirm
    User->>Client: Yes, create it
    Client->>Tool: confirm_playlist(proposal_id)
    Tool->>PS: confirm(proposal_id)
    PS->>Gate: request_approval(proposal)
    alt client supports elicitation
        Gate->>Client: elicitation request with summary
        Client->>User: approve or decline
        User-->>Client: approve
        Client-->>Gate: accept
    else loopback approval page
        Gate->>User: open the approval page in the browser
        Gate-->>PS: pending
        PS-->>Tool: APPROVAL_PENDING without any address
        User->>Gate: press Approve on the page
        Client->>Tool: confirm_playlist(proposal_id) again
        Tool->>PS: confirm(proposal_id)
    end
    PS->>Gate: verify_and_consume(proposal_id)
    PS->>QG: check(plan of 1 channel check, 1 playlist insert, n item inserts)
    PS->>Prov: create_playlist and add_playlist_item for each item
    PS->>DB: state CREATED and audit entry
    PS-->>Tool: playlist URL and quota report
    Tool-->>Client: result
    Client-->>User: link and short analysis
```

## 7. Proposal state machine

```mermaid
stateDiagram-v2
    [*] --> DRAFT
    DRAFT --> PROPOSED : constraints solved
    PROPOSED --> CONFIRMED : approval verified
    PROPOSED --> REJECTED : user declines
    PROPOSED --> EXPIRED : 15 minute expiry elapsed
    CONFIRMED --> CREATED : all items added
    CONFIRMED --> PARTIALLY_CREATED : some items failed
    CONFIRMED --> FAILED : failure before a playlist exists
    PARTIALLY_CREATED --> CONFIRMED : resume with a new approval
    CREATED --> [*]
    REJECTED --> [*]
    EXPIRED --> [*]
    FAILED --> [*]
```

## 8. Use cases

```mermaid
flowchart LR
    ai(["AI client"])
    user(["End user"])
    yt(["YouTube Data API"])
    oauth(["Google OAuth"])
    subgraph server["YouTube Video Intelligence MCP server"]
        uc1["UC-1 Find similar videos (FR-1)"]
        uc2["UC-2 View quota status"]
        uc3["UC-3 Find similar channels (FR-2)"]
        uc4["UC-4 Get recommendations (FR-3)"]
        uc5["UC-5 Analyse engagement (FR-4)"]
        uc6["UC-6 Build playlist from request (FR-5)"]
        uc7["UC-7 Confirm or reject proposal"]
        uc8["UC-8 Run video-to-playlist skill"]
        uc9["UC-9 Authorise or re-authorise OAuth"]
    end
    ai --- uc1
    ai --- uc2
    user --- uc3
    user --- uc4
    user --- uc5
    user --- uc6
    user --- uc7
    user --- uc8
    user --- uc9
    uc1 -.-> yt
    uc3 -.-> yt
    uc4 -.-> yt
    uc5 -.-> yt
    uc6 -.-> yt
    uc9 -.-> oauth
```

## 9. Entity-relationship diagram (local SQLite store)

```mermaid
erDiagram
    playlist_proposal ||--o{ proposal_item : "has items"
    request_log ||--o{ quota_ledger : "request_id (logical)"
    playlist_proposal ||--o{ audit_log : "events (logical)"
    schema_version {
        integer version
    }
    oauth_token {
        integer token_id PK
        text account_hash
        text scopes
        text keyring_ref
        text issued_at
        text expires_at
    }
    quota_ledger {
        integer entry_id PK
        text request_id
        text endpoint
        integer units
        text pt_day
        text created_at
    }
    request_log {
        text request_id PK
        text tool_name
        integer est_units
        integer actual_units
        text outcome
        text created_at
    }
    video_cache {
        text video_id PK
        text json
        text etag
        text fetched_at
        integer ttl_s
    }
    channel_cache {
        text channel_id PK
        text json
        text etag
        text fetched_at
        integer ttl_s
    }
    kv_cache {
        text key PK
        text json
        text fetched_at
        integer ttl_s
    }
    playlist_proposal {
        text proposal_id PK
        text request_json
        text items_hash
        integer total_s
        integer feasible
        text state
        text approval_state
        text approval_hash
        text playlist_id
        text created_at
        text expires_at
    }
    proposal_item {
        text proposal_id PK
        integer pos PK
        text video_id
        real score
        integer duration_s
        integer added_ok
    }
    audit_log {
        integer audit_id PK
        text event
        text proposal_id
        text actor
        text created_at
    }
```

## 10. Data flow (level 1)

```mermaid
flowchart LR
    client["AI client"] -->|request| p1["P1 Validate and sanitise input"]
    p1 -->|valid request| p2["P2 Quota estimate and gate"]
    p2 -->|approved plan| p3["P3 Fetch and cache metadata"]
    p3 -->|videos and channels| p4["P4 Score, rank and solve constraints"]
    p4 -->|proposal| p5["P5 Confirmation and write"]
    p5 -->|result| client
    p3 <-->|cache| d1[("D1 SQLite store")]
    p4 <-->|cache| d1
    p5 <-->|proposals and audit| d1
    p3 <-->|read| yt["YouTube Data API"]
    p5 -->|insert| yt
```
