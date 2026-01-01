# antigravity2claudecode (a2c) - Full Application Plan

## Overview

Transform antigravity2claudecode from a library into a full-featured AI proxy/router application with:

- CLI tools (`a2c serve`, `a2c code`, `a2c status`, etc.)
- Web UI dashboard (React + shadcn/ui)
- Router system for multi-provider support
- Enterprise-grade debugging and logging
- PostgreSQL for debug storage

## Architecture

```
a2c/
├── src/
│   └── a2c/
│       ├── __init__.py
│       ├── core/                    # Existing library code
│       │   ├── converter.py
│       │   ├── streaming.py
│       │   ├── token_estimator.py
│       │   └── helpers.py
│       │
│       ├── server/                  # FastAPI Backend
│       │   ├── __init__.py
│       │   ├── app.py              # App factory
│       │   ├── config.py           # Server configuration
│       │   ├── middleware/
│       │   │   ├── __init__.py
│       │   │   ├── logging.py      # Request/response logging
│       │   │   ├── metrics.py      # Prometheus metrics
│       │   │   ├── cors.py         # CORS handling
│       │   │   └── errors.py       # Error handling
│       │   ├── routes/
│       │   │   ├── __init__.py
│       │   │   ├── anthropic.py    # /v1/messages
│       │   │   ├── openai.py       # /v1/chat/completions
│       │   │   ├── health.py       # /health/*
│       │   │   ├── debug.py        # /debug/*
│       │   │   └── admin.py        # /admin/* (config, providers)
│       │   └── websocket/
│       │       ├── __init__.py
│       │       ├── status.py       # Live status updates
│       │       └── logs.py         # Live log streaming
│       │
│       ├── router/                  # Routing System
│       │   ├── __init__.py
│       │   ├── registry.py         # Provider registry
│       │   ├── rules.py            # Routing rules engine
│       │   ├── selector.py         # Provider selection
│       │   ├── failover.py         # Failover handling
│       │   └── agents.py           # Agent type definitions
│       │
│       ├── providers/               # Provider Implementations
│       │   ├── __init__.py
│       │   ├── base.py             # Base provider interface
│       │   ├── anthropic.py        # Native Anthropic API
│       │   ├── antigravity.py      # Antigravity (Google)
│       │   ├── openai.py           # OpenAI-compatible
│       │   └── gemini.py           # Direct Gemini API
│       │
│       ├── debug/                   # Debug Infrastructure
│       │   ├── __init__.py
│       │   ├── store.py            # PostgreSQL debug store
│       │   ├── models.py           # SQLAlchemy models
│       │   ├── inspector.py        # Request inspector
│       │   └── replay.py           # Request replay
│       │
│       └── cli/                     # CLI Tools
│           ├── __init__.py
│           ├── main.py             # Entry point (typer)
│           ├── serve.py            # a2c serve
│           ├── code.py             # a2c code
│           ├── status.py           # a2c status (TUI)
│           ├── config.py           # a2c config
│           ├── provider.py         # a2c provider
│           └── route.py            # a2c route
│
├── ui/                              # React Frontend
│   ├── package.json
│   ├── vite.config.ts
│   ├── tailwind.config.js
│   ├── src/
│   │   ├── main.tsx
│   │   ├── App.tsx
│   │   ├── components/
│   │   │   ├── ui/                 # shadcn/ui components
│   │   │   ├── layout/
│   │   │   │   ├── Sidebar.tsx
│   │   │   │   ├── Header.tsx
│   │   │   │   └── Layout.tsx
│   │   │   ├── dashboard/
│   │   │   │   ├── MetricsCard.tsx
│   │   │   │   ├── ThroughputChart.tsx
│   │   │   │   └── ProviderStatus.tsx
│   │   │   ├── routing/
│   │   │   │   ├── RulesTable.tsx
│   │   │   │   └── RuleEditor.tsx
│   │   │   ├── logs/
│   │   │   │   ├── LogViewer.tsx
│   │   │   │   └── LogFilters.tsx
│   │   │   └── debug/
│   │   │       ├── RequestInspector.tsx
│   │   │       └── StreamViewer.tsx
│   │   ├── pages/
│   │   │   ├── Dashboard.tsx
│   │   │   ├── Providers.tsx
│   │   │   ├── Routing.tsx
│   │   │   ├── Logs.tsx
│   │   │   ├── Debug.tsx
│   │   │   └── Settings.tsx
│   │   ├── hooks/
│   │   │   ├── useWebSocket.ts
│   │   │   └── useApi.ts
│   │   └── lib/
│   │       ├── api.ts
│   │       └── utils.ts
│   └── public/
│
├── tests/
│   ├── unit/
│   │   ├── test_converter.py
│   │   ├── test_streaming.py
│   │   ├── test_router.py
│   │   ├── test_providers.py
│   │   └── test_cli.py
│   ├── integration/
│   │   ├── test_server.py
│   │   ├── test_routing.py
│   │   └── test_failover.py
│   ├── e2e/
│   │   ├── test_ui_dashboard.py
│   │   ├── test_ui_routing.py
│   │   └── test_ui_debug.py
│   └── conftest.py
│
├── config/
│   └── default.yaml                # Default configuration
│
├── pyproject.toml
├── README.md
└── PLAN.md
```

