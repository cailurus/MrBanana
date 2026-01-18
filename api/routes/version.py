"""
版本检查 API
"""
from fastapi import APIRouter
import httpx

router = APIRouter()

# 当前版本（与前端 i18n.js 中的 APP_VERSION 保持一致）
CURRENT_VERSION = "0.2.5"

# GitHub 仓库信息
GITHUB_REPO = "cailurus/MrBanana"


def compare_versions(current: str, latest: str) -> bool:
    """比较版本号，返回 True 表示有新版本"""
    try:
        current_parts = [int(x) for x in current.split('.')]
        latest_parts = [int(x) for x in latest.split('.')]
        # 补齐位数
        while len(current_parts) < 3:
            current_parts.append(0)
        while len(latest_parts) < 3:
            latest_parts.append(0)
        return latest_parts > current_parts
    except Exception:
        return False


@router.get("/api/version")
async def get_version():
    """获取当前版本信息"""
    return {
        "version": CURRENT_VERSION,
        "repo": GITHUB_REPO
    }


@router.get("/api/version/check")
async def check_update():
    """检查是否有新版本
    
    通过 GitHub API 获取最新 release 信息
    """
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            # 获取最新 release
            release_url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
            resp = await client.get(release_url, headers={
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "MrBanana-App"
            })
            
            if resp.status_code == 200:
                data = resp.json()
                latest_version = data.get("tag_name", "").lstrip("v")
                has_update = compare_versions(CURRENT_VERSION, latest_version)
                
                return {
                    "current_version": CURRENT_VERSION,
                    "latest_version": latest_version,
                    "has_update": has_update,
                    "release_url": data.get("html_url", ""),
                    "release_name": data.get("name", ""),
                    "published_at": data.get("published_at", ""),
                }
            elif resp.status_code == 404:
                # 没有 release，说明是最新的
                return {
                    "current_version": CURRENT_VERSION,
                    "latest_version": CURRENT_VERSION,
                    "has_update": False,
                    "message": "No releases found"
                }
            else:
                return {
                    "current_version": CURRENT_VERSION,
                    "has_update": False,
                    "error": f"GitHub API returned {resp.status_code}"
                }
    except Exception as e:
        return {
            "current_version": CURRENT_VERSION,
            "has_update": False,
            "error": str(e)
        }
