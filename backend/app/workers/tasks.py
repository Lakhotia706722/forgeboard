"""
Celery task stubs — implemented in Phase 4.
"""
from app.workers.celery_app import celery_app


@celery_app.task(name="run_agent")
def run_agent(agent_id: str, run_id: str):
    """Execute an agent run. Fully implemented in Phase 4."""
    raise NotImplementedError("Orchestration engine not yet built (Phase 4).")
