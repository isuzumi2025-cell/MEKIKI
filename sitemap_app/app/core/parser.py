from urllib.parse import urlparse, urljoin, urlunparse, parse_qs, urlencode
import re
from typing import List, Set, Optional
from app.core.config import settings


class URLParser:
    @staticmethod
    def normalize_url(url: str, base_url: str = None, keep_params: List[str] = None) -> str:
        """
        URLを正規化する
        - スキーム/ホスト名を小文字に
        - www. プレフィックス除去
        - 末尾スラッシュ統一（除去）
        - フラグメント除去
        - トラッキングパラメータ除去（keep_paramsで例外指定可能）
        """
        if not url:
            return ""
            
        if base_url:
            url = urljoin(base_url, url)
        
        parsed = urlparse(url)
        
        # Scheme normalization
        scheme = parsed.scheme.lower()
        if scheme not in ['http', 'https']:
            return ""  # Skip non-http
            
        # Domain normalization
        netloc = parsed.netloc.lower()
        if netloc.startswith('www.'):
            netloc = netloc[4:]
            
        # Path normalization (trailing slash removal)
        path = parsed.path
        if not path:
            path = "/"
        elif path != "/" and path.endswith("/"):
            path = path[:-1]
            
        # Remove fragments
        fragment = ""
        
        # Query parameters filtering
        keep_params = keep_params or []
        tracking_params = settings.TRACKING_PARAMS
        
        query = parsed.query
        if query:
            qs = parse_qs(query, keep_blank_values=True)
            new_qs = {}
            for k, v in qs.items():
                # 除外対象でないか、明示的に保持指定されている場合は残す
                if k in keep_params or k not in tracking_params:
                    new_qs[k] = v
            query = urlencode(new_qs, doseq=True)
            
        return urlunparse((scheme, netloc, path, parsed.params, query, fragment))

    @staticmethod
    def extract_links(html_content: str, base_url: str) -> List[str]:
        """HTMLからリンクを抽出して正規化"""
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html_content, 'html.parser')
        links = []
        seen = set()
        for a in soup.find_all('a', href=True):
            href = a['href']
            # Skip javascript:, mailto:, tel:, etc.
            if href.startswith(('javascript:', 'mailto:', 'tel:', '#')):
                continue
            normalized = URLParser.normalize_url(href, base_url)
            if normalized and normalized not in seen:
                links.append(normalized)
                seen.add(normalized)
        return links

    @staticmethod
    def is_internal_link(url: str, base_domain: str, allow_domains: List[str] = None) -> bool:
        """内部リンクかどうかを判定"""
        allow_domains = allow_domains or []
        
        netloc = urlparse(url).netloc.lower()
        if netloc.startswith('www.'):
            netloc = netloc[4:]
        if base_domain.startswith('www.'):
            base_domain = base_domain[4:]
        
        # 同一ドメインチェック
        if netloc == base_domain or netloc.endswith("." + base_domain):
            return True
            
        # 許可ドメインチェック
        for allowed in allow_domains:
            allowed = allowed.lower()
            if allowed.startswith('www.'):
                allowed = allowed[4:]
            if netloc == allowed or netloc.endswith("." + allowed):
                return True
                
        return False

    @staticmethod
    def matches_exclude_pattern(url: str, patterns: List[str]) -> bool:
        """除外パターンにマッチするかチェック"""
        path = urlparse(url).path
        for pattern in patterns:
            # 簡易ワイルドカード対応
            regex_pattern = pattern.replace("*", ".*")
            if re.match(regex_pattern, path):
                return True
        return False

    @staticmethod
    def extract_metadata(html_content: str) -> dict:
        """HTMLからメタデータを抽出"""
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html_content, 'html.parser')
        
        metadata = {
            "h1": None,
            "description": None,
            "canonical": None,
            "og_title": None,
            "og_description": None,
            "og_image": None,
            "noindex": False,
            "nofollow": False,
        }
        
        # H1
        h1 = soup.find('h1')
        if h1:
            metadata["h1"] = h1.get_text(strip=True)
        
        # Meta description
        desc = soup.find('meta', attrs={'name': 'description'})
        if desc and desc.get('content'):
            metadata["description"] = desc['content']
        
        # Canonical
        canonical = soup.find('link', attrs={'rel': 'canonical'})
        if canonical and canonical.get('href'):
            metadata["canonical"] = canonical['href']
        
        # OGP
        og_title = soup.find('meta', attrs={'property': 'og:title'})
        if og_title and og_title.get('content'):
            metadata["og_title"] = og_title['content']
            
        og_desc = soup.find('meta', attrs={'property': 'og:description'})
        if og_desc and og_desc.get('content'):
            metadata["og_description"] = og_desc['content']
            
        og_image = soup.find('meta', attrs={'property': 'og:image'})
        if og_image and og_image.get('content'):
            metadata["og_image"] = og_image['content']
        
        # Robots meta
        robots = soup.find('meta', attrs={'name': 'robots'})
        if robots and robots.get('content'):
            content = robots['content'].lower()
            metadata["noindex"] = 'noindex' in content
            metadata["nofollow"] = 'nofollow' in content
        
        return metadata
