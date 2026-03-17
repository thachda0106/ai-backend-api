# README — AI Backend API Knowledge Base

> **For:** Senior engineers, tech leads, and architects onboarding to this system
> **Not for:** Beginners looking for tutorials — this assumes production Python experience

---

## What is This Knowledge Base?

This is the definitive technical reference for the **AI Backend API** — a production-grade Python monolith built on FastAPI, Domain-Driven Design, and Clean Architecture that serves a multi-tenant RAG (Retrieval-Augmented Generation) platform.

These documents were written to answer the questions a senior engineer asks in their first two weeks:

- _Why is it structured this way?_
- _Where does business logic live and why?_
- _How do I add a new feature without breaking the architecture?_
- _What will break at scale and when?_

---

## Who This Is For

| Role | Start Here |
|------|-----------|
| Backend Engineer (new to codebase) | `01-system-overview.md` → `02-layered-architecture.md` → `03-request-flow.md` |
| Senior Engineer (evaluating design) | `02-layered-architecture.md` → `07-best-practices-and-anti-patterns.md` |
| DevOps / SRE | `04-database-redis.md` → `06-scalability-strategy.md` |
| Tech Lead / Architect | All files, especially `05-concurrency-and-consistency.md` + `06-scalability-strategy.md` |

---

## Recommended Learning Path

```
Week 1 — Understand the system
  1. 01-system-overview.md       ← What and why
  2. 02-layered-architecture.md  ← How it's structured
  3. 03-request-flow.md          ← Trace a real request end-to-end

Week 2 — Go deeper
  4. 04-database-redis.md        ← Data layer internals
  5. 05-concurrency-and-consistency.md ← Hard problems
  6. 07-best-practices-and-anti-patterns.md ← What NOT to do

When scale becomes a concern
  7. 06-scalability-strategy.md  ← Evolution path
```

---

## Document Index

| File | Contents |
|------|---------|
| [`01-system-overview.md`](./01-system-overview.md) | What the system does, monolith rationale, high-level architecture |
| [`02-layered-architecture.md`](./02-layered-architecture.md) | Every layer explained with code examples and rules |
| [`03-request-flow.md`](./03-request-flow.md) | Step-by-step flows for ingest, search, and RAG chat |
| [`04-database-redis.md`](./04-database-redis.md) | PostgreSQL schema, Redis usage, Qdrant vector storage |
| [`05-concurrency-and-consistency.md`](./05-concurrency-and-consistency.md) | Async patterns, background workers, idempotency |
| [`06-scalability-strategy.md`](./06-scalability-strategy.md) | Scaling path from 1K to 1M users as a monolith |
| [`07-best-practices-and-anti-patterns.md`](./07-best-practices-and-anti-patterns.md) | DDD patterns, testing strategy, common mistakes |

---

## Conventions Used

- 🏗️ **Architecture decision** — explains a deliberate design choice
- ⚠️ **Footgun** — something that will hurt you if you ignore it
- 💡 **Senior insight** — non-obvious advice from experience
- 🔴 **Anti-pattern** — what NOT to do and why
- 📐 **Rule** — a hard architectural constraint of this codebase
