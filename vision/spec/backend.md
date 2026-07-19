# Backend Architecture v2

> Derives from: [System Demo](../system-demo.html) + 7 Domain Specs.
> Answers: "How does the backend make the System Demo true at runtime?"

---

## v1 → v2: What Changed

| v1 Problem | v2 Fix |
|------------|--------|
| System Demo read as static schema | System Demo read as LIVE state. Design for concurrency. |
| No frontend-backend contract | Session Transport Protocol: WebSocket + REST |
| Companion pipeline hand-wavy | Full concurrency model: observe/sense/decide pipeline + streaming |
| No real session data flow | Trace one complete session end-to-end |
| No streaming design | SSE for AI output, WS for bidirectional events |
| REST-only assumption | Multi-mode transport: REST + WS + SSE |
| SQLite compromise on graph | PostgreSQL recursive CTE for Knowledge |
| No API contract | Operation contract: WS message types + REST endpoints |

---

## Transport Architecture

AppleGo needs **three** transport modes, not one:

| Mode | Protocol | Purpose |
|------|----------|---------|
| Query | REST (HTTP) | Load static data: workspace list, session history, artifacts |
| Stream | SSE (HTTP) | AI response streaming: token-by-token output from Companion |
| Live | WebSocket | Bidirectional: user actions → server, system events → client |

### Why Not REST-Only?

A live learning session is not request-response:

```
User: reads PDF silently for 12 minutes
       → NO REST call. Frontend tracks scroll position locally.

User: highlights a paragraph
       → WS → { type: "event", behavior: "intake_mark", position: "P18" }

Companion: notices deep reading pattern
       → WS ← { type: "companion observe", signal: "deep_focus" }

User: types a question
       → WS → { type: "message", content: "why does this converge?" }

Companion: streams reply
       → SSE: "Because" ... "ε" ... "controls" ... "the" ... "bound" ...

Companion: suggests opening Canvas
       → WS ← { type: "orchestrate", action: "open_canvas", reason: "visual" }

Companion: finished
       → WS ← { type: "message_complete", id: "msg_42" }
```

REST handles "load my workspaces." WebSocket handles the live learning experience. SSE handles AI streaming. Each does what it's best at.

---

## WebSocket Protocol

### Client → Server (user actions)

```typescript
type ClientMessage =
  | { type: "session.join", session_id: string }
  | { type: "session.leave" }
  | { type: "message.send", session_id: string, content: string }
  | { type: "event.report",
      session_id: string,
      behavior: "intake_read" | "intake_watch" | "externalize_draw" |
                "externalize_note" | "test_attempt" | "test_complete" |
                "artifact_open" | "artifact_close" | "artifact_interact",
      payload: {
        artifact_id?: string,
        position?: string,
        duration_seconds?: number,
        result?: { correct: boolean, answer: string }
      }
    }
  | { type: "session.pause", session_id: string }
  | { type: "session.end", session_id: string }
```

### Server → Client (system events)

```typescript
type ServerMessage =
  // AI streaming (SSE, separate channel)
  | { type: "ai.token", session_id: string, token: string, message_id: string }
  | { type: "ai.complete", session_id: string, message_id: string }
  
  // Companion observations (WS)
  | { type: "companion.observe", session_id: string,
      learner_state: "reading" | "thinking" | "drawing" | "testing" | "idle",
      engagement: "flow" | "normal" | "hesitating" | "stuck" }
  
  // Companion orchestration (WS)
  | { type: "companion.orchestrate", session_id: string,
      action: "open_artifact" | "suggest_practice" | "suggest_close",
      artifact?: { type: string, id: string, position?: string },
      reason: string }
  
  // System state updates (WS)
  | { type: "state.sync", session_id: string,
      active_artifacts: Artifact[], mission: MissionState }
  
  // Session lifecycle (WS)
  | { type: "session.paused", session_id: string }
  | { type: "session.resumed", session_id: string }
```

---

## REST Endpoints

