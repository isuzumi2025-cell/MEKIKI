"""
URL正規化テスト
"""
import pytest
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.parser import URLParser


class TestURLNormalization:
    """URL正規化のテスト"""
    
    def test_basic_normalization(self):
        """基本的な正規化"""
        # ルートURLは / が維持される
        assert URLParser.normalize_url("https://example.com/") == "https://example.com/"
        assert URLParser.normalize_url("https://example.com") == "https://example.com/"
        assert URLParser.normalize_url("https://EXAMPLE.COM/") == "https://example.com/"
    
    def test_www_removal(self):
        """www. プレフィックス除去"""
        assert URLParser.normalize_url("https://www.example.com/page") == "https://example.com/page"
        assert URLParser.normalize_url("https://WWW.EXAMPLE.COM/") == "https://example.com/"
    
    def test_trailing_slash_removal(self):
        """末尾スラッシュ除去"""
        assert URLParser.normalize_url("https://example.com/page/") == "https://example.com/page"
        assert URLParser.normalize_url("https://example.com/a/b/c/") == "https://example.com/a/b/c"
        # ルートは / を維持
        assert URLParser.normalize_url("https://example.com/") == "https://example.com/"
    
    def test_fragment_removal(self):
        """フラグメント除去"""
        assert URLParser.normalize_url("https://example.com/page#section") == "https://example.com/page"
        assert URLParser.normalize_url("https://example.com/#top") == "https://example.com/"
    
    def test_tracking_params_removal(self):
        """トラッキングパラメータ除去"""
        # utm_* 系
        result = URLParser.normalize_url(
            "https://example.com/page?utm_source=google&utm_medium=cpc&id=123"
        )
        assert "utm_source" not in result
        assert "utm_medium" not in result
        assert "id=123" in result
        
        # gclid, fbclid
        result = URLParser.normalize_url(
            "https://example.com/page?gclid=abc123&fbclid=xyz789&product=456"
        )
        assert "gclid" not in result
        assert "fbclid" not in result
        assert "product=456" in result
    
    def test_keep_params(self):
        """パラメータ保持オプション"""
        # 通常は除去される utm_source を保持
        result = URLParser.normalize_url(
            "https://example.com/page?utm_source=special&id=1",
            keep_params=["utm_source"]
        )
        assert "utm_source=special" in result
        assert "id=1" in result
    
    def test_relative_url_resolution(self):
        """相対URL解決"""
        base = "https://example.com/dir/page.html"
        
        assert URLParser.normalize_url("/other", base) == "https://example.com/other"
        assert URLParser.normalize_url("../sibling", base) == "https://example.com/sibling"
        assert URLParser.normalize_url("child", base) == "https://example.com/dir/child"
    
    def test_non_http_urls(self):
        """非HTTPスキーム"""
        assert URLParser.normalize_url("javascript:void(0)") == ""
        assert URLParser.normalize_url("mailto:test@example.com") == ""
        assert URLParser.normalize_url("tel:+81-3-1234-5678") == ""


class TestLinkExtraction:
    """リンク抽出テスト"""
    
    def test_extract_links(self):
        """基本的なリンク抽出"""
        html = """
        <html>
        <body>
            <a href="/page1">Page 1</a>
            <a href="https://example.com/page2">Page 2</a>
            <a href="relative/page3">Page 3</a>
        </body>
        </html>
        """
        base = "https://example.com/"
        links = URLParser.extract_links(html, base)
        
        assert len(links) == 3
        assert "https://example.com/page1" in links
        assert "https://example.com/page2" in links
        assert "https://example.com/relative/page3" in links
    
    def test_skip_invalid_links(self):
        """無効なリンクのスキップ"""
        html = """
        <html>
        <body>
            <a href="javascript:alert('test')">JS</a>
            <a href="mailto:test@example.com">Email</a>
            <a href="tel:123">Phone</a>
            <a href="#section">Anchor</a>
            <a href="/valid">Valid</a>
        </body>
        </html>
        """
        base = "https://example.com/"
        links = URLParser.extract_links(html, base)
        
        assert len(links) == 1
        assert "https://example.com/valid" in links
    
    def test_deduplicate_links(self):
        """重複リンクの除去"""
        html = """
        <html>
        <body>
            <a href="/page">Link 1</a>
            <a href="/page/">Link 2</a>
            <a href="/page">Link 3</a>
        </body>
        </html>
        """
        base = "https://example.com/"
        links = URLParser.extract_links(html, base)
        
        # 正規化により同一URLは1つに（/page と /page/ は同一）
        # 注: パスは大文字小文字を区別する
        assert len(links) == 1


