"""
Celery Beat schedule management for scheduled agents.

How it works:
- A periodic task (sync_scheduled_agents) runs every 60 seconds.
- It queries all LIVE agents with trigger_type=SCHEDULED.
- For each, it checks if a run is due based on the cron expression.
- If due and no run is already PENDING/RUNNING, it enqueues run_agent_task.

We use the `croniter` library for cron evaluation.
⚠ Add `croniter==2.0.5` to requirements.txt (noted below).
"""
import uuid
from datetime import datetime, timezone

from celery.utils.log import get_task_logger

from app.workers.celery_app import celery_app

logger = get_task_logger(__name__)


@celery_app.task(name="sync_scheduled_agents")
def sync_scheduled_agents() -> dict:
    """
    Polls for scheduled agents that are due to run.
    Runs every minute via Celery Beat.
    """
    import asyncio
    return asyncio.run(_sync_async())


async def _sync_async() -> dict:
    from sqlalchemy import select
    from app.core.database import AsyncSessionLocal
    from app.models.agent import Agent, AgentStatus, TriggerType
    from app.models.run import AgentRun, RunStatus
    from app.services.run_service import create_run_record

    triggered = 0
    skipped = 0

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Agent).where(
                Agent.status == AgentStatus.LIVE,
                Agent.trigger_type == TriggerType.SCHEDULED,
                Agent.cron_schedule.isnot(None),
            )
        )
        agents = result.scalars().all()

        now = datetime.now(timezone.utc)

        for agent in agents:
            if not _is_cron_due(agent.cron_schedule, now):
                skipped += 1
                continue

            # Check no run is already active for this agent
            active = await db.execute(
                select(AgentRun).where(
                    AgentRun.agent_id == agent.id,
                    AgentRun.status.in_([RunStatus.PENDING, RunStatus.RUNNING]),
                )
            )
            if active.scalar_one_or_none():
                skipped += 1
                continue

            # Create run record and enqueue
            run = await create_run_record(agent.id, agent.workspace_id, "scheduled", db)
            await db.commit()

            celery_app.send_task(
                "run_agent",
                args=[str(agent.id), str(run.id)],
            )
            triggered += 1
            logger.info(f"Scheduled run enqueued for agent {agent.id} (run {run.id})")

    return {"triggered": triggered, "skipped": skipped}


def _is_cron_due(cron_expr: str, now: datetime) -> bool:
    """
    Returns True if the cron expression was due within the last 60 seconds.
    Uses croniter if available; falls back to always-False (safe default).
    """
    try:
        from croniter import croniter
        # Check if any scheduled time falls in the past 60s window
        cron = croniter(cron_expr, now)
        prev = cron.get_prev(datetime)
        delta = (now - prev).total_seconds()
        return delta <= 60
    except ImportError:
        logger.warning("croniter not installed — scheduled triggers disabled. pip install croniter==2.0.5")
        return False
    except Exception as e:
        logger.error(f"Cron evaluation error for '{cron_expr}': {e}")
        return False