REST handles loading, not living. All REST endpoints serve specific queries from System Demo.

```
GET  /api/workspaces                              → listWorkspaces()
GET  /api/workspaces/:id                          → getWorkspace()
POST /api/workspaces                              → createWorkspace()

GET  /api/workspaces/:id/sessions                 → listSessions()
GET  /api/sessions/:id                            → getSession() + events + title
POST /api/workspaces/:id/sessions                 → createSession()

GET  /api/sessions/:id/memory                     → getSessionMemory()
GET  /api/workspaces/:id/memory                   → getWorkspaceMemory()
GET  /api/memory/recent                           → getRecentMemory(user_id)

GET  /api/workspaces/:id/knowledge/concepts       → getConcepts()
GET  /api/workspaces/:id/knowledge/clusters       → getConceptClusters()
GET  /api/workspaces/:id/knowledge/concept/:name  → getConcept() + connections + depth

GET  /api/workspaces/:id/timeline?scale=week      → getTimeline()
GET  /api/workspaces/:id/evolution                → getEvolutionSnapshots()

GET  /api/learner/profile                         → getLearnerModel()
GET  /api/learner/state/:session_id               → getCurrentLearnerState()
```

**Each endpoint = one System Demo query.** No more, no fewer. Added when a query is needed. Deleted when no longer needed.

---

## Complete Session Lifecycle

This is what actually happens. Backend must support every step concurrently.

### Phase 1: Load (REST)

```
Frontend → GET /api/workspaces
Backend  → [ {id:"w1", name:"微积分", total_sessions:34, ...}, ... ]

Frontend → GET /api/workspaces/w1
Backend  → { ...workspace, active_session_id: "s_142" }

Frontend → GET /api/sessions/s_142
Backend  → {
             ...session, state:"paused",
             events: [ ...last 50 events ],
             active_artifacts: [
               {type:"pdf", id:"pdf_3", position:"page_18"},
               {type:"canvas", id:"canvas_7", nodes: [...]}
             ]
           }

Frontend → GET /api/workspaces/w1/memory
Backend  → { last_position: "ε-δ definition", last_state: "confused_formal", ... }

Frontend → GET /api/learner/state/s_142
Backend  → { current_understanding: {...}, energy: "rested", ... }
```

### Phase 2: Resume (WebSocket)

```
Frontend → WS { type: "session.join", session_id: "s_142" }

Backend:
  1. Load session events into in-memory buffer
  2. Initialize Companion observation loop
  3. Initialize Learner observation buffer

Backend → WS { type: "state.sync", active_artifacts: [...], mission: {...} }

Backend → SSES { type: "companion.observe", learner_state: "idle", ... }
Backend → SSEC ... (no AI message yet — learner is reading)
```

### Phase 3: Live Learning (WebSocket + SSE concurrent)

