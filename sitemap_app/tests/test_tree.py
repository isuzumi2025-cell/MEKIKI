"""
ツリー構築・監査ロジックテスト
"""
import pytest
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.auditor import Auditor
from app.core.interfaces import InMemoryQueue, QueueItem, MD5Hasher


class TestInMemoryQueue:
    """インメモリキューのテスト"""
    
    @pytest.mark.asyncio
    async def test_queue_operations(self):
        """基本的なキュー操作"""
        queue = InMemoryQueue()
        
        # 初期状態
        assert await queue.is_empty()
        assert await queue.size() == 0
        
        # エンキュー
        await queue.enqueue(QueueItem(url="https://example.com/1", depth=0))
        await queue.enqueue(QueueItem(url="https://example.com/2", depth=1))
        
        assert not await queue.is_empty()
        assert await queue.size() == 2
        
        # デキュー（FIFO）
        item1 = await queue.dequeue()
        assert item1.url == "https://example.com/1"
        assert item1.depth == 0
        
        item2 = await queue.dequeue()
        assert item2.url == "https://example.com/2"
        assert item2.depth == 1
        
        # 空になった
        assert await queue.is_empty()
        assert await queue.dequeue() is None
    
    @pytest.mark.asyncio
    async def test_parent_tracking(self):
        """親ID追跡"""
        queue = InMemoryQueue()
        
        await queue.enqueue(QueueItem(url="https://example.com/child", depth=1, parent_id=123))
        
        item = await queue.dequeue()
        assert item.parent_id == 123


class TestMD5Hasher:
    """コンテンツハッシュのテスト"""
    
    def test_same_content_same_hash(self):
        """同一コンテンツは同一ハッシュ"""
        hasher = MD5Hasher()
        
        html1 = "<html><body><p>Hello World</p></body></html>"
        html2 = "<html><body><p>Hello World</p></body></html>"
        
        assert hasher.compute(html1) == hasher.compute(html2)
    
    def test_different_content_different_hash(self):
        """異なるコンテンツは異なるハッシュ"""
        hasher = MD5Hasher()
        
        html1 = "<html><body><p>Hello World</p></body></html>"
        html2 = "<html><body><p>Goodbye World</p></body></html>"
        
        assert hasher.compute(html1) != hasher.compute(html2)
    
    def test_ignore_scripts_and_styles(self):
        """script/styleタグは無視"""
        hasher = MD5Hasher()
        
        html1 = "<html><body><p>Content</p></body></html>"
        html2 = """
        <html>
        <head><script>console.log('test');</script></head>
        <style>.class { color: red; }</style>
        <body><p>Content</p></body>
        </html>
        """
        
        assert hasher.compute(html1) == hasher.compute(html2)


class TestAuditorRules:
    """監査ルールのテスト（DBなしでのシンプルテスト）"""
    
    def test_issue_type_constants(self):
        """Issue Type定数"""
        assert Auditor.HTTP_404 == "http_404"
        assert Auditor.HTTP_5XX == "http_5xx"
        assert Auditor.MISSING_TITLE == "missing_title"
        assert Auditor.MISSING_H1 == "missing_h1"
        assert Auditor.MISSING_OGP == "missing_ogp"
        assert Auditor.CANONICAL_MISMATCH == "canonical_mismatch"
        assert Auditor.NOINDEX_DETECTED == "noindex_detected"
    
    def test_summarize_findings(self):
        """Findings サマリー生成"""
        # モックFindings
        class MockFinding:
            def __init__(self, level, issue_type):
                self.level = level
                self.issue_type = issue_type
        
        findings = [
            MockFinding("error", "http_404"),
            MockFinding("error", "http_404"),
            MockFinding("warning", "missing_title"),
            MockFinding("info", "noindex_detected"),
        ]
        
        summary = Auditor.summarize_findings(findings)
        
        assert summary["total"] == 4
        assert summary["errors"] == 2
        assert summary["warnings"] == 1
        assert summary["info"] == 1
        assert summary["by_type"]["http_404"] == 2
        assert summary["by_type"]["missing_title"] == 1


class TestTreeConstruction:
    """ツリー構築ロジックのテスト"""
    
    def test_bfs_order(self):
        """BFS順序（浅い階層優先）"""
        # シミュレーション：depth順にソートされるか
        items = [
            {"url": "/deep/path", "depth": 3},
            {"url": "/", "depth": 0},
            {"url": "/mid", "depth": 1},
            {"url": "/mid/child", "depth": 2},
        ]
        
        # BFSでは depth 順に処理される
        sorted_items = sorted(items, key=lambda x: x["depth"])
        
        assert sorted_items[0]["depth"] == 0
        assert sorted_items[1]["depth"] == 1
        assert sorted_items[2]["depth"] == 2
        assert sorted_items[3]["depth"] == 3
    
    def test_parent_child_relationship(self):
        """親子関係の追跡"""
        # BFSでの親子関係：最初に発見したリンク元が親
        pages = {}
        links = []
        
        # ルートページ
        pages["https://example.com"] = {"id": 1, "depth": 0, "parent_id": None}
        
        # 子ページ（ルートから発見）
        pages["https://example.com/about"] = {"id": 2, "depth": 1, "parent_id": 1}
        links.append({"source": 1, "target": 2})
        
        # 孫ページ（aboutから発見）
        pages["https://example.com/about/team"] = {"id": 3, "depth": 2, "parent_id": 2}
        links.append({"source": 2, "target": 3})
        
        # 親子関係の検証
        assert pages["https://example.com"]["parent_id"] is None
        assert pages["https://example.com/about"]["parent_id"] == 1
        assert pages["https://example.com/about/team"]["parent_id"] == 2
        
        # リンク数
        assert len(links) == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
