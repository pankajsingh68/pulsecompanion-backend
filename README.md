# PulseCompanion

**Adaptive Human-State-Aware AI Orchestration System**

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688.svg)](https://fastapi.tiangolo.com)
[![LangGraph](https://img.shields.io/badge/LangGraph-0.2-orange.svg)](https://github.com/langchain-ai/langgraph)
[![Version](https://img.shields.io/badge/version-8.0.0-green.svg)]()

---

## What Is This

PulseCompanion is a **real-time adaptive orchestration system** that continuously infers human emotional and cognitive state from multimodal signals (text, voice prosody, biometrics) and dynamically adjusts AI response behavior — tone, verbosity, pacing, and interaction mode — without explicit user input.

The system is **not a chatbot**. It is an orchestration layer that sits between raw sensor signals and LLM output, making real-time decisions about *how* to respond based on *who* the user is right now.

---

## Core Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        SENSOR LAYER                                  │
│  Text Sentiment │ Voice Prosody │ Biometrics │ Behavioral Signals   │
└────────────────────────────┬────────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────────┐
│                    HUMAN STATE ENGINE                                 │
│  Multimodal Fusion → Stress/Fatigue/Load/Engagement Inference       │
│  Temporal Tracking → Stability Analysis → Confidence Scoring        │
└────────────────────────────┬────────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────────┐
│               EMOTIONAL INTELLIGENCE CORE                            │
│  Fusion Engine │ Rhythm Engine │ Overload Controller │ Relational   │
│  Pattern Memory │ Adaptive Interaction Engine                        │
└────────────────────────────┬────────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────────┐
│              ADAPTIVE UX ORCHESTRATION                                │
│  Response Policy → Prompt Conditioning → Constraint Enforcement     │
│  Mode Selection │ Verbosity Control │ Pacing │ Silence Decisions    │
└────────────────────────────┬────────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────────┐
│                   COGNITION LAYER                                     │
│  LLM Router → Phi-3 Backend → Response Constraint Enforcer          │
│  Context Assembly │ Summarization │ Priority Budget                  │
└────────────────────────────┬────────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────────┐
│                   DELIVERY LAYER                                      │
│  WebSocket Streaming │ Voice Pipeline │ Heartbeat │ Event Bus       │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Key Capabilities

| Capability | Description |
|---|---|
| **Multimodal State Inference** | Fuses text sentiment, voice prosody, heart rate, HRV, and behavioral signals into a unified human state model |
| **Adaptive Response Policy** | Dynamically selects response mode, verbosity, tone, and pacing based on inferred state |
| **Silence Decisions** | System can choose *not* to respond when cognitive load is too high or user needs space |
| **Emotional Intelligence Cycle** | 5-engine pipeline: fusion, rhythm, interaction, overload regulation, relational memory |
| **Cognitive Memory** | Working memory, episodic detection, semantic self-model, importance scoring, decay |
| **Voice Pipeline** | VAD → transcription → prosody extraction → TTS output (Kokoro ONNX) |
| **Runtime Stability** | Backpressure control, adaptive stabilization, hysteresis, bounded strategy enforcement |
| **Observable Runtime** | Event bus, lineage tracing, loop traces, runtime introspection API |
| **Chaos Engineering** | Built-in simulation lab with failure injection, stream corruption, WebSocket flood testing |

---

## Response Modes

The orchestration layer selects from these modes every cycle:

| Mode | Trigger | Behavior |
|------|---------|----------|
| **NORMAL** | Balanced state, moderate engagement | Standard conversational responses |
| **CALM_MINIMAL** | Elevated stress, low engagement | Shorter, gentler, reduced complexity |
| **FOCUS_MODE** | High cognitive load | Structured, concise, no tangents |
| **OVERLOAD_PROTECTION** | Extreme stress + high load | Ultra-brief, no new information, check-ins only |
| **SILENCE** | Very high load, low openness | No response — system stays quiet |

Transitions are rate-clamped (max ±0.15/cycle), hysteresis-guarded, and cooldown-protected.

---

## Prerequisites

- **Python 3.11+**
- **Ollama** running locally with:
  - `phi3:mini` — primary LLM
  - `nomic-embed-text` — embedding model
- **Optional**: Kokoro ONNX model files for TTS (place in `models/kokoro/`)

---

## Quick Start

```bash
cd backend/

# Create and activate virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env

# Pull Ollama models
ollama pull phi3:mini
ollama pull nomic-embed-text

# Start Ollama (separate terminal)
ollama serve

# Run the server
python main.py
```

Server starts at `http://localhost:8000`.

---

## API Reference

### Health & Readiness

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Live runtime health with session count, TTS status, LLM backend |
| `/ready` | GET | Kubernetes-style readiness probe |

### Chat Pipeline

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/chat` | POST | Send message through full adaptive pipeline |
| `/api/state/current` | GET | Current inferred human state for a session |

### Runtime Observability

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/runtime/traces` | GET | Recent loop traces |
| `/api/runtime/pressure` | GET | Backpressure state |
| `/api/runtime/introspection` | GET | Full runtime introspection |

### WebSocket

| Endpoint | Description |
|----------|-------------|
| `ws://localhost:8000/ws/{session_id}` | Real-time bidirectional state + response streaming |
| `ws://localhost:8000/voice/{session_id}` | Voice session with audio streaming |

---

## WebSocket Protocol

**Send:**
```json
{
  "type": "message",
  "content": "Hello",
  "biometric_hints": {"heart_rate": 72, "hrv": 55}
}
```

**Receive:**
```json
{
  "type": "response",
  "content": "Hi there.",
  "ux_mode": "NORMAL",
  "human_state": {
    "stress": 0.2,
    "cognitive_load": 0.3,
    "engagement": 0.7,
    "fatigue": 0.1
  }
}
```

---

## Project Structure

```
backend/
├── main.py                     # FastAPI entry point
├── config.py                   # Pydantic settings
├── requirements.txt
│
├── api/routes/                 # HTTP endpoints
├── websocket/                  # WS manager, router, handlers, heartbeat
│
├── human_state/                # Multimodal state inference engine
│   ├── signals/                # Text, biometric, behavior, voice extractors
│   ├── inference/              # Stress, fatigue, load, engagement, stability
│   ├── fusion/                 # Multimodal signal fusion
│   └── temporal/               # State tracking over time
│
├── emotion/                    # Emotional intelligence core
│   ├── emotional_fusion_engine.py
│   ├── conversational_rhythm_engine.py
│   ├── adaptive_interaction_engine.py
│   ├── overload_regulation_controller.py
│   ├── relational_pattern_memory.py
│   └── emotional_intelligence_core.py
│
├── orchestration/              # Adaptive UX orchestration
│   ├── orchestrator.py         # Main orchestration loop
│   ├── models.py               # UXStrategy, VerbosityLevel, ResponseTone
│   ├── rules.py                # Mode selection rules
│   └── temporal_adaptation.py  # Transition smoothing
│
├── cognition/                  # LLM layer
│   ├── response_policy_engine.py
│   ├── prompt_conditioner.py
│   ├── response_constraint_enforcer.py
│   ├── llm_orchestrator.py
│   ├── llm_router.py
│   ├── conversation_context_assembler.py
│   └── backends/               # Phi-3 Ollama, llama.cpp
│
├── memory/                     # Cognitive memory system
│   ├── cognitive_memory.py     # Integration layer
│   ├── working/                # Working memory buffer
│   ├── episodic/               # Episode detection + store
│   ├── semantic/               # Self-model
│   ├── decay/                  # Memory decay engine
│   └── retrieval/              # Retrieval router
│
├── voice/                      # Voice pipeline
│   ├── voice_pipeline.py       # Full pipeline orchestration
│   ├── vad_runtime.py          # Voice activity detection
│   ├── transcription_stream.py # STT streaming
│   ├── prosody_extractor.py    # Emotional prosody analysis
│   ├── voice_session_bridge.py # WebSocket bridge
│   └── backends/               # Kokoro TTS, SenseVoice
│
├── runtime/                    # Runtime infrastructure
│   ├── session_runtime.py      # Session lifecycle
│   ├── runtime_clock.py        # LIVE/REPLAY/FIXED clock modes
│   ├── runtime_supervisor.py   # Lifecycle coordination, panic mode
│   ├── backpressure_controller.py
│   ├── adaptive_stabilizer.py  # Hysteresis, damping, spike prevention
│   ├── snapshot_consistency.py # Atomic state snapshots
│   └── concurrency_model.py    # Ownership + mutation tracking
│
├── events/                     # Observable event system
│   ├── event_bus.py            # Async event bus
│   ├── lineage.py              # Causal lineage tracking
│   └── pipeline_instrumentation.py
│
├── safety/                     # Safety boundaries
│   └── bounded_strategy.py     # Strategy enforcement limits
│
├── streaming/                  # Ambient streaming runtime
├── bootstrap/                  # Application bootstrapping
├── simulation/                 # Sensor + session simulation
├── chaos/                      # Chaos engineering suite
├── validation/                 # Resilience validation
├── metrics/                    # Runtime metrics collection
├── integration/                # Integration validation layer
├── confidence/                 # Confidence scoring
├── baseline/                   # Rolling baseline computation
└── models/kokoro/              # TTS model files (not in git)
```

---

## Design Principles

1. **Runtime is the decision maker** — the LLM generates text, but the orchestration layer decides *if*, *when*, and *how* to deliver it
2. **Deterministic pipelines** — all state inference and policy decisions are reproducible given the same inputs
3. **Bounded memory** — every buffer, queue, and history has hard caps; no unbounded growth
4. **Replay-safe** — monotonic timestamps, no `random()` in runtime paths, clock abstraction
5. **Graceful degradation** — every subsystem has fallback behavior; failures never cascade
6. **Rate-clamped transitions** — emotional dimensions change max ±0.15 per cycle; no jarring shifts
7. **Observable by default** — event bus, lineage traces, and introspection APIs built into every layer

---

## Configuration

All configuration via environment variables (see `.env.example`):

| Variable | Default | Description |
|----------|---------|-------------|
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama API endpoint |
| `OLLAMA_MODEL` | `phi3:mini` | Primary LLM model |
| `OLLAMA_EMBED_MODEL` | `nomic-embed-text` | Embedding model |
| `CHROMADB_PATH` | `./chroma_data` | Vector store path |
| `LOG_LEVEL` | `INFO` | Logging verbosity |
| `SESSION_TIMEOUT_MINUTES` | `30` | Session inactivity timeout |
| `LLM_BACKEND` | `phi3_ollama` | Active LLM backend |

---

## Development

```bash
# Run with auto-reload
ENV=development python main.py

# Debug: test full cognition chain (EI → Policy → Phi-3 → Enforcer)
python test_llm_direct.py
```

---

## Version

**8.0.0** — Full adaptive orchestration with voice pipeline, cognitive memory, emotional intelligence, and observable runtime.

---

## License

Proprietary. Internal development.
