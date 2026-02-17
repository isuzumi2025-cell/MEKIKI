"""
基本的な使用例
WebページとPDFの比較を自動化
"""

import sys
from pathlib import Path

# プロジェクトルートをパスに追加
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.crawler import WebCrawler
from app.core.pdf_loader import PDFLoader
from app.core.engine_clustering import ClusteringEngine
from app.core.comparator import Comparator


def main():
    """基本的な比較フロー"""
    
    # 1. Webクローリング
    print("=" * 60)
    print("1. Webページのスクリーンショット撮影")
    print("=" * 60)
    
    crawler = WebCrawler()
    web_result = crawler.crawl(
        url="https://example.com",
        output_path="temp_web.png",
        wait_time=2,
        full_page=True
    )
    
    if not web_result["success"]:
        print(f"エラー: {web_result['error']}")
        return
    
    print(f"✅ Web画像を取得: {web_result['title']}")
    
    # 2. PDF読み込み
    print("\n" + "=" * 60)
    print("2. PDFの高解像度画像化")
    print("=" * 60)
    
    pdf_loader = PDFLoader(dpi=300)
    pdf_images = pdf_loader.load("example.pdf", page_numbers=[1])
    
    if not pdf_images:
        print("エラー: PDFの読み込みに失敗")
        return
    
    print(f"✅ PDF画像を取得: {len(pdf_images)} ページ")
    
    # 3. クラスタリング（デモ用ダミーデータ）
    print("\n" + "=" * 60)
    print("3. 領域検出（クラスタリング）")
    print("=" * 60)
    
    # 実際にはGoogle Cloud Vision APIを使用
    # ここではダミーデータ
    web_clusters = [
        {"id": 1, "rect": [50, 50, 300, 150], "text": "サンプルテキスト1"},
        {"id": 2, "rect": [50, 200, 400, 300], "text": "サンプルテキスト2"}
    ]
    
    pdf_clusters = [
        {"id": 1, "rect": [50, 50, 300, 150], "text": "サンプルテキスト1"},
        {"id": 2, "rect": [50, 200, 400, 300], "text": "サンプルテキスト2（修正版）"}
    ]
    
    print(f"✅ Web: {len(web_clusters)} エリア検出")
    print(f"✅ PDF: {len(pdf_clusters)} エリア検出")
    
    # 4. 比較実行
    print("\n" + "=" * 60)
    print("4. Web vs PDF 比較")
    print("=" * 60)
    
    comparator = Comparator()
    comparator.set_data(web_clusters, pdf_clusters)
    results = comparator.compare_all()
    
    # 5. サマリー表示
    summary = comparator.get_summary()
    
    print(f"\n📊 比較サマリー")
    print(f"  総数: {summary['total']}")
    print(f"  ✅ 一致: {summary['match']}")
    print(f"  ⚠️ 不一致: {summary['mismatch']}")
    print(f"  🌐 Web専用: {summary['web_only']}")
    print(f"  📄 PDF専用: {summary['pdf_only']}")
    print(f"  平均類似度: {summary['average_similarity']:.2%}")
    
    # 6. 詳細表示
    print(f"\n📝 詳細結果")
    for result in results:
        status_icon = {
            "match": "✅",
            "mismatch": "⚠️",
            "web_only": "🌐",
            "pdf_only": "📄"
        }.get(result["status"], "❓")
        
        print(f"\n{status_icon} Area {result['area_id']} - {result['status'].upper()}")
        print(f"   類似度: {result['similarity']:.2%}")
        if result["web_text"]:
            print(f"   Web: {result['web_text'][:50]}...")
        if result["pdf_text"]:
            print(f"   PDF: {result['pdf_text'][:50]}...")
    
    # 7. エクスポート
    print("\n" + "=" * 60)
    print("5. レポート出力")
    print("=" * 60)
    
    comparator.export_to_csv("comparison_result.csv")
    comparator.export_to_html("comparison_result.html")
    
    print("\n✅ 完了！")


if __name__ == "__main__":
    main()

