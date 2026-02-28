"""
Vault Router — /api/v1/vault

Provides full-text search and node browsing over the ObsidianVault markdown
knowledge base located at the workspace root.

Endpoints
---------
GET /search          — full-text search across vault notes
GET /nodes           — list all vault notes
GET /nodes/{path}    — read the raw content of a note
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import List, Optional
from urllib.parse import unquote

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel

# ---------------------------------------------------------------------------
# Vault root — sibling of the backend directory
# ---------------------------------------------------------------------------
_VAULT_ROOT = Path(__file__).parents[5] / "ObsidianVault"


def _vault_root() -> Path:
    resolved = _VAULT_ROOT.resolve()
    return resolved


router = APIRouter(prefix="/vault", tags=["vault"])

# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class VaultSearchResult(BaseModel):
    title: str
    excerpt: str
    path: str
    tags: List[str]


class VaultNode(BaseModel):
    title: str
    path: str
    size: int
    tags: List[str]


class VaultNodeContent(BaseModel):
    title: str
    path: str
    content: str
    tags: List[str]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_TAG_RE = re.compile(r"#([A-Za-z0-9_\-/]+)")
_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
_FRONTMATTER_TAGS_RE = re.compile(r"^tags:\s*\[([^\]]+)\]", re.MULTILINE)
_FRONTMATTER_TAGS_LIST_RE = re.compile(r"^tags:\s*\n((?:\s+-\s+\S+\n?)+)", re.MULTILINE)


def _extract_tags(content: str) -> List[str]:
    """Extract tags from frontmatter and inline #hashtags."""
    tags: List[str] = []

    # Frontmatter tags: [] style
    m = _FRONTMATTER_TAGS_RE.search(content)
    if m:
        tags.extend(t.strip().strip('"').strip("'") for t in m.group(1).split(","))

    # Frontmatter tags: list style
    m2 = _FRONTMATTER_TAGS_LIST_RE.search(content)
    if m2:
        tags.extend(
            line.strip().lstrip("- ").strip()
            for line in m2.group(1).splitlines()
            if line.strip()
        )

    # Inline #hashtags (outside frontmatter)
    body = _FRONTMATTER_RE.sub("", content, count=1)
    tags.extend(_TAG_RE.findall(body))

    # Deduplicate while preserving order
    seen: set = set()
    result: List[str] = []
    for t in tags:
        if t and t not in seen:
            seen.add(t)
            result.append(t)
    return result


def _excerpt(content: str, query: str, window: int = 200) -> str:
    """Return a short excerpt centred around the first match of query."""
    body = _FRONTMATTER_RE.sub("", content, count=1).strip()
    lower_body = body.lower()
    idx = lower_body.find(query.lower())
    if idx == -1:
        return body[:window].replace("\n", " ").strip()
    start = max(0, idx - window // 2)
    end = min(len(body), idx + window // 2)
    snippet = body[start:end].replace("\n", " ").strip()
    if start > 0:
        snippet = "…" + snippet
    if end < len(body):
        snippet = snippet + "…"
    return snippet


def _all_markdown_files() -> List[Path]:
    """Return all .md files under the vault root, sorted by path."""
    vault = _vault_root()
    if not vault.exists():
        return []
    return sorted(vault.rglob("*.md"))


def _relative_path(p: Path) -> str:
    vault = _vault_root()
    try:
        return p.relative_to(vault).as_posix()
    except ValueError:
        return p.as_posix()


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get(
    "/search",
    response_model=List[VaultSearchResult],
    summary="Full-text search across ObsidianVault notes",
)
def search_vault(
    q: str = Query(..., min_length=1, description="Search query string"),
    limit: int = Query(20, ge=1, le=200, description="Maximum number of results"),
) -> List[VaultSearchResult]:
    """Search markdown files in the ObsidianVault directory for the given
    query string.  Matching is case-insensitive and looks at the full file
    content.

    Returns up to *limit* results ordered by filename.
    """
    vault = _vault_root()
    if not vault.exists():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"ObsidianVault not found at {vault}.",
        )

    results: List[VaultSearchResult] = []
    query_lower = q.lower()

    for md_file in _all_markdown_files():
        try:
            content = md_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        if query_lower not in content.lower():
            continue

        results.append(
            VaultSearchResult(
                title=md_file.stem,
                excerpt=_excerpt(content, q),
                path=_relative_path(md_file),
                tags=_extract_tags(content),
            )
        )

        if len(results) >= limit:
            break

    return results


@router.get(
    "/nodes",
    response_model=List[VaultNode],
    summary="List all notes in the ObsidianVault",
)
def list_nodes(
    limit: int = Query(500, ge=1, le=2000, description="Maximum nodes to return"),
) -> List[VaultNode]:
    """Return metadata for all markdown files in the vault.

    Does not read full file content; returns title, path, size, and tags
    extracted from the first 4 KB of each file for performance.
    """
    vault = _vault_root()
    if not vault.exists():
        return []

    nodes: List[VaultNode] = []
    for md_file in _all_markdown_files():
        try:
            stat = md_file.stat()
            # Read only enough for tags
            content_head = md_file.read_text(encoding="utf-8", errors="replace")[:4096]
        except OSError:
            continue

        nodes.append(
            VaultNode(
                title=md_file.stem,
                path=_relative_path(md_file),
                size=stat.st_size,
                tags=_extract_tags(content_head),
            )
        )

        if len(nodes) >= limit:
            break

    return nodes


@router.get(
    "/nodes/{path:path}",
    response_model=VaultNodeContent,
    summary="Read the raw content of a vault note",
)
def get_node(path: str) -> VaultNodeContent:
    """Return the full markdown content of the note at the given vault-relative
    path (e.g. ``90_System/Orchestra_Phase0_Progress_2026-02-08.md``).

    Path traversal outside the vault root is rejected with 403.
    """
    # Decode URL encoding (%20 etc.)
    decoded = unquote(path)
    vault = _vault_root()
    target = (vault / decoded).resolve()

    # Security: prevent path traversal
    try:
        target.relative_to(vault.resolve())
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Path traversal outside vault root is not permitted.",
        )

    if not target.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Note '{decoded}' not found in vault.",
        )

    if not target.is_file():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"'{decoded}' is a directory, not a note.",
        )

    try:
        content = target.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Cannot read note: {exc}",
        ) from exc

    return VaultNodeContent(
        title=target.stem,
        path=_relative_path(target),
        content=content,
        tags=_extract_tags(content),
    )
