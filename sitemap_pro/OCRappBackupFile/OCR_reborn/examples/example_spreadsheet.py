"""
Googleスプレッドシート連携の例
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.engine_spreadsheet import SpreadsheetEngine


def main():
    """スプレッドシート連携のデモ"""
    
    # サンプルクラスタデータ
    clusters = [
        {
            "id": 1,
            "rect": [50, 50, 300, 150],
            "text": "タイトル: 商品A\n価格: ¥1,000\n在庫: あり"
        },
        {
            "id": 2,
            "rect": [50, 200, 300, 350],
            "text": "タイトル: 商品B\n価格: ¥2,000\n在庫: なし"
        },
        {
            "id": 3,
            "rect": [350, 50, 600, 150],
            "text": "カテゴリ: 電子機器\n評価: ★★★★☆"
        }
    ]
    
    print("📊 Googleスプレッドシート連携デモ")
    print("=" * 60)
    
    try:
        # スプレッドシートエンジン初期化
        sheet_engine = SpreadsheetEngine(
            credential_path="service_account.json"
        )
        
        # 既存のスプレッドシートに書き込む場合
        sheet_url = input("スプレッドシートのURL（空欄で新規作成）: ").strip()
        
        if not sheet_url:
            # 新規作成
            sheet_name = input("新規作成するシート名: ").strip() or "Test Sheet"
            user_email = input("共有するメールアドレス（オプション）: ").strip()
            
            url = sheet_engine.sync_clusters(
                clusters=clusters,
                sheet_identifier=sheet_name,
                worksheet_name="Data",
                create_if_not_exists=True,
                user_email=user_email or None
            )
        else:
            # 既存シートに書き込み
            url = sheet_engine.sync_clusters(
                clusters=clusters,
                sheet_identifier=sheet_url,
                worksheet_name="Data"
            )
        
        print("\n✅ 成功！")
        print(f"   URL: {url}")
        print("\nブラウザでスプレッドシートを開いて確認してください。")
        
    except FileNotFoundError as e:
        print(f"\n❌ エラー: {e}")
        print("\nservice_account.json ファイルをプロジェクトルートに配置してください。")
    except Exception as e:
        print(f"\n❌ エラー: {e}")


if __name__ == "__main__":
    main()

