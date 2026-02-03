"""
監査チェックモジュール
ページのSEO/品質問題を検出する
"""
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from app.db import models


class Auditor:
    """監査チェッカー"""
    
    # Issue Types
    HTTP_404 = "http_404"
    HTTP_5XX = "http_5xx"
    REDIRECT_CHAIN = "redirect_chain"
    MISSING_TITLE = "missing_title"
    MISSING_H1 = "missing_h1"
    MISSING_DESCRIPTION = "missing_description"
    MISSING_OGP = "missing_ogp"
    CANONICAL_MISMATCH = "canonical_mismatch"
    NOINDEX_DETECTED = "noindex_detected"
    DUPLICATE_CONTENT = "duplicate_content"
    
    def __init__(self, db: Session, job_id: str):
        self.db = db
        self.job_id = job_id
        self.findings: List[models.Finding] = []
    
    def check_page(self, page: models.Page, options: Dict[str, bool] = None) -> List[models.Finding]:
        """
        ページの監査チェックを実行
        options: {"check_ogp": True, "check_description": True} 等でON/OFF可能
        """
        options = options or {}
        check_ogp = options.get("check_ogp", True)
        check_description = options.get("check_description", True)
        
        findings = []
        metadata = page.metadata_info or {}
        
        # 1. HTTPステータスチェック
        if page.status_code == 404:
            findings.append(self._create_finding(
                page, "error", self.HTTP_404, 
                f"ページが404 Not Foundを返しました"
            ))
        elif page.status_code and page.status_code >= 500:
            findings.append(self._create_finding(
                page, "error", self.HTTP_5XX,
                f"サーバーエラー (HTTP {page.status_code})"
            ))
        
        # 2. リダイレクトチェーン
        redirect_chain = metadata.get("redirect_chain", [])
        if len(redirect_chain) > 1:
            findings.append(self._create_finding(
                page, "warning", self.REDIRECT_CHAIN,
                f"リダイレクトチェーン検出: {' -> '.join(redirect_chain)}"
            ))
        
        # 3. Titleチェック
        if not page.title or page.title.strip() == "":
            findings.append(self._create_finding(
                page, "warning", self.MISSING_TITLE,
                "titleタグがありません"
            ))
        
        # 4. H1チェック
        if not metadata.get("h1"):
            findings.append(self._create_finding(
                page, "warning", self.MISSING_H1,
                "h1タグがありません"
            ))
        
        # 5. Description チェック（オプション）
        if check_description and not metadata.get("description"):
            findings.append(self._create_finding(
                page, "info", self.MISSING_DESCRIPTION,
                "meta descriptionがありません"
            ))
        
        # 6. OGP チェック（オプション）
        if check_ogp:
            if not metadata.get("og_title") or not metadata.get("og_image"):
                missing = []
                if not metadata.get("og_title"):
                    missing.append("og:title")
                if not metadata.get("og_image"):
                    missing.append("og:image")
                findings.append(self._create_finding(
                    page, "info", self.MISSING_OGP,
                    f"OGPタグ欠落: {', '.join(missing)}"
                ))
        
        # 7. Canonical不整合
        canonical = metadata.get("canonical")
        if canonical and canonical != page.url:
            # 正規化して比較
            from app.core.parser import URLParser
            norm_canonical = URLParser.normalize_url(canonical)
            norm_url = URLParser.normalize_url(page.url)
            if norm_canonical != norm_url:
                findings.append(self._create_finding(
                    page, "warning", self.CANONICAL_MISMATCH,
                    f"Canonical URL不整合: {canonical}"
                ))
        
        # 8. noindex検出
        if metadata.get("noindex"):
            findings.append(self._create_finding(
                page, "info", self.NOINDEX_DETECTED,
                "noindexが設定されています"
            ))
        
        return findings
    
    def check_duplicates(self, pages: List[models.Page]) -> List[models.Finding]:
        """
        コンテンツ重複チェック（content_hashで判定）
        """
        findings = []
        hash_map: Dict[str, List[models.Page]] = {}
        
        for page in pages:
            if page.content_hash:
                if page.content_hash in hash_map:
                    hash_map[page.content_hash].append(page)
                else:
                    hash_map[page.content_hash] = [page]
        
        for content_hash, duplicates in hash_map.items():
            if len(duplicates) > 1:
                urls = [p.url for p in duplicates]
                for page in duplicates:
                    findings.append(self._create_finding(
                        page, "warning", self.DUPLICATE_CONTENT,
                        f"コンテンツ重複の可能性: {', '.join(urls)}"
                    ))
        
        return findings
    
    def save_findings(self, findings: List[models.Finding]):
        """Findingsをデータベースに保存"""
        for finding in findings:
            self.db.add(finding)
        self.db.commit()
    
    def _create_finding(self, page: models.Page, level: str, issue_type: str, message: str) -> models.Finding:
        """Finding オブジェクトを作成"""
        return models.Finding(
            job_id=self.job_id,
            page_id=page.id,
            level=level,
            issue_type=issue_type,
            message=message
        )
    
    @staticmethod
    def summarize_findings(findings: List[models.Finding]) -> Dict[str, Any]:
        """Findingsのサマリーを生成"""
        summary = {
            "total": len(findings),
            "errors": 0,
            "warnings": 0,
            "info": 0,
            "by_type": {}
        }
        
        for f in findings:
            if f.level == "error":
                summary["errors"] += 1
            elif f.level == "warning":
                summary["warnings"] += 1
            else:
                summary["info"] += 1
            
            if f.issue_type not in summary["by_type"]:
                summary["by_type"][f.issue_type] = 0
            summary["by_type"][f.issue_type] += 1
        
        return summary
