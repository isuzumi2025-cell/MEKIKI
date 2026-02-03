"""
アプリケーションのエントリーポイント（python -m app で実行可能にする）
"""
import sys

# GUIモードかCLIモードかを判定
if len(sys.argv) > 1 and sys.argv[1] == "--gui":
    # GUIモード
    from app.gui import main
    main()
else:
    # CLIモード（デフォルト）
    from app.cli import cli
    if __name__ == "__main__":
        cli()
