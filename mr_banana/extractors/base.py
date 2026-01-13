"""
视频提取器基类
"""
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any


class BaseExtractor(ABC):
    """视频信息提取器基类"""

    def __init__(self, network_handler):
        self.network = network_handler

    @abstractmethod
    def can_handle(self, url: str) -> bool:
        """检查是否可以处理该 URL"""
        pass

    @abstractmethod
    def extract(self, url: str) -> Optional[Dict[str, Any]]:
        """
        提取视频信息
        
        Returns:
            dict: 包含以下字段:
                - id: str - 视频 ID
                - title: str - 视频标题
                - video_url: str - m3u8 或直接链接
                - metadata: dict - 其他元数据 (可选)
        """
        pass
