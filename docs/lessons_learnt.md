# Lessons Learnt

## 2026-03-27
- Migrated backend data access from SQLAlchemy ORM calls to Supabase client table operations.
- Introduced a shared repository utility ([backend/app/services/supabase_repo.py](backend/app/services/supabase_repo.py)) to avoid duplicated query logic and keep response payloads consistent.
- Ensured API/service migration was validated with Python syntax compilation before finalizing.
- Updated environment template and docs to reflect GitHub Models as the preferred OpenAI-compatible LLM provider.
- Documentation drift was a risk because [docs/architecture.md](docs/architecture.md) was missing; adding it reduced future ambiguity about backend data flow.
