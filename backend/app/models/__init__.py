# Import all models here so Alembic can detect them for autogenerate
from app.models.user import User, Workspace  # noqa: F401
from app.models.connector import Connector  # noqa: F401
from app.models.kv_store import KvEntry  # noqa: F401
from app.models.agent import Agent, AgentConnector  # noqa: F401
from app.models.run import AgentRun  # noqa: F401
from app.models.audit import AuditLogEntry  # noqa: F401
from app.models.voice_agent import VoiceAgent, CallLog  # noqa: F401
