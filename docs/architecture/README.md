# Architecture

Replace this template with a navigable description of the actual system.

## System context

- Users and external actors:
- Primary use cases:
- External systems:
- Trust boundaries:
- Data classifications:

## Components

| Component | Responsibility | Interface | Owner/source |
| --- | --- | --- | --- |
| `<NAME>` | `<RESPONSIBILITY>` | `<API/PROTOCOL>` | `<PATH/TEAM>` |

## Data and control flow

Document normal flow, failure flow, retries, idempotency, ordering, persistence, and recovery.

## Invariants

List properties that changes must preserve, for example:

- authorization is checked at a named boundary;
- data has a single authoritative owner;
- protocol messages remain backward compatible;
- retries cannot duplicate irreversible effects;
- generated artifacts are reproducible from tracked inputs.

## Deployment and operations

- Environments:
- Configuration sources:
- Secret boundaries:
- Deployment procedure:
- Rollback procedure:
- Observability:
- Capacity and failure assumptions:

## Local maps

For a large repository, add component-level documents and nested `AGENTS.md` files rather than expanding the root instruction file indefinitely.
