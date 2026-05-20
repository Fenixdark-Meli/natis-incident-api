import httpx
from typing import Optional, Dict, List
from app.config import settings
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class DriveClient:
    def __init__(self):
        self.base = "https://www.googleapis.com/drive/v3"
        self.headers = {}
        if settings.DRIVE_TOKEN:
            self.headers["Authorization"] = f"Bearer {settings.DRIVE_TOKEN}"

    async def search(self, query: str, folder_id: str = None) -> List[Dict]:
        if not settings.DRIVE_TOKEN:
            return []
        try:
            folder = folder_id or settings.DRIVE_RECORDINGS_FOLDER
            async with httpx.AsyncClient(timeout=15) as c:
                r = await c.get(f"{self.base}/files",headers=self.headers,params={"q":f"'{folder}' in parents and fullText contains '{query}'","pageSize":8,"fields":"files(id,name,mimeType,createdTime,webViewLink)"})
                if r.status_code == 200:
                    return [{"id":f.get("id"),"name":f.get("name",""),"type":f.get("mimeType",""),"created":f.get("createdTime",""),"url":f.get("webViewLink","")} for f in r.json().get("files",[])]
        except Exception as e:
            logger.warning(f"Drive search: {e}")
        return []

    async def save_report(self, ticket: str, content: str) -> Optional[str]:
        if not settings.DRIVE_TOKEN:
            return None
        try:
            filename = f"NATIS_{ticket}_{datetime.now().strftime('%Y%m%d_%H%M')}.md"
            metadata = {"name":filename,"parents":[settings.DRIVE_NATIS_FOLDER],"mimeType":"text/plain"}
            async with httpx.AsyncClient(timeout=30) as c:
                r = await c.post(f"https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart",headers=self.headers,files={"metadata":(None,str(metadata),"application/json"),"file":(filename,content.encode(),"text/plain")})
                if r.status_code in (200,201):
                    return f"https://drive.google.com/file/d/{r.json().get('id')}/view"
        except Exception as e:
            logger.warning(f"Drive save: {e}")
        return None