## Agent Types & Routing

### Agent Types

| Agent Type     | Description                  | Default Provider       |
| -------------- | ---------------------------- | ---------------------- |
| `default`      | Standard requests            | Anthropic Native       |
| `background`   | Background/async tasks       | Antigravity            |
| `think`        | Extended thinking (Opus)     | Antigravity (thinking) |
| `long_context` | Requests > context threshold | Gemini (1M context)    |
| `websearch`    | Web search enabled           | Gemini with grounding  |

### Routing Rules (YAML Config)

```yaml
routing:
  rules:
    - name: thinking-requests
      match:
        thinking: enabled
      provider: antigravity-thinking

    - name: long-context
      match:
        context_tokens: ">100000"
      provider: gemini-pro

    - name: websearch
      match:
        agent_type: websearch
      provider: gemini-grounded

    - name: background
      match:
        agent_type: background
      provider: antigravity

    - name: default
      match: "*"
      provider: anthropic
```

## CLI Commands

```bash
# Server
a2c serve [--port 8080] [--config config.yaml]
a2c serve --dev  # With hot reload

# Claude Code Integration
a2c code                    # Launch claude with a2c proxy
a2c code --provider opus    # Use specific provider

# Status TUI
a2c status                  # Rich TUI dashboard

# Configuration
a2c config init            # Create default config
a2c config show            # Show current config
a2c config set KEY VALUE   # Set config value

# Provider Management
a2c provider list          # List providers
a2c provider test NAME     # Test provider connection
a2c provider add NAME URL  # Add provider

# Routing
a2c route list             # Show routing rules
a2c route test REQUEST     # Test which provider would handle request

# Debugging
a2c logs [--follow] [--level ERROR]
a2c debug request ID       # Inspect request by ID
a2c debug replay ID        # Replay a request
```

## API Endpoints

### Proxy Endpoints

- `POST /v1/messages` - Anthropic Messages API
- `POST /v1/chat/completions` - OpenAI Chat API

### Health Endpoints

- `GET /health/live` - Liveness probe
- `GET /health/ready` - Readiness probe
- `GET /health/providers` - Provider status

### Admin Endpoints

- `GET /admin/config` - Get configuration
- `PUT /admin/config` - Update configuration
- `GET /admin/providers` - List providers
- `POST /admin/providers/{name}/test` - Test provider
- `GET /admin/routing/rules` - Get routing rules
- `PUT /admin/routing/rules` - Update routing rules

### Debug Endpoints

- `GET /debug/requests` - List recent requests
- `GET /debug/requests/{id}` - Get request details
- `POST /debug/requests/{id}/replay` - Replay request
- `GET /debug/requests/{id}/stream` - Get SSE recording
- `WS /debug/live` - Live request feed

### WebSocket Endpoints

- `WS /ws/status` - Live metrics updates
- `WS /ws/logs` - Live log streaming

## Database Schema (PostgreSQL)

```sql
-- Requests table
CREATE TABLE requests (
    id UUID PRIMARY KEY,
    created_at TIMESTAMP DEFAULT NOW(),
    method VARCHAR(10),
    path VARCHAR(255),
    provider VARCHAR(50),
    agent_type VARCHAR(50),
    model VARCHAR(100),
    status_code INTEGER,
    latency_ms INTEGER,
    input_tokens INTEGER,
    output_tokens INTEGER,
    error TEXT,
    request_headers JSONB,
    request_body JSONB,
    response_headers JSONB,
    response_body JSONB
);

-- SSE streams table (for streaming requests)
CREATE TABLE sse_events (
    id SERIAL PRIMARY KEY,
    request_id UUID REFERENCES requests(id),
    sequence INTEGER,
    event_type VARCHAR(50),
    data JSONB,
    timestamp TIMESTAMP DEFAULT NOW()
);

-- Metrics aggregation
CREATE TABLE metrics_hourly (
    hour TIMESTAMP PRIMARY KEY,
    total_requests INTEGER,
    total_errors INTEGER,
    avg_latency_ms FLOAT,
    total_input_tokens BIGINT,
    total_output_tokens BIGINT,
    by_provider JSONB,
    by_agent_type JSONB
);

-- Indexes
CREATE INDEX idx_requests_created ON requests(created_at DESC);
CREATE INDEX idx_requests_provider ON requests(provider);
CREATE INDEX idx_requests_status ON requests(status_code);
CREATE INDEX idx_sse_request ON sse_events(request_id);
```

