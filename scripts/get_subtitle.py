import sys
import os
from urllib.parse import urljoin
from curl_cffi import requests
from lxml import etree

BASE_URL = "https://subtitlecat.com"

def get_headers():
    return {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }

def search_subtitles(keyword, proxy=None):
    """
    搜索字幕，对应 Java 中的 searchSubtitles 方法
    """
    print(f"正在搜索: {keyword} ...")
    url = f"{BASE_URL}/index.php"
    params = {"search": keyword}
    
    proxies = {"http": proxy, "https": proxy} if proxy else None

    try:
        # 使用 curl_cffi 模拟浏览器指纹，对应 Java 中的 UserAgentInterceptor
        r = requests.get(url, params=params, headers=get_headers(), impersonate="chrome", timeout=30, proxies=proxies)
        if r.status_code != 200:
            print(f"搜索请求失败，状态码: {r.status_code}")
            return []
        
        html = r.text
        tree = etree.HTML(html)
        
        # 对应 Java 中的选择器逻辑: .sub-table tbody tr, table tbody tr 等
        # 这里使用 XPath 查找表格行
        rows = tree.xpath("//table//tbody//tr")
        if not rows:
            rows = tree.xpath("//tr")
            
        results = []
        # 对应 Java 中的 Math.min(rows.size(), 5)
        for row in rows[:5]: 
            # 对应 Java: tds.get(0).select("a")
            links = row.xpath(".//td[1]//a")
            if not links:
                continue
            
            link = links[0]
            title = link.text.strip() if link.text else "Unknown"
            href = link.get("href")
            
            # 简单提取下载量和评论数用于展示 (可选)
            # Java 代码中有解析下载量和评论数的逻辑
            
            if href:
                results.append({"title": title, "href": href})
                
        return results
    except Exception as e:
        print(f"搜索出错: {e}")
        return []

def get_download_link(detail_path, proxy=None):
    """
    获取下载链接，对应 Java 中的 getSubtitleDownloadUrl 和 parseDownloadUrl 方法
    """
    url = urljoin(BASE_URL, detail_path)
    print(f"正在获取详情页: {url} ...")
    
    proxies = {"http": proxy, "https": proxy} if proxy else None
    
    try:
        r = requests.get(url, headers=get_headers(), impersonate="chrome", timeout=30, proxies=proxies)
        if r.status_code != 200:
            print(f"详情页请求失败: {r.status_code}")
            return None
            
        html = r.text
        tree = etree.HTML(html)
        
        download_url = None
        
        # 对应 Java 中的 parseDownloadUrl 逻辑
        # 1. 查找中文字幕下载链接 (#download_zh-CN, #download_zh)
        candidates = tree.xpath("//a[@id='download_zh-CN']/@href")
        if not candidates:
            candidates = tree.xpath("//a[@id='download_zh']/@href")
        
        # 2. 查找通用下载链接 (.download-link)
        if not candidates:
            candidates = tree.xpath("//a[contains(@class, 'download-link')]/@href")
            
        if candidates:
            download_url = candidates[0]
        else:
            # 3. 兜底策略：查找包含 download 或 .srt/.ass 的链接
            all_links = tree.xpath("//a/@href")
            for link in all_links:
                if "download" in link or link.endswith(".srt") or link.endswith(".ass"):
                    download_url = link
                    break
        
        if download_url:
            return urljoin(BASE_URL, download_url)
        return None

    except Exception as e:
        print(f"获取下载链接出错: {e}")
        return None

def download_file(url, filename, proxy=None):
    """
    下载文件
    """
    print(f"正在下载: {url} -> {filename}")
    proxies = {"http": proxy, "https": proxy} if proxy else None
    try:
        r = requests.get(url, headers=get_headers(), impersonate="chrome", timeout=60, proxies=proxies)
        if r.status_code == 200:
            with open(filename, 'wb') as f:
                f.write(r.content)
            print(f"下载成功! 文件已保存为: {filename}")
        else:
            print(f"下载失败，状态码: {r.status_code}")
    except Exception as e:
        print(f"下载出错: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("使用方法: python get_subtitle.py <番号或关键词> [代理URL]")
        print("示例: python get_subtitle.py SSIS-062 http://127.0.0.1:7890")
        sys.exit(1)
        
    keyword = sys.argv[1]
    proxy = sys.argv[2] if len(sys.argv) > 2 else None
    
    # 1. 搜索
    results = search_subtitles(keyword, proxy)
    
    if not results:
        print("未找到相关字幕。")
        sys.exit(0)
        
    print(f"找到 {len(results)} 个结果:")
    for i, res in enumerate(results):
        print(f"[{i+1}] {res['title']}")
    
    # 简单起见，默认选择第一个结果，或者匹配度最高的（这里直接取第一个）
    best_match = results[0]
    print(f"\n正在处理第一个结果: {best_match['title']}")
    
    # 2. 解析详情页获取下载链接
    dl_link = get_download_link(best_match['href'], proxy)
    
    if dl_link:
        # 3. 下载
        # 尝试从 URL 推断扩展名，默认为 .srt
        ext = ".srt"
        if ".ass" in dl_link:
            ext = ".ass"
        elif ".vtt" in dl_link:
            ext = ".vtt"
            
        filename = f"{keyword}{ext}"
        download_file(dl_link, filename, proxy)
    else:
        print("抱歉，未能提取到有效的下载链接。")
