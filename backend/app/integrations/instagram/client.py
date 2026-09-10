from typing import Any

import httpx

from app.core.config import settings
from app.integrations.platforms.errors import (
    PlatformAuthenticationError,
    PlatformPermanentError,
    PlatformRateLimitError,
    PlatformTransientError,
)


class InstagramClient:
    """
    Low-level client for the Instagram Graph API.

    This class owns HTTP communication with Instagram.
    Business logic remains in the adapter/service layers.
    """

    def __init__(
        self,
        access_token: str,
    ) -> None:
        if not access_token:
            raise ValueError(
                "Instagram access token is required."
            )

        self.access_token = access_token
        self.base_url = settings.instagram_api_base_url

    async def get_account(
        self,
    ) -> dict[str, Any]:
        """
        Fetch the authenticated Instagram account.

        Returns account ID and username information.
        """

        return await self._get(
            "/me",
            params={
                "fields": "id,username",
            },
        )

    async def create_media_container(
        self,
        image_url: str,
        caption: str,
    ) -> dict[str, Any]:
        """
        Create an Instagram media container.

        Instagram content publishing requires media. Text-only posts
        cannot be published through the Instagram publishing API.
        """

        if not image_url:
            raise ValueError(
                "Instagram image URL is required."
            )

        return await self._post(
            "/me/media",
            data={
                "image_url": image_url,
                "caption": caption,
            },
        )

    async def publish_media_container(
        self,
        creation_id: str,
    ) -> dict[str, Any]:
        """
        Publish a previously created Instagram media container.
        """

        if not creation_id:
            raise ValueError(
                "Instagram creation ID is required."
            )

        return await self._post(
            "/me/media_publish",
            data={
                "creation_id": creation_id,
            },
        )

    async def _get(
        self,
        path: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Execute an authenticated GET request."""

        request_params = dict(params or {})
        request_params["access_token"] = self.access_token

        try:
            async with httpx.AsyncClient(
                timeout=30.0,
            ) as client:
                response = await client.get(
                    f"{self.base_url}{path}",
                    params=request_params,
                    headers={
                        "Accept": "application/json",
                    },
                )

            return self._handle_response(response)

        except (
            PlatformAuthenticationError,
            PlatformRateLimitError,
            PlatformPermanentError,
            PlatformTransientError,
        ):
            raise

        except (
            httpx.TimeoutException,
            httpx.NetworkError,
        ) as exc:
            raise PlatformTransientError(
                f"Instagram network request failed: {exc}"
            ) from exc

    async def _post(
        self,
        path: str,
        data: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute an authenticated POST request."""

        request_data = dict(data)
        request_data["access_token"] = self.access_token

        try:
            async with httpx.AsyncClient(
                timeout=30.0,
            ) as client:
                response = await client.post(
                    f"{self.base_url}{path}",
                    data=request_data,
                    headers={
                        "Accept": "application/json",
                    },
                )

            return self._handle_response(response)

        except (
            PlatformAuthenticationError,
            PlatformRateLimitError,
            PlatformPermanentError,
            PlatformTransientError,
        ):
            raise

        except (
            httpx.TimeoutException,
            httpx.NetworkError,
        ) as exc:
            raise PlatformTransientError(
                f"Instagram network request failed: {exc}"
            ) from exc

    @staticmethod
    def _handle_response(
        response: httpx.Response,
    ) -> dict[str, Any]:
        """
        Convert Instagram HTTP failures into generic platform errors.
        """

        if response.is_success:
            try:
                return response.json()
            except ValueError as exc:
                raise PlatformTransientError(
                    "Instagram returned an invalid JSON response."
                ) from exc

        status_code = response.status_code

        try:
            payload = response.json()
            error_payload = payload.get("error", {})
            message = error_payload.get(
                "message",
                response.text,
            )
        except ValueError:
            message = response.text

        if status_code in (401, 403):
            raise PlatformAuthenticationError(
                f"Instagram authentication failed: {message}"
            )

        if status_code == 429:
            raise PlatformRateLimitError(
                f"Instagram rate limit reached: {message}"
            )

        if 400 <= status_code <= 499:
            raise PlatformPermanentError(
                f"Instagram request rejected: {message}"
            )

        if 500 <= status_code <= 599:
            raise PlatformTransientError(
                f"Instagram server error: {message}"
            )

        raise PlatformPermanentError(
            f"Instagram request failed with HTTP "
            f"{status_code}: {message}"
        )