class TestInternalLinkCheck:
    """内部リンク判定テスト"""
    
    def test_same_domain(self):
        """同一ドメイン"""
        assert URLParser.is_internal_link("https://example.com/page", "example.com")
        assert URLParser.is_internal_link("https://www.example.com/page", "example.com")
    
    def test_subdomain(self):
        """サブドメイン"""
        assert URLParser.is_internal_link("https://sub.example.com/page", "example.com")
        assert URLParser.is_internal_link("https://a.b.example.com/page", "example.com")
    
    def test_external_domain(self):
        """外部ドメイン"""
        assert not URLParser.is_internal_link("https://other.com/page", "example.com")
        assert not URLParser.is_internal_link("https://example.org/page", "example.com")
    
    def test_allow_domains(self):
        """許可ドメイン"""
        allowed = ["partner.com", "cdn.example.net"]
        assert URLParser.is_internal_link("https://partner.com/page", "example.com", allowed)
        assert URLParser.is_internal_link("https://cdn.example.net/file", "example.com", allowed)
        assert not URLParser.is_internal_link("https://other.com/page", "example.com", allowed)


class TestMetadataExtraction:
    """メタデータ抽出テスト"""
    
    def test_extract_all_metadata(self):
        """全メタデータ抽出"""
        html = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Test Page</title>
            <meta name="description" content="This is a test page">
            <meta name="robots" content="noindex, nofollow">
            <link rel="canonical" href="https://example.com/canonical">
            <meta property="og:title" content="OG Title">
            <meta property="og:description" content="OG Description">
            <meta property="og:image" content="https://example.com/og.jpg">
        </head>
        <body>
            <h1>Main Heading</h1>
        </body>
        </html>
        """
        
        metadata = URLParser.extract_metadata(html)
        
        assert metadata["h1"] == "Main Heading"
        assert metadata["description"] == "This is a test page"
        assert metadata["canonical"] == "https://example.com/canonical"
        assert metadata["og_title"] == "OG Title"
        assert metadata["og_description"] == "OG Description"
        assert metadata["og_image"] == "https://example.com/og.jpg"
        assert metadata["noindex"] == True
        assert metadata["nofollow"] == True
    
    def test_missing_metadata(self):
        """メタデータ欠落時"""
        html = "<html><head><title>Title</title></head><body></body></html>"
        
        metadata = URLParser.extract_metadata(html)
        
        assert metadata["h1"] is None
        assert metadata["description"] is None
        assert metadata["canonical"] is None
        assert metadata["noindex"] == False


class TestExcludePatterns:
    """除外パターンテスト"""
    
    def test_wildcard_matching(self):
        """ワイルドカードマッチ"""
        patterns = ["/admin/*", "/login"]
        
        assert URLParser.matches_exclude_pattern("https://example.com/admin/users", patterns)
        assert URLParser.matches_exclude_pattern("https://example.com/admin/settings", patterns)
        assert URLParser.matches_exclude_pattern("https://example.com/login", patterns)
        assert not URLParser.matches_exclude_pattern("https://example.com/page", patterns)
    
    def test_complex_patterns(self):
        """複雑なパターン"""
        patterns = ["*/api/*", "*_old*"]
        
        assert URLParser.matches_exclude_pattern("https://example.com/v1/api/users", patterns)
        assert URLParser.matches_exclude_pattern("https://example.com/page_old_version", patterns)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
