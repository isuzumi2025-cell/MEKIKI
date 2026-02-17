# Phase 0: プロジェクト初期化

## 目的

プロジェクトの骨格を作成し、仕様書と設定ファイルの雛形を整備する。

## 実行手順

1. 仕様書を `docs/requirements.md` に反映（SSOT化）
2. Phase別ドキュメントを作成
3. 設定ファイルの雛形を作成
4. Pythonプロジェクトの最小骨格を作成
5. 環境変数の雛形を作成

## 設計方針

### ディレクトリ構造

```
/
├── app/                    # メインアプリケーション
│   ├── __init__.py
│   ├── cli.py             # CLIエントリーポイント
│   ├── ingest.py           # Phase 1: 取り込み処理
│   ├── ocr/                # OCR関連
│   ├── pipeline/            # パイプライン処理
│   ├── japanese/            # 日本語チェック
│   └── utils/               # ユーティリティ
├── configs/                 # 設定ファイル
│   ├── pipeline.yaml.example
│   └── connectors.yaml.example
├── docs/                    # ドキュメント
│   ├── requirements.md
│   └── phases/
├── tests/                   # テスト
│   ├── __init__.py
│   ├── test_ingest.py
│   └── assets/              # テスト用サンプル
├── library/                 # 出力先（.gitignore）
├── .env.example
├── .gitignore
├── pyproject.toml           # または setup.py
├── requirements.txt
└── README.md
```

### 設計原則

1. **モジュール化**: 各Phaseが独立して拡張可能
2. **設定外部化**: ハードコードを避け、YAML/環境変数で管理
3. **再現性**: 乱数シード固定、ソート規則固定
4. **監査性**: すべての中間成果物を保存

## 制約

* Phase 1まではWeb取得機能は実装しない
* Phase 2までは比較機能は実装しない
* 各Phaseは独立してテスト可能

## 受入基準

- [x] `docs/requirements.md` が存在し、仕様が明確
- [x] `docs/phases/phase-0.md`, `phase-1.md` が存在
- [x] `configs/pipeline.yaml.example`, `connectors.yaml.example` が存在
- [x] Pythonプロジェクトとして `python -m app --help` が動作
- [x] `tests/` ディレクトリが存在し、テスト実行可能
- [x] `.env.example` が存在し、必要な環境変数が列挙されている

## 完了後のチェックリスト

Phase 1へ進む前に以下を確認：

- [ ] プロジェクト構造が整っている
- [ ] 依存関係が `requirements.txt` に記載されている
- [ ] CLIの骨格が動作する
- [ ] テスト環境が整っている
- [ ] 設定ファイルの雛形が用意されている
