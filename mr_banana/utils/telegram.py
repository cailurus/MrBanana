"""
Telegram Bot 推送模块
用于将订阅更新推送到 Telegram
"""
import httpx
from typing import Optional, List, Dict


class TelegramBot:
    """Telegram Bot 推送类"""
    
    def __init__(self, bot_token: str, chat_id: str):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.base_url = f"https://api.telegram.org/bot{bot_token}"
    
    def send_message(self, text: str, parse_mode: str = "HTML") -> bool:
        """发送消息到 Telegram
        
        Args:
            text: 消息内容（支持HTML格式）
            parse_mode: 解析模式，默认HTML
            
        Returns:
            是否发送成功
        """
        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.post(
                    f"{self.base_url}/sendMessage",
                    json={
                        "chat_id": self.chat_id,
                        "text": text,
                        "parse_mode": parse_mode,
                        "disable_web_page_preview": True,
                    }
                )
                return response.status_code == 200
        except Exception as e:
            print(f"[Telegram] Failed to send message: {e}")
            return False
    
    def test_connection(self) -> tuple[bool, str]:
        """测试 Bot 连接是否正常
        
        Returns:
            (是否成功, 错误信息)
        """
        try:
            with httpx.Client(timeout=10.0) as client:
                # 先验证 Bot Token
                response = client.get(f"{self.base_url}/getMe")
                if response.status_code != 200:
                    return False, "Bot Token 无效"
                
                # 发送测试消息
                response = client.post(
                    f"{self.base_url}/sendMessage",
                    json={
                        "chat_id": self.chat_id,
                        "text": "🍌 Mr. Banana 订阅推送测试成功！\n\nTelegram Bot 已成功连接。",
                        "parse_mode": "HTML",
                        "disable_web_page_preview": True,
                    }
                )
                
                if response.status_code == 200:
                    return True, ""
                
                # 解析错误
                try:
                    error_data = response.json()
                    error_desc = error_data.get("description", "")
                    if "chat not found" in error_desc.lower():
                        return False, "请先在 Telegram 中向 Bot 发送 /start 开始对话"
                    elif "bot was blocked" in error_desc.lower():
                        return False, "Bot 已被用户屏蔽，请取消屏蔽后重试"
                    elif "chat_id" in error_desc.lower():
                        return False, f"Chat ID 无效: {error_desc}"
                    else:
                        return False, error_desc
                except:
                    return False, f"发送失败: HTTP {response.status_code}"
                    
        except httpx.TimeoutException:
            return False, "连接超时，请检查网络"
        except Exception as e:
            print(f"[Telegram] Connection test failed: {e}")
            return False, str(e)


def send_subscription_update(
    bot_token: str,
    chat_id: str,
    updates: List[Dict]
) -> bool:
    """发送订阅更新通知
    
    Args:
        bot_token: Telegram Bot Token
        chat_id: Telegram Chat ID
        updates: 更新列表，每个元素包含 code, new_count, magnet_links
        
    Returns:
        是否发送成功
    """
    if not bot_token or not chat_id or not updates:
        return False
    
    bot = TelegramBot(bot_token, chat_id)
    
    # 构建消息
    lines = ["🍌 <b>Mr. Banana 订阅更新</b>\n"]
    
    for update in updates:
        code = update.get("code", "Unknown")
        new_count = update.get("new_count", 0)
        javdb_url = f"https://javdb.com/search?q={code}"
        
        lines.append(f"📦 <b>{code}</b>")
        lines.append(f"   发现 {new_count} 个新磁力链接")
        lines.append(f"   <a href=\"{javdb_url}\">在 JavDB 查看</a>\n")
    
    lines.append(f"\n共 {len(updates)} 个订阅有更新")
    
    message = "\n".join(lines)
    return bot.send_message(message)


def send_daily_summary(
    bot_token: str,
    chat_id: str,
    total_subscriptions: int,
    checked_count: int,
    updated_count: int,
    updates: List[Dict] = None
) -> bool:
    """发送每日检查汇总
    
    Args:
        bot_token: Telegram Bot Token
        chat_id: Telegram Chat ID
        total_subscriptions: 总订阅数
        checked_count: 检查数量
        updated_count: 有更新的数量
        updates: 更新详情列表
        
    Returns:
        是否发送成功
    """
    if not bot_token or not chat_id:
        return False
    
    bot = TelegramBot(bot_token, chat_id)
    
    # 构建消息
    lines = ["🍌 <b>Mr. Banana 每日订阅检查报告</b>\n"]
    lines.append(f"📊 总订阅数: {total_subscriptions}")
    lines.append(f"✅ 已检查: {checked_count}")
    lines.append(f"🆕 有更新: {updated_count}\n")
    
    if updates and updated_count > 0:
        lines.append("<b>更新详情:</b>")
        for update in updates[:10]:  # 最多显示10个
            code = update.get("code", "Unknown")
            new_count = update.get("new_count", 0)
            lines.append(f"  • {code}: {new_count} 个新链接")
        
        if len(updates) > 10:
            lines.append(f"  ... 还有 {len(updates) - 10} 个")
    elif updated_count == 0:
        lines.append("暂无新更新 ✨")
    
    message = "\n".join(lines)
    return bot.send_message(message)
