"""
CLIエントリーポイント
"""
import click
from pathlib import Path


@click.group()
@click.version_option(version="0.1.0")
def cli():
    """OCR Scanner - 日本語文言抽出ツール"""
    pass


@cli.command()
def gui():
    """GUIアプリケーションを起動"""
    from app.gui import main
    main()


@cli.command()
@click.option("--input", "-i", required=True, type=click.Path(exists=True), help="入力ファイルまたはディレクトリ")
@click.option("--client", "-c", required=True, help="クライアント名")
@click.option("--campaign", "-p", required=True, help="キャンペーン名")
@click.option("--month", "-m", help="月（YYYY-MM形式）")
@click.option("--preprocess-lines", type=click.Choice(["on", "off"]), default="on", help="線マスク処理")
@click.option("--debug", type=click.Choice(["on", "off"]), default="off", help="デバッグモード")
def ingest(input, client, campaign, month, preprocess_lines, debug):
    """画像/PDFを取り込んでOCR処理を実行"""
    from pathlib import Path
    from app.ingest import ingest_file
    
    input_path = Path(input)
    preprocess_lines_bool = preprocess_lines == "on"
    debug_bool = debug == "on"
    
    click.echo(f"取り込み処理を開始: {input}")
    click.echo(f"クライアント: {client}, キャンペーン: {campaign}")
    click.echo(f"月: {month or '未指定'}")
    
    result = ingest_file(
        input_path=input_path,
        client=client,
        campaign=campaign,
        month=month,
        preprocess_lines=preprocess_lines_bool,
        debug=debug_bool,
    )
    
    if result["status"] == "success":
        click.echo(f"✓ 処理完了: {result['normalized_json']}")
        click.echo(f"  処理ページ数: {result['pages_processed']}")
    else:
        click.echo(f"✗ エラー: {result.get('message', '不明なエラー')}", err=True)
        raise click.Abort()


@cli.command()
@click.option("--connector", "-n", required=True, help="コネクタ名")
@click.option("--client", "-c", required=True, help="クライアント名")
@click.option("--campaign", "-p", required=True, help="キャンペーン名")
@click.option("--month", "-m", help="月（YYYY-MM形式）")
def fetch_web(connector, client, campaign, month):
    """Webページを取得してOCR処理を実行（Phase 3）"""
    click.echo(f"Web取得: コネクタ={connector}")
    click.echo(f"クライアント: {client}, キャンペーン: {campaign}")
    click.echo(f"月: {month or '未指定'}")
    # TODO: Phase 3で実装
    click.echo("Phase 3の実装が必要です")


if __name__ == "__main__":
    cli()
