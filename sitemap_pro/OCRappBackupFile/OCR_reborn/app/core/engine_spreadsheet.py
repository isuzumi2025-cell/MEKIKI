"""
スプレッドシート同期エンジン
Google Spreadsheetsとの双方向同期機能
エリア情報の変更をリアルタイムに反映
"""

import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
from typing import List, Dict, Optional
import os


class SpreadsheetEngine:
    """
    Google Spreadsheetsとの同期を管理するクラス
    
    機能:
    - エリア情報の書き込み
    - 既存シートへの上書き
    - 新規シート作成
    - 権限共有
    - 差分更新（部分的な変更の反映）
    """
    
    def __init__(self, credential_path: str = "service_account.json"):
        """
        Args:
            credential_path: サービスアカウントJSONファイルパス
        """
        self.credential_path = credential_path
        self.client = None
        self._initialize_client()
    
    def _initialize_client(self):
        """gspreadクライアントの初期化"""
        if not os.path.exists(self.credential_path):
            raise FileNotFoundError(
                f"認証ファイルが見つかりません: {self.credential_path}\n"
                "Google Cloud Consoleでサービスアカウントを作成し、\n"
                "JSONキーをダウンロードしてください。"
            )
        
        scopes = [
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive'
        ]
        
        try:
            self.client = gspread.service_account(
                filename=self.credential_path,
                scopes=scopes
            )
            print(f"✅ Google Sheets認証成功")
        except Exception as e:
            raise RuntimeError(f"認証エラー: {e}")
    
    def sync_clusters(
        self,
        clusters: List[Dict],
        sheet_identifier: str,
        worksheet_name: str = "Sheet1",
        create_if_not_exists: bool = True,
        user_email: Optional[str] = None,
        folder_id: Optional[str] = None
    ) -> str:
        """
        クラスタ情報をスプレッドシートに同期
        
        Args:
            clusters: クラスタ情報のリスト
                [{
                    "id": int,
                    "rect": [x0, y0, x1, y1],
                    "text": str
                }, ...]
            sheet_identifier: スプレッドシートのURLまたは名前
            worksheet_name: ワークシート名
            create_if_not_exists: 存在しない場合に新規作成するか
            user_email: 共有するユーザーのメールアドレス
            folder_id: 新規作成時の保存先フォルダID
        
        Returns:
            スプレッドシートのURL
        """
        try:
            # スプレッドシートを開くか作成
            if sheet_identifier.startswith("https://"):
                # URLが渡された場合、既存シートを開く
                spreadsheet = self._open_by_url(sheet_identifier)
            else:
                # 名前が渡された場合
                spreadsheet = self._open_or_create(
                    sheet_identifier,
                    create_if_not_exists,
                    folder_id
                )
                
                # 新規作成した場合は権限共有
                if user_email:
                    self._share_with_user(spreadsheet, user_email)
            
            # ワークシート取得
            try:
                worksheet = spreadsheet.worksheet(worksheet_name)
            except gspread.WorksheetNotFound:
                worksheet = spreadsheet.add_worksheet(
                    title=worksheet_name,
                    rows=1000,
                    cols=20
                )
            
            # データ書き込み
            self._write_clusters(worksheet, clusters)
            
            print(f"✅ スプレッドシート同期完了: {spreadsheet.url}")
            return spreadsheet.url
            
        except Exception as e:
            raise RuntimeError(f"スプレッドシート同期エラー: {e}")
    
    def _open_by_url(self, url: str):
        """URLから既存スプレッドシートを開く"""
        try:
            return self.client.open_by_url(url)
        except gspread.SpreadsheetNotFound:
            raise FileNotFoundError(
                f"指定されたスプレッドシートが見つかりません。\n"
                f"URL: {url}\n"
                f"サービスアカウントに共有権限が付与されているか確認してください。"
            )
    
    def _open_or_create(
        self,
        name: str,
        create: bool,
        folder_id: Optional[str]
    ):
        """名前でスプレッドシートを開くか新規作成"""
        try:
            return self.client.open(name)
        except gspread.SpreadsheetNotFound:
            if not create:
                raise FileNotFoundError(f"スプレッドシート '{name}' が見つかりません")
            
            # 新規作成
            if folder_id:
                return self.client.create(name, folder_id=folder_id)
            else:
                return self.client.create(name)
    
    def _share_with_user(self, spreadsheet, email: str, role: str = 'writer'):
        """スプレッドシートをユーザーと共有"""
        try:
            spreadsheet.share(email, perm_type='user', role=role)
            print(f"🔓 {email} に{role}権限を付与しました")
        except Exception as e:
            print(f"⚠️  共有設定警告: {e}")
    
    def _write_clusters(self, worksheet, clusters: List[Dict]):
        """クラスタ情報をワークシートに書き込み"""
        # ヘッダー行
        header = [
            "Area ID",
            "Position (x0, y0, x1, y1)",
            "Extracted Text",
            "Human Verify",
            "Correction",
            "Status",
            "Timestamp"
        ]
        
        # データ行の構築
        rows = [header]
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        for cluster in clusters:
            area_id = f"Area {cluster.get('id', 0)}"
            rect = cluster.get('rect', [0, 0, 0, 0])
            position = f"({rect[0]}, {rect[1]}, {rect[2]}, {rect[3]})"
            text = cluster.get('text', '')
            
            rows.append([
                area_id,
                position,
                text,
                "",  # Human Verify (空欄)
                "",  # Correction (空欄)
                "Pending",  # Status
                now
            ])
        
        # 一括書き込み（高速化）
        worksheet.clear()
        worksheet.update(rows, value_input_option='RAW')
        
        # フォーマット適用
        self._apply_formatting(worksheet, len(rows))
    
    def _apply_formatting(self, worksheet, row_count: int):
        """ワークシートにフォーマットを適用"""
        try:
            # ヘッダー行のフォーマット
            worksheet.format('A1:G1', {
                "backgroundColor": {"red": 0.2, "green": 0.4, "blue": 0.6},
                "textFormat": {
                    "foregroundColor": {"red": 1, "green": 1, "blue": 1},
                    "fontSize": 11,
                    "bold": True
                },
                "horizontalAlignment": "CENTER"
            })
            
            # 列幅の調整
            worksheet.set_column_width(1, 100)   # Area ID
            worksheet.set_column_width(2, 200)   # Position
            worksheet.set_column_width(3, 400)   # Extracted Text
            worksheet.set_column_width(4, 100)   # Human Verify
            worksheet.set_column_width(5, 300)   # Correction
            worksheet.set_column_width(6, 100)   # Status
            worksheet.set_column_width(7, 150)   # Timestamp
            
            # データ行のフォーマット
            if row_count > 1:
                worksheet.format(f'A2:G{row_count}', {
                    "textFormat": {"fontSize": 10},
                    "wrapStrategy": "WRAP"
                })
            
        except Exception as e:
            print(f"⚠️  フォーマット適用警告: {e}")
    
    def update_cluster(
        self,
        sheet_url: str,
        area_id: int,
        new_text: str = None,
        new_rect: List[int] = None,
        worksheet_name: str = "Sheet1"
    ):
        """
        特定エリアの情報を更新（差分更新）
        
        Args:
            sheet_url: スプレッドシートURL
            area_id: エリアID
            new_text: 新しいテキスト（指定した場合のみ更新）
            new_rect: 新しい座標 [x0, y0, x1, y1]（指定した場合のみ更新）
            worksheet_name: ワークシート名
        """
        try:
            spreadsheet = self.client.open_by_url(sheet_url)
            worksheet = spreadsheet.worksheet(worksheet_name)
            
            # Area IDで該当行を検索
            cell = worksheet.find(f"Area {area_id}")
            if not cell:
                raise ValueError(f"Area {area_id} が見つかりません")
            
            row = cell.row
            
            # テキストの更新（C列）
            if new_text is not None:
                worksheet.update_cell(row, 3, new_text)
            
            # 座標の更新（B列）
            if new_rect is not None:
                position = f"({new_rect[0]}, {new_rect[1]}, {new_rect[2]}, {new_rect[3]})"
                worksheet.update_cell(row, 2, position)
            
            # タイムスタンプの更新（G列）
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            worksheet.update_cell(row, 7, now)
            
            print(f"✅ Area {area_id} を更新しました")
            
        except Exception as e:
            raise RuntimeError(f"更新エラー: {e}")
    
    def read_clusters_from_sheet(
        self,
        sheet_url: str,
        worksheet_name: str = "Sheet1"
    ) -> List[Dict]:
        """
        スプレッドシートからクラスタ情報を読み込む
        （編集されたデータを取得）
        
        Returns:
            クラスタ情報のリスト
        """
        try:
            spreadsheet = self.client.open_by_url(sheet_url)
            worksheet = spreadsheet.worksheet(worksheet_name)
            
            # 全データ取得（ヘッダー除く）
            records = worksheet.get_all_records()
            
            clusters = []
            for record in records:
                # Area IDから番号を抽出
                area_id_str = record.get('Area ID', '')
                area_id = int(area_id_str.replace('Area ', '')) if area_id_str else 0
                
                # Position文字列から座標を抽出
                position_str = record.get('Position (x0, y0, x1, y1)', '')
                rect = self._parse_position(position_str)
                
                # テキスト（Correction優先、なければExtracted Text）
                text = record.get('Correction', '') or record.get('Extracted Text', '')
                
                clusters.append({
                    "id": area_id,
                    "rect": rect,
                    "text": text,
                    "status": record.get('Status', ''),
                    "human_verify": record.get('Human Verify', '')
                })
            
            return clusters
            
        except Exception as e:
            raise RuntimeError(f"読み込みエラー: {e}")
    
    @staticmethod
    def _parse_position(position_str: str) -> List[int]:
        """Position文字列を座標リストに変換"""
        try:
            # "(100, 200, 300, 400)" -> [100, 200, 300, 400]
            nums = position_str.strip('()').split(',')
            return [int(n.strip()) for n in nums]
        except:
            return [0, 0, 0, 0]
    
    @staticmethod
    def extract_folder_id(folder_url: str) -> Optional[str]:
        """
        Google DriveのフォルダURLからフォルダIDを抽出
        
        Args:
            folder_url: https://drive.google.com/drive/folders/XXXXX 形式
        
        Returns:
            フォルダID（XXXXXの部分）
        """
        if "folders/" in folder_url:
            return folder_url.split("folders/")[-1].split("?")[0]
        return None

