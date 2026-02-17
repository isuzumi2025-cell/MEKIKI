import click
import os
import sys
from dotenv import load_dotenv
from app.utils.file_loader import FileLoader
from app.core.preprocessor import ImagePreprocessor
from app.core.engine_local import LocalOCREngine
from app.core.engine_cloud import CloudOCREngine

# .envファイルの読み込み
load_dotenv()

# Windowsでの文字化け対策
if sys.platform.startswith('win'):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

@click.command()
@click.argument('input_path', type=click.Path(exists=True))
@click.option('--engine', '-e', type=click.Choice(['local', 'cloud']), default='local', help='OCRエンジンを選択')
@click.option('--output', '-o', type=click.Path(), help='出力ファイルパス')
def main(input_path, engine, output):
    """日本語OCR実行ツール"""
    click.echo(f"🚀 開始: {input_path} (Engine: {engine})")

    try:
        # エンジン初期化
        if engine == 'cloud':
            ocr_engine = CloudOCREngine()
        else:
            ocr_engine = LocalOCREngine()

        # 画像読み込み
        images = FileLoader.load_file(input_path)
        click.echo(f"📄 {len(images)} 枚の画像を読み込みました。")

        full_text = []
        for i, img in enumerate(images):
            click.echo(f"⚙️  処理中... {i+1}/{len(images)}")
            processed_img = ImagePreprocessor.process(img)
            text = ocr_engine.extract_text(processed_img)
            full_text.append(f"--- Page {i+1} ---\n{text}\n")

        # 結果表示
        result = "\n".join(full_text)
        if output:
            with open(output, 'w', encoding='utf-8') as f:
                f.write(result)
            click.echo(f"✅ 保存完了: {output}")
        else:
            click.echo("\n" + "="*10 + " 結果 " + "="*10)
            click.echo(result)
            click.echo("="*26)

    except Exception as e:
        click.echo(f"❌ エラー: {e}", err=True)

if __name__ == '__main__':
    main()