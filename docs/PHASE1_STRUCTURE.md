# Phase 1 Structure Boundaries (Team Safe)

This document defines where new work should be added during Phase 1 without breaking existing team components.

## Rules

- Keep current working paths unchanged unless the team approves a migration.
- Put language-model-specific logic only inside `comp-language-model` and `models/language-model`.
- Put reusable/shared utilities in `backend/shared`.
- Avoid cross-component imports that create tight coupling.

## Backend Boundaries

- `backend/shared/config/`: existing shared runtime configuration (already in use).
- `backend/shared/schemas/`: shared request/response contracts.
- `backend/shared/utils/`: shared helpers usable by multiple components.
- `backend/comp-transaction-sementic/`: component-specific backend code.
- `backend/comp-tax-optimization/`: component-specific backend code.
- `backend/comp-personalized-recommendation/`: component-specific backend code.
- `backend/comp-language-model/`: language-model-specific backend code only.

## Model Boundaries

- `models/transaction-semantic/`: artifacts and code for transaction semantic model work.
- `models/tax-optimization/`: artifacts and code for optimization model work.
- `models/personalized-recommendation/`: artifacts and code for recommendation model work.
- `models/language-model/`: language-model-specific artifacts and code only.

## Non-Breaking Phase 1 Policy

- No refactor of existing imports in `backend/shared/config`.
- No movement of current files (`scripts/init_db.py`, migrations, configs) in Phase 1.
- New folders are additive and safe for parallel team development.
