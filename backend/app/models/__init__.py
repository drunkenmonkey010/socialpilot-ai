"""
SQLAlchemy ORM model registry.

Importing models from this module ensures that all ORM models are
registered with SQLAlchemy's metadata before Alembic performs
autogeneration.
"""

from app.models.brand import Brand
from app.models.campaign import Campaign
from app.models.user import User

__all__ = [
    "User",
    "Brand",
    "Campaign",
]