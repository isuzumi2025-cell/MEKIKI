from abc import ABC, abstractmethod
from PIL import Image

class OCREngineStrategy(ABC):
    """
    全てのOCRエンジンが守るべき共通ルール（インターフェース）。
    これを作ることで、後でエンジンを増やしてもメインコードを修正しなくて済みます。
    """

    @abstractmethod
    def extract_text(self, image: Image.Image) -> str:
        """
        PIL画像を受け取り、抽出したテキストを文字列で返す。
        """
        pass
