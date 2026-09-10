from datetime import datetime, timezone

from sqlalchemy import case, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.publication import Publication, PublicationStatus


class PublicationRepository:
    """Database operations for durable Publication state."""

    @staticmethod
    async def create(
        db: AsyncSession,
        publication: Publication,
    ) -> Publication:
        """Create a durable publication record."""

        db.add(publication)

        await db.commit()
        await db.refresh(publication)

        return publication

    @staticmethod
    async def get_by_id(
        db: AsyncSession,
        publication_id: int,
    ) -> Publication | None:
        """Retrieve a publication by ID."""

        result = await db.execute(
            select(Publication).where(
                Publication.id == publication_id,
            )
        )

        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_publication_key(
        db: AsyncSession,
        publication_key: str,
    ) -> Publication | None:
        """Retrieve a publication by its durable idempotency key."""

        result = await db.execute(
            select(Publication).where(
                Publication.publication_key == publication_key,
            )
        )

        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_post_and_account(
        db: AsyncSession,
        post_id: int,
        social_account_id: int,
    ) -> Publication | None:
        """Retrieve publication for a post and social account."""

        result = await db.execute(
            select(Publication).where(
                Publication.post_id == post_id,
                Publication.social_account_id == social_account_id,
            )
        )

        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_post(
        db: AsyncSession,
        post_id: int,
    ) -> list[Publication]:
        """Return all platform publications for a post."""

        result = await db.execute(
            select(Publication)
            .where(
                Publication.post_id == post_id,
            )
            .order_by(Publication.id.asc())
        )

        return list(result.scalars().all())

    @staticmethod
    async def increment_attempt(
        db: AsyncSession,
        publication_id: int,
    ) -> Publication | None:
        """Increment the durable external publication attempt counter."""

        now = datetime.now(timezone.utc)

        result = await db.execute(
            update(Publication)
            .where(
                Publication.id == publication_id,
            )
            .values(
                attempt_count=Publication.attempt_count + 1,
                status=PublicationStatus.PUBLISHING.value,
                first_attempt_at=case(
                    (
                        Publication.first_attempt_at.is_(None),
                        now,
                    ),
                    else_=Publication.first_attempt_at,
                ),
                last_attempt_at=now,
                last_error=None,
                retry_after_seconds=None,
            )
            .returning(Publication)
        )

        publication = result.scalar_one_or_none()

        if publication is None:
            await db.rollback()
            return None

        await db.commit()

        return publication

    @staticmethod
    async def mark_published(
        db: AsyncSession,
        publication_id: int,
        external_post_id: str,
        publication_metadata: dict | None = None,
    ) -> Publication | None:
        """Persist successful external publication state."""

        result = await db.execute(
            update(Publication)
            .where(
                Publication.id == publication_id,
            )
            .values(
                status=PublicationStatus.PUBLISHED.value,
                external_post_id=external_post_id,
                published_at=datetime.now(timezone.utc),
                last_error=None,
                retry_after_seconds=None,
                publication_metadata=publication_metadata,
            )
            .returning(Publication)
        )

        publication = result.scalar_one_or_none()

        if publication is None:
            await db.rollback()
            return None

        await db.commit()

        return publication

    @staticmethod
    async def mark_failed(
        db: AsyncSession,
        publication_id: int,
        error: str,
        retry_after_seconds: int | None = None,
    ) -> Publication | None:
        """Persist a permanent publication failure."""

        result = await db.execute(
            update(Publication)
            .where(
                Publication.id == publication_id,
            )
            .values(
                status=PublicationStatus.FAILED.value,
                last_error=error,
                retry_after_seconds=retry_after_seconds,
            )
            .returning(Publication)
        )

        publication = result.scalar_one_or_none()

        if publication is None:
            await db.rollback()
            return None

        await db.commit()

        return publication

    @staticmethod
    async def record_error(
        db: AsyncSession,
        publication_id: int,
        error: str,
        retry_after_seconds: int | None = None,
    ) -> Publication | None:
        """Persist a retryable publication error."""

        result = await db.execute(
            update(Publication)
            .where(
                Publication.id == publication_id,
            )
            .values(
                last_error=error,
                retry_after_seconds=retry_after_seconds,
            )
            .returning(Publication)
        )

        publication = result.scalar_one_or_none()

        if publication is None:
            await db.rollback()
            return None

        await db.commit()

        return publication