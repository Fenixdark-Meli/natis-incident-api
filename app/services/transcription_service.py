"""
Serviço de transcrição de vídeos MP4 do Drive
Usa OpenAI Whisper para transcrever gravações do war room
"""
import httpx
import logging
import os
import tempfile
from typing import Optional
from app.config import settings

logger = logging.getLogger(__name__)


class TranscriptionService:
    """Transcreve vídeos MP4 do Google Drive usando Whisper"""

    WHISPER_MODEL = "whisper-1"
    SUPPORTED_FORMATS = [".mp4", ".mp3", ".wav", ".m4a", ".webm"]
    MAX_SIZE_MB = 25  # limite do Whisper API

    async def transcribe_from_drive(self, file_id: str) -> Optional[str]:
        """Baixa e transcreve um arquivo do Drive"""
        if not settings.DRIVE_TOKEN:
            return None

        try:
            # Download do arquivo
            logger.info(f"Baixando arquivo do Drive: {file_id}")
            content = await self._download_drive_file(file_id)
            if not content:
                return None

            # Transcreve
            return await self._transcribe_bytes(content, f"recording_{file_id}.mp4")
        except Exception as e:
            logger.error(f"Transcription error: {e}")
            return None

    async def transcribe_from_url(self, url: str) -> Optional[str]:
        """Transcreve de uma URL direta"""
        try:
            async with httpx.AsyncClient(timeout=120) as c:
                r = await c.get(url)
                if r.status_code == 200:
                    return await self._transcribe_bytes(r.content, "recording.mp4")
        except Exception as e:
            logger.error(f"URL transcription error: {e}")
        return None

    async def _download_drive_file(self, file_id: str) -> Optional[bytes]:
        headers = {"Authorization": f"Bearer {settings.DRIVE_TOKEN}"}
        try:
            async with httpx.AsyncClient(timeout=120) as c:
                # Tenta export como video primeiro
                r = await c.get(
                    f"https://www.googleapis.com/drive/v3/files/{file_id}?alt=media",
                    headers=headers
                )
                if r.status_code == 200:
                    return r.content
        except Exception as e:
            logger.error(f"Drive download error: {e}")
        return None

    async def _transcribe_bytes(self, audio_bytes: bytes, filename: str) -> Optional[str]:
        """Transcreve usando OpenAI Whisper API"""
        if not settings.ANTHROPIC_API_KEY:
            # Usa mock para testes sem API key
            return self._mock_transcription(filename)

        try:
            # Whisper aceita até 25MB
            size_mb = len(audio_bytes) / (1024 * 1024)
            if size_mb > self.MAX_SIZE_MB:
                logger.warning(f"Arquivo grande ({size_mb:.1f}MB) — usando transcrição parcial")
                audio_bytes = audio_bytes[:self.MAX_SIZE_MB * 1024 * 1024]

            with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
                tmp.write(audio_bytes)
                tmp_path = tmp.name

            try:
                import openai
                client = openai.OpenAI(api_key=settings.ANTHROPIC_API_KEY)
                with open(tmp_path, "rb") as f:
                    transcript = client.audio.transcriptions.create(
                        model=self.WHISPER_MODEL,
                        file=f,
                        language="pt",
                        response_format="text"
                    )
                return str(transcript)
            finally:
                os.unlink(tmp_path)

        except ImportError:
            logger.warning("openai package não instalado — sem transcrição")
            return None
        except Exception as e:
            logger.error(f"Whisper error: {e}")
            return None

    def _mock_transcription(self, filename: str) -> str:
        return f"""[Transcrição simulada — configure OPENAI_API_KEY para transcrição real]
Arquivo: {filename}
Para transcrever gravações reais, instale: pip install openai
E configure OPENAI_API_KEY nas variáveis de ambiente."""
