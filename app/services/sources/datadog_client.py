import httpx
from typing import Optional, Dict, List
from app.config import settings
import logging

logger = logging.getLogger(__name__)

class DatadogClient:
    def __init__(self):
        self.base = f"https://api.{settings.DD_SITE}"
        self.headers = {}
        if settings.DD_API_KEY: self.headers["DD-API-KEY"] = settings.DD_API_KEY
        if settings.DD_APP_KEY: self.headers["DD-APPLICATION-KEY"] = settings.DD_APP_KEY

    async def search_incidents(self, query: str) -> List[Dict]:
        if not settings.DD_API_KEY:
            return []
        try:
            async with httpx.AsyncClient(timeout=15) as c:
                r = await c.get(f"{self.base}/api/v2/incidents",headers=self.headers,params={"filter[query]":query,"page[size]":5})
                if r.status_code == 200:
                    return [{"id":i.get("id"),"title":i.get("attributes",{}).get("title",""),"status":i.get("attributes",{}).get("status",""),"url":f"https://app.{settings.DD_SITE}/incidents/{i.get('id')}"} for i in r.json().get("data",[])]
        except Exception as e:
            logger.warning(f"Datadog: {e}")
        return []
