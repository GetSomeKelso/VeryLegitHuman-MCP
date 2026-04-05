"""AI face generation via ThisPersonDoesNotExist."""

from __future__ import annotations

import logging
import uuid
from pathlib import Path
from typing import Optional

import httpx

from ..config import FACES_DIR, TPDNE_TIMEOUT, TPDNE_URL

logger = logging.getLogger(__name__)


async def fetch_face_tpdne(persona_id: Optional[str] = None) -> dict:
    """Fetch a random AI-generated face from ThisPersonDoesNotExist.

    Downloads the JPEG and saves it locally.
    Returns dict with file_path and source info.
    """
    FACES_DIR.mkdir(parents=True, exist_ok=True)

    filename = f"{persona_id or uuid.uuid4()}.jpg"
    filepath = FACES_DIR / filename

    async with httpx.AsyncClient(timeout=TPDNE_TIMEOUT) as client:
        response = await client.get(
            TPDNE_URL,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
            follow_redirects=True,
        )
        response.raise_for_status()

        filepath.write_bytes(response.content)
        logger.info("Face saved to %s (%d bytes)", filepath, len(response.content))

    return {
        "file_path": str(filepath),
        "filename": filename,
        "source": "thispersondoesnotexist",
        "size_bytes": len(response.content),
    }
