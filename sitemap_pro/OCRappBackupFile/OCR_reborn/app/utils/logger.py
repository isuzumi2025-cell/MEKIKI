"""
ロギングユーティリティ
"""

import logging
from datetime import datetime
from pathlib import Path


def setup_logger(name: str, log_file: str = None, level=logging.INFO):
    """
    ロガーをセットアップ
    
    Args:
        name: ロガー名
        log_file: ログファイルパス（オプション）
        level: ログレベル
    
    Returns:
        logger オブジェクト
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # フォーマッター
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # コンソールハンドラ
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # ファイルハンドラ（オプション）
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    return logger


# デフォルトロガー
default_logger = setup_logger(
    'web_pdf_verification',
    log_file=f'logs/app_{datetime.now():%Y%m%d}.log'
)

