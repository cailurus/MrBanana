"""Test script: verify curl_cffi direct mode with jable cookies."""
import json
import sys
sys.path.insert(0, '.')

from mr_banana.extractors.jable import JableExtractor
from mr_banana.utils.network import NetworkHandler
from mr_banana.utils.config import load_config, AppConfig

cfg = load_config()
jable_cookies = AppConfig.parse_cookie_string(cfg.jable_cookie) if cfg.jable_cookie else None
print("Cookies available:", list(jable_cookies.keys()) if jable_cookies else "NONE")

nh = NetworkHandler(cookies=jable_cookies)
extractor = JableExtractor(nh)

url = "https://jable.tv/videos/mida-460/"
print(f"\nTesting extract from: {url}")
print("-" * 50)

try:
    info = extractor.extract(url)
    if info:
        print("EXTRACTION SUCCESS!")
        vid = info["id"]
        title = info["title"]
        vurl = info["video_url"]
        print(f"  ID: {vid}")
        print(f"  Title: {title}")
        print(f"  Video URL: {vurl[:80]}...")
        print(f"  Metadata keys: {list(info['metadata'].keys())}")
    else:
        print("EXTRACTION FAILED: No info returned")
except Exception as e:
    print(f"ERROR: {e}")