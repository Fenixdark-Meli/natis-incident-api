import httpx
from typing import Optional, Dict, Any, List
from app.config import settings
import logging

logger = logging.getLogger(__name__)

class JiraClient:
    def __init__(self):
        self.base_url = f"{settings.ATLASSIAN_URL}/rest/api/3"
        self.headers = {"Accept":"application/json"}
        if settings.ATLASSIAN_TOKEN:
            self.headers["Authorization"] = f"Bearer {settings.ATLASSIAN_TOKEN}"

    async def get_issue(self, key: str) -> Optional[Dict]:
        if not settings.ATLASSIAN_TOKEN:
            return {"error":"ATLASSIAN_TOKEN não configurado","key":key}
        try:
            async with httpx.AsyncClient(timeout=15) as c:
                r = await c.get(f"{self.base_url}/issue/{key}",headers=self.headers,params={"expand":"renderedFields,changelog"})
                if r.status_code == 200:
                    d = r.json(); f = d.get("fields",{})
                    return {"key":d.get("key"),"summary":f.get("summary",""),"status":f.get("status",{}).get("name",""),"priority":f.get("priority",{}).get("name",""),"reporter":f.get("reporter",{}).get("displayName","") if f.get("reporter") else "","assignee":f.get("assignee",{}).get("displayName","") if f.get("assignee") else "","created":f.get("created",""),"updated":f.get("updated",""),"labels":f.get("labels",[]),"linked_issues":[{"type":l.get("type",{}).get("name",""),"key":(l.get("inwardIssue") or l.get("outwardIssue") or {}).get("key","")} for l in f.get("issuelinks",[])],"url":f"{settings.ATLASSIAN_URL}/browse/{d.get('key')}"}
                return {"error":f"HTTP {r.status_code}","key":key}
        except Exception as e:
            return {"error":str(e),"key":key}

    async def search_related(self, num: str) -> List[Dict]:
        if not settings.ATLASSIAN_TOKEN or not num:
            return []
        try:
            jql = f'text ~ "{num}" AND project = SSHP ORDER BY created DESC'
            async with httpx.AsyncClient(timeout=15) as c:
                r = await c.post(f"{self.base_url}/search",headers={**self.headers,"Content-Type":"application/json"},json={"jql":jql,"maxResults":8,"fields":["summary","status","created"]})
                if r.status_code == 200:
                    return [{"key":i.get("key"),"summary":i.get("fields",{}).get("summary",""),"status":i.get("fields",{}).get("status",{}).get("name",""),"url":f"{settings.ATLASSIAN_URL}/browse/{i.get('key')}"} for i in r.json().get("issues",[])]
        except Exception as e:
            logger.warning(f"Jira search: {e}")
        return []
