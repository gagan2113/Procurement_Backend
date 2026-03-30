from backend.db.session import engine
from backend.db.base import Base

# Import all models so they are registered on the Base metadata
import backend.models.request  # noqa: F401


def create_all_tables() -> None:
    """Create all database tables if they don't exist."""
    Base.metadata.create_all(bind=engine)
