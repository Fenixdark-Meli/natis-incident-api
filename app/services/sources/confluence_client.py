import httpx
from typing import List, Dict
from app.config import settings
import logging

logger = logging.getLogger(__name__)

class ConfluenceClient:
    def __init__(self):
        self.base = f"{settings.ATLASSIAN_URL}/wiki/rest/api"
        self.headers = {"Accept":"application/json"}
        if settings.ATLASSIAN_TOKEN:
            self.headers["Authorization"] = f"Bearer {settings.ATLASSIAN_TOKEN}"

    async def search(self, query: str, space: str = "ISSM") -> List[Dict]:
        if not settings.ATLASSIAN_TOKEN:
            return []
        try:
            async with httpx.AsyncClient(timeout=15) as c:
                r = await c.get(f"{self.base}/content/search",headers=self.headers,params={"cql":f'space="{space}" AND text~"{query}" ORDER BY lastmodified DESC',"limit":5,"expand":"body.view"})
                if r.status_code == 200:
                    return [{"id":p.get("id"),"title":p.get("title",""),"url":f"{settings.ATLASSIAN_URL}/wiki{p.get('_links',{}).get('webui','')}","excerpt":p.get("body",{}).get("view",{}).get("value","")[:500] if p.get("body") else ""} for p in r.json().get("results",[])]
        except Exception as e:
            logger.warning(f"Confluence: {e}")
        return []
