from sqlalchemy.ext.asyncio import AsyncSession

from app.models.post import Post
from app.repositories.post import PostRepository
from app.schemas.post import PostCreate, PostUpdate


class PostService:
    """Business operations for Post entities."""

    @staticmethod
    async def create_post(
        db: AsyncSession,
        user_id: int,
        post_data: PostCreate,
    ) -> Post | None:
        """Create a post only under a campaign owned by the user."""

        owns_campaign = await PostRepository.campaign_belongs_to_user(
            db,
            post_data.campaign_id,
            user_id,
        )

        if not owns_campaign:
            return None

        post = Post(
            campaign_id=post_data.campaign_id,
            content=post_data.content,
            platform=post_data.platform,
            status=post_data.status,
            scheduled_at=post_data.scheduled_at,
            published_at=post_data.published_at,
        )

        return await PostRepository.create(
            db,
            post,
        )

    @staticmethod
    async def get_post(
        db: AsyncSession,
        post_id: int,
        user_id: int,
    ) -> Post | None:
        """Retrieve a post only if the user owns its campaign."""

        return await PostRepository.get_by_id_for_user(
            db,
            post_id,
            user_id,
        )

    @staticmethod
    async def get_campaign_posts(
        db: AsyncSession,
        campaign_id: int,
        user_id: int,
    ) -> list[Post] | None:
        """Retrieve posts only from a campaign owned by the user."""

        return await PostRepository.get_by_campaign_id_for_user(
            db,
            campaign_id,
            user_id,
        )

    @staticmethod
    async def update_post(
        db: AsyncSession,
        post: Post,
        post_data: PostUpdate,
    ) -> Post:
        """Apply requested changes to an existing post."""

        update_data = post_data.model_dump(
            exclude_unset=True,
        )

        for field, value in update_data.items():
            setattr(post, field, value)

        return await PostRepository.update(
            db,
            post,
        )

    @staticmethod
    async def delete_post(
        db: AsyncSession,
        post: Post,
    ) -> None:
        """Delete an existing post."""

        await PostRepository.delete(
            db,
            post,
        )