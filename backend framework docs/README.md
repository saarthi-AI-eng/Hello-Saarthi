# Saarthi.ai Backend Framework — Documentation Index

This directory contains all documentation for the **Saarthi.ai backend framework**. It describes how the backend is structured, how the orchestrator (Shrijeet) interacts with it, what data flows in and out, and what conventions the development team must follow.

**No code lives here** — only markdown documentation. Implementation will follow these specs.

---

## Document Map

| # | Document | Purpose |
|---|----------|---------|
| 1 | [Backend Architecture Overview](01-backend-architecture-overview.md) | High-level architecture, layers, and how the backend fits with the orchestrator |
| 2 | [Directory Structure](02-directory-structure.md) | Full directory tree and responsibility of each folder/module |
| 3 | [Orchestrator-to-Backend Contract](03-orchestrator-to-backend-contract.md) | **What the orchestrator sends**: request formats, endpoints, payloads, and conventions |
| 4 | [Backend-to-Orchestrator Responses](04-backend-to-orchestrator-responses.md) | **What the backend returns**: response schemas, examples, and error formats |
| 5 | [Data Models and Schemas](05-data-models-and-schemas.md) | Entities, request/response schema naming, and field descriptions (documentation only) |
| 6 | [Ingestion Pipeline](06-ingestion-pipeline.md) | Video, notes, and code ingestion flows and data formats |
| 7 | [Retrieval Layer](07-retrieval-layer.md) | Hybrid retrieval engine, how experts call it, and interfaces |
| 8 | [Expert Services Interface](08-expert-services-interface.md) | Theory, Problem-Solving, Video, Code, Multimodal — inputs and outputs per expert |
| 9 | [Development Guidelines](09-development-guidelines.md) | Conventions for router, service, DAO, logging, and exceptions (adapted for Saarthi) |
| 10 | [API Endpoints Index](10-api-endpoints-index.md) | List of all API endpoints the orchestrator and frontend will call |
| 11 | [State and Context](11-state-and-context.md) | Conversation state, context storage, and what the backend exposes for memory |

---

## Quick Reference for Roles

- **Product lead (Karthik)**: Use docs 01, 02, 09 for architecture and guidelines; 05 for data design.
- **Orchestrator developer (Shrijeet)**: Use docs 03, 04, 08, 10, 11 for contracts, responses, expert interfaces, and endpoints.
- **Backend developers**: Use 01–11; start with 01, 02, 09, then 03–08 and 10–11 as needed.

---

## Version

- **Created**: January 2026  
- **Aligned with**: Karthik's approach (Part A, B, C), clarification on knowledge-graph timing, and existing coding guidelines/workbench structure.
