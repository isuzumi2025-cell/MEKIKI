from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime

# --- Profile Schemas ---
class ProfileBase(BaseModel):
    name: str
    target_url: Optional[str] = None
    max_pages: Optional[int] = 50
    max_depth: Optional[int] = 3
    max_time_seconds: Optional[int] = 1800
    concurrent_limit: Optional[int] = 3
    mode: Optional[str] = "render"
    auth_config: Optional[Dict[str, Any]] = {}
    allow_domains: Optional[List[str]] = []
    exclude_patterns: Optional[List[str]] = []
    keep_params: Optional[List[str]] = []
    respect_robots: Optional[bool] = True
    capture_sp: Optional[bool] = False

class ProfileCreate(ProfileBase):
    pass

class ProfileUpdate(BaseModel):
    """プロファイル更新用（部分更新対応）"""
    name: Optional[str] = None
    target_url: Optional[str] = None
    max_pages: Optional[int] = None
    max_depth: Optional[int] = None
    max_time_seconds: Optional[int] = None
    concurrent_limit: Optional[int] = None
    mode: Optional[str] = None
    auth_config: Optional[Dict[str, Any]] = None
    allow_domains: Optional[List[str]] = None
    exclude_patterns: Optional[List[str]] = None
    keep_params: Optional[List[str]] = None
    respect_robots: Optional[bool] = None
    capture_sp: Optional[bool] = None

class Profile(ProfileBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True

# --- Page & Link Schemas (Nested in Job) ---
class PageBase(BaseModel):
    url: str
    title: Optional[str] = None
    status_code: int
    depth: int
    screenshot_path: Optional[str] = None
    screenshot_sp_path: Optional[str] = None
    content_hash: Optional[str] = None
    metadata_info: Optional[Dict[str, Any]] = {}

class Page(PageBase):
    id: int
    crawled_at: datetime
    
    class Config:
        from_attributes = True

class LinkBase(BaseModel):
    source_page_id: int
    target_page_id: int
    type: str

class Link(LinkBase):
    id: int
    
    class Config:
        from_attributes = True

class FindingBase(BaseModel):
    page_id: Optional[int]
    level: str
    issue_type: str
    message: str

class Finding(FindingBase):
    id: int
    
    class Config:
        from_attributes = True

# --- Job Schemas ---
class JobBase(BaseModel):
    profile_id: int
    start_url: Optional[str] = None

class JobCreate(JobBase):
    overrides: Optional[Dict[str, Any]] = {}

class Job(JobBase):
    id: str
    status: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    pages_crawled: int
    result_summary: Optional[Dict[str, Any]] = {}

    class Config:
        from_attributes = True

class JobDetail(Job):
    pages: List[Page] = []
    links: List[Link] = []
    findings: List[Finding] = []

# --- Export Schemas ---
class ExportJSON(BaseModel):
    job_id: str
    start_url: str
    status: str
    pages_crawled: int
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    result_summary: Dict[str, Any] = {}
    nodes: List[Dict[str, Any]] = []
    edges: List[Dict[str, Any]] = []

class AuditSummary(BaseModel):
    total: int
    errors: int
    warnings: int
    info: int

class AuditReport(BaseModel):
    job_id: str
    generated_at: str
    summary: AuditSummary
    findings_by_type: Dict[str, List[Dict[str, Any]]]
