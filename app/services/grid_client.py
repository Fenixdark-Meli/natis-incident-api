import httpx
import logging
from app.config import settings

logger = logging.getLogger(__name__)

class GridClient:
    async def upload(self, ticket: str, html_content: str, user_email: str = None) -> str | None:
        email = user_email or settings.NATIS_EMAIL
        try:
            files = {
                "file": (f"natis-{ticket.lower()}.html", html_content.encode(), "text/html"),
                "title": (None, f"NATIS · {ticket} · IS Shipping Brasil"),
                "visibility": (None, "public"),
            }
            async with httpx.AsyncClient(timeout=30.0) as client:
                r = await client.post(
                    f"{settings.GRID_HOST}/api/v1/documents",
                    headers={"X-User-Email": email},
                    files=files
                )
                if r.status_code in (200, 201):
                    data = r.json()
                    return data.get("view_url") or data.get("share_url")
        except Exception as e:
            logger.error(f"Grid upload error: {e}")
        return None