```
--- User reads PDF silently ---
Frontend → WS { type: "event.report", behavior: "intake_read",
                payload: { artifact_id: "pdf_3", position: "page_18" } }

Backend → writes LearningEvent to append-only log
        → emits EventBus("intake_read", ...)

Companion (consumes event):
  → Observe: user is reading, page_18, deep focus
  → Does NOT interrupt. Learner state = "flow". Companion stays silent.

Memory (consumes event):
  → Evaluate: reading position changed. Memorable? YES — part of learning trajectory.
  → Store: SessionMemory.write({ type: "intake_position", position: "page_18" })

Time (consumes event):
  → Update session duration counter

--- 4 minutes later ---
Frontend → WS { type: "event.report", behavior: "intake_read",
                payload: { artifact_id: "pdf_3", position: "page_19", duration_seconds: 240 } }
Backend → same flow, Companion stays silent

--- User types a question ---
Frontend → WS { type: "message.send", content: "为什么 ε 必须任意小？要是 ε 比 0.1 大呢？" }

Backend → writes LearningEvent("understanding_question", ...)
        → emits EventBus

Companion (consumes event):
  → Observe: user asking. Behavior = "understanding". Engagement = "normal".
  → Sense: question about ε-δ rigor. Formal approach might not land.
           Previous strategy: tried visual analogy yesterday. It worked partially.
  → Decide: visual + formal hybrid. Start with visual. Then bridge to formal.
  → Load context from Memory: last_position, what was understood, what's still fuzzy
  → Build system prompt with context
  → Stream response:

SSE → { type: "ai.token", token: "好", message_id: "msg_89" }
SSE → { type: "ai.token", token: "问题", message_id: "msg_89" }
SSE → { type: "ai.token", token: "。", message_id: "msg_89" }
...
SSE → { type: "ai.token", token: "画", message_id: "msg_89" }
SSE → { type: "ai.token", token: "出来。", message_id: "msg_89" }
SSE → { type: "ai.complete", message_id: "msg_89" }

Companion → decides to orchestrate:
WS  ← { type: "companion.orchestrate",
        action: "open_artifact",
        artifact: { type: "canvas", id: "canvas_7" },
        reason: "ε-δ visualization" }

Frontend → opens Canvas panel

--- User draws on Canvas ---
Frontend → WS { type: "event.report", behavior: "externalize_draw",
                payload: { artifact_id: "canvas_7", nodes_added: 2 } }
Backend → LearningEvent → EventBus

Companion (consumes event):
  → Observe: drawing 2 new nodes. Seems to be building intuition.
  → Stays silent. Protects externalization.

Knowledge (consumes event):
  → Canvas interaction detected for concept "ε-δ".
  → Evidence strengthens: user is deepening understanding.
  → Depth: "approaching" → "approaching" (confidence increases)

--- User sends follow-up ---
Frontend → WS { type: "message.send", content: "所以 ε 就是那个'误差容忍度'？" }

Companion (consumes event):
  → Observe: user is synthesizing. Using own words.
  → Sense: this is a breakthrough moment. Mark it.
  → Decide: affirm the synthesis. Connect to prior concepts.

SSE → ...streaming reply...
SSE → { type: "ai.complete", message_id: "msg_90" }

Companion → marks breakthrough:
Memory (async): { type: "moment", subtype: "breakthrough",
                  concept: "ε-δ", description: "self-synthesized error tolerance analogy" }

Time (async): { type: "milestone", subtype: "breakthrough",
                concept: "ε-δ", day_number: 34 }

--- User signals end ---
Frontend → WS { type: "session.end", session_id: "s_142" }

Backend:
  1. Mark session as paused (not ended — learning continues off-screen)
  2. Run end-of-session pipeline:

     Companion:
       → Generate session title from conversation summary
       → "理解 ε-δ 的直观含义"

     Memory:
       → Promote session events to Workspace memory
       → Apply write filter (discard trivial, keep meaningful)
       → Update workspace memory snapshot

     Knowledge:
       → Update concept depths based on session evidence
       → "ε-δ": depth evidence now includes "self-explained analogy" + "visualized"
       → Run cluster detection (new concepts might group)

     Learner:
       → Process observation buffer → update patterns
       → "Pauses before formal questions" confidence: 0.7 → 0.8
       → Update learner model if threshold crossed

     Time:
       → Update milestone counters
       → Recompute evolution snapshot
       → "Day 34: 12 sessions, 5 concepts, breakthrough on ε-δ formal understanding"

  3. Respond:

WS ← { type: "session.paused", session_id: "s_142" }
WS ← { type: "state.sync", session_id: null, ... }  // frontend navigates away
```

---

## Companion: Full Concurrency Model

The Companion is the most complex service. It runs **three concurrent loops**:

### Loop 1: Observation (continuous, 2s tick)

