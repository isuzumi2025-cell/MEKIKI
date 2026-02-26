"""
Page metadata API route.

Exposes PDF page geometry (width, height, rotation) so the web client
can perform accurate coordinate conversions between PDF point space
and CSS pixel space.
"""

import json
from pathlib import Path
from typing import Any, Dict

try:
    from fastapi import APIRouter, HTTPException

    router = APIRouter()

    @router.get("/documents/{doc_id}/page-metadata")
    async def get_page_metadata(doc_id: str) -> Dict[str, Any]:
        """
        Retrieve page metadata for a document.

        Args:
            doc_id: Document identifier.

        Returns:
            Dictionary mapping page numbers (as strings) to metadata
            containing width, height, and rotation.

        Raises:
            HTTPException 404: If the metadata file does not exist.
            HTTPException 400: If the document ID contains path traversal.
        """
        # Guard against path traversal
        if ".." in doc_id or "/" in doc_id or "\\" in doc_id:
            raise HTTPException(status_code=400, detail="Invalid document ID")

        metadata_path = Path(f"/data/{doc_id}/page_metadata.json")
        if not metadata_path.exists():
            raise HTTPException(status_code=404, detail="Metadata not found")

        content = metadata_path.read_text(encoding="utf-8")
        return json.loads(content)  # type: ignore[no-any-return]

except ImportError:
    # FastAPI not available; provide a no-op placeholder so module can
    # still be imported in environments without FastAPI (e.g. tests).
    router = None  # type: ignore[assignment]
