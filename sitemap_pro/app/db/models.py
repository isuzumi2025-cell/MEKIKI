from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, JSON, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
from .database import Base

class Profile(Base):
    __tablename__ = "profiles"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    target_url = Column(String)
    max_pages = Column(Integer, default=50)
    max_depth = Column(Integer, default=3)
    max_time_seconds = Column(Integer, default=1800)  # 30分
    concurrent_limit = Column(Integer, default=3)
    mode = Column(String, default="render")  # 'render' or 'fast'
    auth_config = Column(JSON, default={})
    allow_domains = Column(JSON, default=[])
    exclude_patterns = Column(JSON, default=[])
    keep_params = Column(JSON, default=[])  # パラメータ除外の例外
    respect_robots = Column(Boolean, default=True)
    capture_sp = Column(Boolean, default=False)  # SP版スクショ
    created_at = Column(DateTime, default=datetime.utcnow)

    jobs = relationship("Job", back_populates="profile")


class Job(Base):
    __tablename__ = "jobs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    profile_id = Column(Integer, ForeignKey("profiles.id"))
    status = Column(String, default="pending")  # pending, running, completed, failed, stopped, paused
    start_url = Column(String)
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    pages_crawled = Column(Integer, default=0)
    result_summary = Column(JSON, default={})

    profile = relationship("Profile", back_populates="jobs")
    pages = relationship("Page", back_populates="job", cascade="all, delete-orphan")
    links = relationship("Link", back_populates="job", cascade="all, delete-orphan")
    findings = relationship("Finding", back_populates="job", cascade="all, delete-orphan")


class Page(Base):
    __tablename__ = "pages"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(String, ForeignKey("jobs.id"))
    url = Column(String, index=True)
    title = Column(String, nullable=True)
    status_code = Column(Integer)
    depth = Column(Integer)
    screenshot_path = Column(String, nullable=True)
    screenshot_sp_path = Column(String, nullable=True)  # SP版
    content_hash = Column(String, nullable=True)
    metadata_info = Column(JSON, default={})
    crawled_at = Column(DateTime, default=datetime.utcnow)

    job = relationship("Job", back_populates="pages")


class Link(Base):
    __tablename__ = "links"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(String, ForeignKey("jobs.id"))
    source_page_id = Column(Integer, ForeignKey("pages.id"))
    target_page_id = Column(Integer, ForeignKey("pages.id"))
    type = Column(String, default="internal")  # internal, external, resource

    job = relationship("Job", back_populates="links")
    source_page = relationship("Page", foreign_keys=[source_page_id])
    target_page = relationship("Page", foreign_keys=[target_page_id])


class Finding(Base):
    __tablename__ = "findings"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(String, ForeignKey("jobs.id"))
    page_id = Column(Integer, ForeignKey("pages.id"), nullable=True)
    level = Column(String)  # error, warning, info
    issue_type = Column(String)  # http_404, missing_title, etc.
    message = Column(String)

    job = relationship("Job", back_populates="findings")
    page = relationship("Page", back_populates="findings")
    
Page.findings = relationship("Finding", back_populates="page")


class ExcludedLink(Base):
    """除外されたリンク（PDF、画像等）の記録"""
    __tablename__ = "excluded_links"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(String, ForeignKey("jobs.id"))
    url = Column(String)
    source_url = Column(String, nullable=True)  # どのページから発見されたか
    extension = Column(String)  # 除外理由となった拡張子
    excluded_at = Column(DateTime, default=datetime.utcnow)

    job = relationship("Job", back_populates="excluded_links")

# Job に excluded_links リレーションを追加
Job.excluded_links = relationship("ExcludedLink", back_populates="job", cascade="all, delete-orphan")