```
Every 2 seconds:
  1. Read latest LearningEvents since last tick
  2. Update Observation:
     - learner_state: reading | thinking | drawing | testing | idle
     - engagement: flow | normal | hesitating | stuck | tired
     - current_artifact, position
  3. Emit WS ← { type: "companion.observe", ... }
  
  4. Evaluate interrupt rules:
     - IF learner_state == "reading" AND engagement == "flow"
       → SILENT. Do nothing.
     - IF engagement == "stuck" AND stuck_duration > 60s
       → Flag for Decide loop
     - IF engagement == "tired" AND session_duration > 45min
       → Flag for Decide loop
```

### Loop 2: Response (triggered by user message)

```
On message.received:
  1. Pause observation (don't obsolete yourself while responding)
  2. Load context:
     - Memory: workspace_memory snapshot
     - Learner: style, pace, current understanding
     - Knowledge: concept depth for relevant concepts
     - Session: recent events (last 20)
  3. Sense:
     - What is the user really asking?
     - What approach has worked before?
     - What approach has failed?
  4. Build system prompt with full context
  5. Stream response → SSE
  6. On complete:
     - Decide: need orchestration? (open canvas, suggest practice)
     - If yes: WS ← { type: "companion.orchestrate", ... }
     - Mark any breakthrough moments → Memory
  7. Resume observation loop
```

### Loop 3: Orchestration (background, triggered by observation)

```
Every 5 seconds, when observation flags:
  1. Read observation flag (stuck / tired / milestone)
  2. Decide action:
     - Stuck: suggest visual → open_canvas
     - Stuck (canvas already open): suggest practice → generate_flashcards
     - Tired: suggest close → suggest_close
     - Breakthrough detected: mark moment → Memory
  3. Emit orchestration event if action decided
```

### Concurrency Safety

```typescript
class CompanionSession {
  private observeLock = false;
  private respondLock = false;

  // Observation can only update Observation state.
  // It cannot send messages or orchestrate during active response.

  async onObservationTick() {
    if (this.respondLock) return; // skip tick during response
    const state = await this.observe();
    this.emit("companion.observe", state);
    this.checkOrchestrationTriggers(state); // sets flags for Loop 3
  }

  async onMessageReceived(message: ClientMessage) {
    this.respondLock = true;
    await this.respond(message);
    this.respondLock = false;
  }

  async onOrchestrationTick() {
    if (this.respondLock) return; // don't orchestrate while responding
    const action = this.decideOrchestration();
    if (action) this.emit("companion.orchestrate", action);
  }
}
```

