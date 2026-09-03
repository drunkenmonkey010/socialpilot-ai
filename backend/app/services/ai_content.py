"""
AI content generation service.

This module is responsible for building grounded prompts and generating
social media content using the configured LLM.
"""

from app.integrations.llm.ollama import generate_ollama_response
from app.models.brand import Brand
from app.models.campaign import Campaign


def build_social_post_prompt(
    brand: Brand,
    campaign: Campaign,
    platform: str,
) -> str:
    """Build a grounded prompt for generating a social media post."""

    brand_description = (
        brand.description
        if brand.description
        else "No brand description provided."
    )

    campaign_description = (
        campaign.description
        if campaign.description
        else "No campaign description provided."
    )

    return f"""
You are a professional social media content writer.

Write ONE social media post using ONLY the information provided below.

BRAND
Name: {brand.name}
Description: {brand_description}

CAMPAIGN
Name: {campaign.name}
Description: {campaign_description}

TARGET PLATFORM
{platform}

RULES
- Write exactly one social media post.
- Make it engaging and natural.
- Match the brand and campaign context.
- Adapt the style to the target platform.
- Keep it concise.
- Relevant hashtags are allowed.
- Do NOT invent products.
- Do NOT invent services.
- Do NOT invent prices.
- Do NOT invent discounts.
- Do NOT invent statistics.
- Do NOT invent product features.
- Do NOT invent promotions.
- Do NOT invent guarantees.
- Do NOT invent URLs.
- Do NOT make claims that are not supported by the information above.
- If information is limited, keep the post general.
- Return ONLY the final post.
- Do NOT explain your reasoning.
- Do NOT add a "Post:" label.
- Do NOT surround the post with quotation marks.

FINAL POST:
""".strip()


def clean_generated_content(content: str) -> str:
    """
    Clean formatting artifacts returned by the LLM.

    The model may occasionally surround the complete response
    with quotation marks. Remove only those outer quotes.
    """

    content = content.strip()

    if (
        len(content) >= 2
        and content.startswith('"')
        and content.endswith('"')
    ):
        content = content[1:-1].strip()

    return content


async def generate_social_post(
    brand: Brand,
    campaign: Campaign,
    platform: str,
) -> str:
    """Generate a grounded social media post."""

    prompt = build_social_post_prompt(
        brand=brand,
        campaign=campaign,
        platform=platform,
    )

    content = await generate_ollama_response(prompt)

    return clean_generated_content(content)