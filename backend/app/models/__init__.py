# Import all models here so Alembic can detect them for autogenerate
from app.models.user import User, Workspace  # noqa: F401
from app.models.connector import Connector  # noqa: F401
from app.models.kv_store import KvEntry  # noqa: F401