**Three rules guarantee safety:**
1. Observation pauses during AI response (avoiding "AI talks over AI")
2. Orchestration pauses during AI response (don't interrupt your own reply)
3. Multiple observations can accumulate — only the latest state matters

---

## PostgreSQL Storage Per Domain

All domains use PostgreSQL. No SQLite. Different storage strategies per domain.

### Environment / Session / Time / Learner / Memory → Relational

```
-- Workspace
CREATE TABLE workspaces (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL,
  name TEXT NOT NULL,
  icon TEXT DEFAULT 'book',
  color TEXT DEFAULT '#4A90D9',
  created_at TIMESTAMPTZ DEFAULT now(),
  last_active_at TIMESTAMPTZ,
  total_sessions INT DEFAULT 0,
  total_minutes INT DEFAULT 0,
  active_session_id UUID REFERENCES sessions(id)
);

-- Session
CREATE TABLE sessions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id UUID NOT NULL REFERENCES workspaces(id),
  title TEXT,
  state TEXT NOT NULL DEFAULT 'active'
    CHECK (state IN ('active', 'paused', 'ended')),
  starting_mode TEXT NOT NULL
    CHECK (starting_mode IN ('continuity', 'mission', 'free')),
  started_at TIMESTAMPTZ DEFAULT now(),
  ended_at TIMESTAMPTZ
);

-- LearningEvent: append-only log
CREATE TABLE learning_events (
  id BIGSERIAL PRIMARY KEY,
  session_id UUID NOT NULL REFERENCES sessions(id),
  timestamp TIMESTAMPTZ DEFAULT now(),
  behavior TEXT NOT NULL,
  payload JSONB NOT NULL DEFAULT '{}'
);
CREATE INDEX idx_learning_events_session ON learning_events(session_id, timestamp);

-- SessionArtifact
CREATE TABLE session_artifacts (
  session_id UUID NOT NULL REFERENCES sessions(id),
  artifact_id UUID NOT NULL,
  artifact_type TEXT NOT NULL,
  state JSONB NOT NULL DEFAULT '{}',
  PRIMARY KEY (session_id, artifact_id)
);

-- MemoryEntry (three-tier)
CREATE TABLE memory_entries (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL,
  workspace_id UUID,
  session_id UUID,
  tier TEXT NOT NULL CHECK (tier IN ('session', 'workspace', 'global')),
  memory_type TEXT NOT NULL
    CHECK (memory_type IN ('event', 'understanding_shift', 'moment', 'pattern', 'pathway')),
  summary TEXT NOT NULL,
  payload JSONB NOT NULL DEFAULT '{}',
  detail_ref UUID,           -- links to learning_events.id
  created_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX idx_memory_user_tier ON memory_entries(user_id, tier, created_at DESC);
CREATE INDEX idx_memory_workspace ON memory_entries(workspace_id, created_at DESC);

-- Milestone
CREATE TABLE milestones (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id UUID NOT NULL,
  day_number INT NOT NULL,
  timestamp TIMESTAMPTZ DEFAULT now(),
  type TEXT NOT NULL CHECK (type IN ('breakthrough', 'stuck', 'first_encounter', 'project_complete')),
  concept TEXT,
  description TEXT
);
CREATE INDEX idx_milestones_workspace_day ON milestones(workspace_id, day_number);

-- EvolutionSnapshot
CREATE TABLE evolution_snapshots (
  workspace_id UUID NOT NULL,
  day_number INT NOT NULL,
  session_count INT DEFAULT 0,
  concept_count INT DEFAULT 0,
  connection_count INT DEFAULT 0,
  top_concepts JSONB DEFAULT '[]',
  learner_summary JSONB DEFAULT '{}',
  PRIMARY KEY (workspace_id, day_number)
);

-- Learner Pattern
CREATE TABLE learner_patterns (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL,
  workspace_id UUID,
  pattern_type TEXT NOT NULL,
  description TEXT NOT NULL,
  confidence FLOAT DEFAULT 0.0,
  evidence_count INT DEFAULT 1,
  first_observed TIMESTAMPTZ DEFAULT now(),
  last_observed TIMESTAMPTZ DEFAULT now()
);

-- Learner Model (one row per user)
CREATE TABLE learner_models (
  user_id UUID PRIMARY KEY,
  learning_style_summary JSONB DEFAULT '{}',
  pace_profile JSONB DEFAULT '{}',
  strength_areas JSONB DEFAULT '[]',
  struggle_areas JSONB DEFAULT '[]',
  updated_at TIMESTAMPTZ DEFAULT now()
);
```

### Knowledge → Graph (PostgreSQL recursive CTE)

```sql
-- Concept node
CREATE TABLE concepts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id UUID NOT NULL,
  name TEXT NOT NULL,
  depth TEXT NOT NULL DEFAULT 'surface'
    CHECK (depth IN ('surface', 'understanding', 'application', 'connection', 'creation')),
  depth_evidence JSONB DEFAULT '[]',
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now(),
  UNIQUE (workspace_id, name)
);

-- Connection edge
CREATE TABLE connections (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id UUID NOT NULL,
  source_id UUID NOT NULL REFERENCES concepts(id),
  target_id UUID NOT NULL REFERENCES concepts(id),
  relationship TEXT NOT NULL
    CHECK (relationship IN ('builds_on', 'alternative_to', 'formalizes', 'applies_to', 'related')),
  strength FLOAT DEFAULT 0.0,
  evidence_count INT DEFAULT 1,
  UNIQUE (workspace_id, source_id, target_id, relationship)
);

-- Cluster (auto-generated)
CREATE TABLE clusters (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id UUID NOT NULL,
  name TEXT NOT NULL,
  concept_ids UUID[] NOT NULL,
  is_auto_generated BOOLEAN DEFAULT true,
  emerged_at TIMESTAMPTZ DEFAULT now()
);
```

**Recursive CTE: all prerequisites of a concept**

```sql
WITH RECURSIVE prereqs AS (
  -- Base: direct prerequisites
  SELECT target_id AS concept_id, 1 AS depth, target_id AS path
  FROM connections
  WHERE source_id = $1 AND relationship = 'builds_on'

  UNION ALL

  -- Recursive: prerequisites of prerequisites
  SELECT c.target_id, p.depth + 1, p.path || c.target_id
  FROM connections c
  JOIN prereqs p ON c.source_id = p.concept_id
  WHERE c.relationship = 'builds_on'
    AND p.depth < 5
    AND NOT (c.target_id = ANY(p.path))  -- cycle prevention
)
SELECT DISTINCT ON (concept_id) concept_id, depth
FROM prereqs
ORDER BY concept_id, depth ASC;
```

**Reverse CTE: "what depends on this concept?"**

```sql
WITH RECURSIVE dependents AS (
  SELECT source_id AS concept_id, 1 AS depth
  FROM connections
  WHERE target_id = $1 AND relationship = 'builds_on'

  UNION ALL

  SELECT c.source_id, d.depth + 1
  FROM connections c
  JOIN dependents d ON c.target_id = d.concept_id
  WHERE c.relationship = 'builds_on' AND d.depth < 5
)
SELECT * FROM dependents;
```

**Cross-time connection: "when was this concept discussed before?"**

```sql
-- Window function: compare this session vs historical
SELECT
  le.session_id,
  MIN(le.timestamp) AS first_mention,
  COUNT(*) AS event_count
FROM learning_events le
WHERE le.behavior IN ('intake_read', 'understanding_question', 'understanding_answer')
  AND le.payload->>'concept' = 'ε-δ'
  AND le.timestamp < now() - INTERVAL '7 days'
GROUP BY le.session_id
ORDER BY first_mention DESC;
```

---

## Event Bus: PostgreSQL NOTIFY

Replace in-process event emitter with PostgreSQL NOTIFY/LISTEN. Why:

1. **Durability**: events survive process restart. In-process emitter loses all pending events on crash.
2. **Single source**: events are written to `learning_events` table. NOTIFY is a side-effect, not a separate system.
3. **No extra infrastructure**: no Redis, no RabbitMQ. PostgreSQL already runs.

```sql
-- After inserting a LearningEvent:
NOTIFY learning_event, '{"id": 12345, "session_id": "s_142", "behavior": "intake_read"}';
```

```typescript
// Companion service listens:
await pgClient.query('LISTEN learning_event');
pgClient.on('notification', async (msg) => {
  const event = JSON.parse(msg.payload);
  await companion.processEvent(event);
});
```

```sql
-- Trigger function to auto-notify:
CREATE OR REPLACE FUNCTION notify_learning_event()
RETURNS TRIGGER AS $$
BEGIN
  PERFORM pg_notify('learning_event',
    json_build_object(
      'id', NEW.id,
      'session_id', NEW.session_id,
      'behavior', NEW.behavior,
      'payload', NEW.payload
    )::text
  );
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER learning_event_notify
  AFTER INSERT ON learning_events
  FOR EACH ROW EXECUTE FUNCTION notify_learning_event();
```

---

## Service Topology (v2)

```
┌──────────────────────────────────────────────────────┐
│                    Nginx / Caddy                       │
│         /api/* → REST  │  /ws → WebSocket             │
│         /sse/* → SSE                                   │
└────────┬──────────────────┬───────────────────────────┘
         │                  │
    ┌────▼─────┐     ┌──────▼──────────┐
    │ REST API │     │  WS Gateway      │
    │ (Express)│     │  (+ SSE manager) │
    └────┬─────┘     └──────┬──────────┘
         │                  │
         └──────┬───────────┘
                │
    ┌───────────▼──────────────────────────┐
    │           Domain Services             │
    │                                       │
    │  WorkspaceService  SessionService     │
    │  TimeService       KnowledgeService   │
    │  MemoryService     LearnerService     │
    │                                       │
    │            CompanionEngine            │
    │    (observe loop + respond loop       │
    │     + orchestrate loop)               │
    └───────────┬──────────────────────────┘
                │
    ┌───────────▼──────────────────────────┐
    │         PostgreSQL                     │
    │  ┌────────────────────────────┐       │
    │  │ Tables + JSONB + CTE       │       │
    │  │ NOTIFY/LISTEN event bus    │       │
    │  └────────────────────────────┘       │
    └───────────────────────────────────────┘
```

---

## Concurrency: Per-Session Isolation

Each session is an independent unit of concurrency:

```typescript
class SessionRuntime {
  private sessionId: string;
  private companion: CompanionSession;  // has its own loops
  private eventBuffer: LearningEvent[] = [];
  private pgClient: PoolClient;         // dedicated connection for LISTEN
  
  async start() {
    await this.pgClient.query(`LISTEN learning_event`);
    this.pgClient.on('notification', (msg) => {
      const event = JSON.parse(msg.payload);
      if (event.session_id !== this.sessionId) return; // filter: only this session
      this.eventBuffer.push(event);
    });
    
    this.startObserverTick();
    this.startOrchestratorTick();
  }
  
  private startObserverTick() {
    setInterval(() => {
      this.companion.onObservationTick(this.eventBuffer.splice(0));
    }, 2000);
  }
  
  private startOrchestratorTick() {
    setInterval(() => {
      this.companion.onOrchestrationTick();
    }, 5000);
  }
  
  async onUserMessage(content: string) {
    await this.companion.onMessageReceived(content);
  }
  
  async onUserEvent(behavior: string, payload: any) {
    // Write to DB → trigger fires → NOTIFY → back to this session's LISTEN
    await db.query(
      `INSERT INTO learning_events (session_id, behavior, payload)
       VALUES ($1, $2, $3)`,
      [this.sessionId, behavior, JSON.stringify(payload)]
    );
  }
}
```

Each active session runs in-memory with its own Companion loops. Paused sessions are unloaded. Multiple sessions can be active simultaneously (one per workspace). PostgreSQL NOTIFY ensures that all services see the same event stream.

---

## Storage Summary (v2)

| Domain | PG Strategy | Key PG Feature |
|--------|------------|----------------|
| Environment | Relational tables | ACID transactions |
| Session (meta) | Relational tables | Foreign key constraints |
| Session (events) | Append-only table + NOTIFY | BRIN index on timestamp |
| Companion (AI state) | In-memory only | N/A (disposable per session) |
| Companion (history) | JSONB column in learning_events | JSONB query |
| Time | Relational + materialized views | Window functions |
| Learner | Relational | JSONB for flexible patterns |
| Memory | Relational + JSONB | GIN index on payload |
| Knowledge | Adjacency list + recursive CTE | WITH RECURSIVE |

---

## What v2 Rejects

- **REST-only transport.** AppleGo needs WebSocket + SSE + REST. Three modes.
- **In-process event emitter.** PostgreSQL NOTIFY is durable, survives restarts, no extra infra.
- **SQLite.** PostgreSQL recursive CTE, JSONB, window functions, NOTIFY — four features AppleGo depends on.
- **ORM-first.** Raw SQL for recursive CTE, window functions, JSONB queries. ORM only for simple CRUD.
- **Stateless backend.** Session runtime is stateful (Companion loops, event buffers, SSE connections).
- **Monolith API.** Session runtime runs per-session. API gateway is thin. Domain logic lives in services.
