"""
バッチ処理の例
複数のURLを一括で処理
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.crawler import WebCrawler, URLManager
from app.utils.helpers import create_output_directory, save_clusters_to_json


def main():
    """複数URLの一括処理"""
    
    # URLリストの準備
    urls = [
        "https://example.com/page1",
        "https://example.com/page2",
        "https://example.com/page3",
    ]
    
    # または、ファイルから読み込み
    # urls = URLManager.load_from_file("urls.txt")
    
    # 出力ディレクトリ作成
    output_dir = create_output_directory("batch_output")
    
    # クローラー初期化
    crawler = WebCrawler()
    
    # 一括クロール
    print("🚀 バッチ処理開始")
    print(f"   対象URL数: {len(urls)}")
    print(f"   出力先: {output_dir}")
    print()
    
    results = crawler.crawl_multiple(
        urls=urls,
        output_dir=str(output_dir),
        username=None,  # Basic認証が必要な場合は指定
        password=None,
        wait_time=2,
        full_page=True,
        headless=True
    )
    
    # 結果のサマリー
    success_count = sum(1 for r in results if r["success"])
    
    print("\n" + "=" * 60)
    print("📊 バッチ処理完了")
    print("=" * 60)
    print(f"  成功: {success_count} / {len(urls)}")
    print(f"  失敗: {len(urls) - success_count}")
    
    # 失敗したURLを表示
    failed_urls = [r["url"] for r in results if not r["success"]]
    if failed_urls:
        print("\n⚠️ 失敗したURL:")
        for url in failed_urls:
            print(f"  - {url}")


if __name__ == "__main__":
    main()

