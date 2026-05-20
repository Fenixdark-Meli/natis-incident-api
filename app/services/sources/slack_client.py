import httpx
from typing import List, Dict
from app.config import settings
import logging

logger = logging.getLogger(__name__)

class SlackClient:
    def __init__(self):
        self.base = "https://slack.com/api"
        self.headers = {}
        if settings.SLACK_TOKEN:
            self.headers["Authorization"] = f"Bearer {settings.SLACK_TOKEN}"

    async def search(self, query: str) -> List[Dict]:
        if not settings.SLACK_TOKEN:
            return []
        try:
            async with httpx.AsyncClient(timeout=15) as c:
                r = await c.get(f"{self.base}/search.messages",headers=self.headers,params={"query":query,"count":8,"sort":"timestamp"})
                if r.status_code == 200 and r.json().get("ok"):
                    return [{"text":m.get("text","")[:400],"user":m.get("username",""),"channel":m.get("channel",{}).get("name",""),"permalink":m.get("permalink","")} for m in r.json().get("messages",{}).get("matches",[])]
        except Exception as e:
            logger.warning(f"Slack: {e}")
        return []
