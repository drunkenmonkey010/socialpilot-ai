from app.integrations.instagram.client import InstagramClient
from app.integrations.platforms.base import PlatformPublisher
from app.integrations.platforms.errors import (
    PlatformAuthenticationError,
    PlatformPermanentError,
    PlatformRateLimitError,
    PlatformTransientError,
    PlatformValidationError,
)
from app.integrations.platforms.types import (
    PlatformCapabilities,
    PublicationResult,
)
from app.models.social_account import SocialAccount


class InstagramAdapter(PlatformPublisher):
    """
    Instagram implementation of the generic publishing contract.

    Instagram-specific API behavior remains inside this adapter and its
    low-level client. The application core interacts only with the
    PlatformPublisher interface.
    """

    platform = "instagram"

    @property
    def capabilities(self) -> PlatformCapabilities:
        """
        Return capabilities currently supported by this adapter.
        """

        return PlatformCapabilities(
            text=True,
            images=True,
            video=True,
            carousel=True,
            scheduling=False,
            analytics=False,
            reconciliation=False,
            max_text_length=2200,
        )

    async def publish(
        self,
        account: SocialAccount,
        content: str,
        publication_key: str | None = None,
    ) -> PublicationResult:
        """
        Publish content to Instagram.

        Instagram publishing requires media. Since the current Post model
        does not yet contain a media URL, this method deliberately rejects
        text-only publication rather than pretending Instagram supports it.
        """

        if not account.access_token:
            raise PlatformAuthenticationError(
                "Instagram access token is required."
            )

        self.validate_content(content)

        raise PlatformValidationError(
            "Instagram publication requires media. "
            "The current Post model supports text-only content, so "
            "Instagram publishing will be enabled after media support "
            "is added."
        )

    async def publish_image(
        self,
        account: SocialAccount,
        image_url: str,
        caption: str = "",
        publication_key: str | None = None,
    ) -> PublicationResult:
        """
        Publish an image with an optional caption to Instagram.

        This method is ready for use once the application publication
        layer supports media URLs.
        """

        if not account.access_token:
            raise PlatformAuthenticationError(
                "Instagram access token is required."
            )

        if not image_url:
            raise PlatformValidationError(
                "Instagram image URL is required."
            )

        self.validate_content(caption)

        client = InstagramClient(
            access_token=account.access_token,
        )

        try:
            container = await client.create_media_container(
                image_url=image_url,
                caption=caption,
            )

            creation_id = container.get("id")

            if not creation_id:
                raise PlatformTransientError(
                    "Instagram did not return a media container ID."
                )

            response = await client.publish_media_container(
                creation_id=str(creation_id),
            )

        except (
            PlatformAuthenticationError,
            PlatformRateLimitError,
            PlatformPermanentError,
            PlatformTransientError,
        ):
            raise

        external_post_id = response.get("id")

        if not external_post_id:
            raise PlatformTransientError(
                "Instagram did not return a published media ID."
            )

        return PublicationResult(
            platform=self.platform,
            external_post_id=str(external_post_id),
            metadata={
                "publication_key": publication_key,
                "container_id": str(creation_id),
                "response": response,
            },
        )

    def classify_error(
        self,
        exc: Exception,
    ) -> bool:
        """
        Determine whether an Instagram error should be retried.
        """

        if isinstance(
            exc,
            (
                PlatformTransientError,
                PlatformRateLimitError,
            ),
        ):
            return True

        if isinstance(
            exc,
            (
                PlatformAuthenticationError,
                PlatformPermanentError,
                PlatformValidationError,
            ),
        ):
            return False

        return True


instagram_adapter = InstagramAdapter()