## Web UI Pages

### 1. Dashboard

- Request throughput chart (line graph)
- Latency percentiles (p50, p95, p99)
- Provider health status cards
- Recent errors list
- Token usage gauge

### 2. Providers

- Provider list with status indicators
- Add/edit provider modal
- Connection test button
- Credential status (env var set/missing)

### 3. Routing

- Visual routing rules table
- Drag-drop priority ordering
- Rule editor with:
  - Match conditions (model, thinking, context size, agent type)
  - Provider selection
  - Fallback provider
- Test routing with sample request

### 4. Logs

- Searchable log table
- Filters: level, provider, model, status
- Time range selector
- Live tail mode (WebSocket)
- Export to JSON

### 5. Debug

- Request inspector
  - Full request/response view
  - Headers, body, timing
  - SSE stream replay
- Request replay functionality
- Compare requests side-by-side

### 6. Settings

- Server configuration
- Log level control
- Debug storage retention
- UI preferences (theme)

## Implementation Phases

### Phase 1: Core Backend (Week 1)

- [ ] Restructure package layout
- [ ] FastAPI server with health endpoints
- [ ] Provider base class and registry
- [ ] Anthropic native provider
- [ ] Antigravity provider (existing code)
- [ ] Basic routing (model-based)
- [ ] CLI: `a2c serve`

### Phase 2: Router System (Week 1-2)

- [ ] YAML config loading
- [ ] Routing rules engine
- [ ] Agent type detection
- [ ] Context threshold detection
- [ ] OpenAI provider
- [ ] Gemini provider
- [ ] Failover logic
- [ ] CLI: `a2c route`, `a2c provider`

### Phase 3: Debug Infrastructure (Week 2)

- [ ] PostgreSQL integration
- [ ] Request logging middleware
- [ ] Debug store (save requests)
- [ ] Debug API endpoints
- [ ] SSE stream recording
- [ ] Request replay
- [ ] CLI: `a2c logs`, `a2c debug`

### Phase 4: CLI Tools (Week 2-3)

- [ ] `a2c status` TUI with Rich
- [ ] `a2c code` (spawn claude)
- [ ] `a2c config` management
- [ ] Shell completion

### Phase 5: Web UI - Foundation (Week 3)

- [ ] React + Vite setup
- [ ] shadcn/ui integration
- [ ] Layout components
- [ ] API client
- [ ] WebSocket hooks

### Phase 6: Web UI - Pages (Week 3-4)

- [ ] Dashboard page
- [ ] Providers page
- [ ] Routing page
- [ ] Logs page
- [ ] Debug page
- [ ] Settings page

### Phase 7: Testing & Polish (Week 4)

- [ ] Unit tests (>90% core coverage)
- [ ] Integration tests
- [ ] E2E tests with Playwright
- [ ] Documentation
- [ ] README with examples

## Technology Stack

### Backend

- Python 3.12+
- FastAPI + Uvicorn
- SQLAlchemy + asyncpg (PostgreSQL)
- Pydantic for validation
- httpx for HTTP client
- Rich for TUI
- Typer for CLI

### Frontend

- React 18
- TypeScript
- Vite
- TailwindCSS
- shadcn/ui components
- Recharts for charts
- TanStack Query for data fetching

### Testing

- pytest + pytest-asyncio
- pytest-cov
- Playwright (E2E)
- Factory Boy (fixtures)

## Environment Variables

```bash
# Server
A2C_PORT=8080
A2C_HOST=127.0.0.1
A2C_LOG_LEVEL=INFO
A2C_CONFIG_PATH=./config.yaml

# Database
A2C_DATABASE_URL=postgresql://localhost/a2c

# Provider Credentials
ANTHROPIC_API_KEY=sk-ant-...
GOOGLE_API_KEY=...
OPENAI_API_KEY=sk-...

# Optional
A2C_DEBUG_RETENTION_DAYS=7
A2C_METRICS_ENABLED=true
```

## Success Criteria

1. `a2c serve` starts server that proxies to multiple providers
2. `a2c code` launches Claude Code using a2c as proxy
3. `a2c status` shows live TUI dashboard
4. Web UI accessible at http://localhost:8080
5. Routing rules correctly direct requests to providers
6. Debug inspector shows full request/response
7. > 90% test coverage on core modules
8. All E2E tests pass with Playwright
