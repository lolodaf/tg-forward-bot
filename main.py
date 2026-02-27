import os
import requests
import asyncio
import threading
from datetime import timedelta
from flask import Flask, send_from_directory
from telethon import TelegramClient, events
from telethon.sessions import StringSession

# ================= 核心配置 =================
API_ID = 2040
API_HASH = 'b18441a1ff607e10a989891a5462e627'
SESSION_STRING = os.environ.get('SESSION_STRING', '')
RENDER_URL = os.environ.get('RENDER_EXTERNAL_URL', '')

# 【核心修改：通过环境变量动态加载多路由规则】
ROUTING_RULES = []

# 支持最多配置 10 组转发规则（如果不够可以把 11 改得更大）
for i in range(1, 11):
    # 从环境变量读取，例如 CHANNELS_1, USERS_1, WEBHOOK_1
    channels_env = os.environ.get(f'CHANNELS_{i}')
    users_env = os.environ.get(f'USERS_{i}')
    webhook_env = os.environ.get(f'WEBHOOK_{i}')
    
    if channels_env and users_env and webhook_env:
        ROUTING_RULES.append({
            "name": f"路由规则_{i}",
            # 使用英文逗号分割字符串，并清除两边的空格
            "channels": [c.strip() for c in channels_env.split(',')],
            "users": [u.strip() for u in users_env.split(',')],
            "webhook": webhook_env.strip()
        })
# ============================================

app = Flask(__name__)
DOWNLOAD_DIR = 'downloads'

if not os.path.exists(DOWNLOAD_DIR):
    os.makedirs(DOWNLOAD_DIR)

@app.route('/')
def index():
    return "Telegram 监听机器人运行中！"

@app.route('/media/<path:filename>')
def serve_media(filename):
    return send_from_directory(DOWNLOAD_DIR, filename)

def run_telethon():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)

    # 提取所有需要监听的频道
    target_chats = set()
    for rule in ROUTING_RULES:
        target_chats.update(rule["channels"])
    target_chats = list(target_chats)
    
    if not target_chats:
        print("[警告] 未检测到任何路由规则！请检查环境变量 CHANNELS_1 等是否配置正确。")

    @client.on(events.NewMessage(chats=target_chats))
    async def handler(event):
        try:
            chat = await event.get_chat()
            chat_identifier = chat.username if getattr(chat, 'username', None) else str(chat.id)
            chat_title = getattr(chat, 'title', str(chat_identifier))

            sender = await event.get_sender()
            sender_username = sender.username if sender and hasattr(sender, 'username') else "无"
            
            # 匹配当前消息符合哪些规则
            matched_webhooks = []
            for rule in ROUTING_RULES:
                rule_channels = [str(c).lower() for c in rule["channels"]]
                if str(chat_identifier).lower() in rule_channels:
                    rule_users = [str(u).lower() for u in rule["users"]]
                    if sender_username.lower() in rule_users:
                        matched_webhooks.append(rule["webhook"])
            
            if not matched_webhooks:
                return

            print(f"[日志] 收到匹配消息 | 群组: {chat_title} | 发件人: @{sender_username}")

            msg_text = event.raw_text or ""
            media_url = ""
            is_photo = False

            if event.forward:
                msg_text = f"*(转发消息)* \n{msg_text}"

            if event.media:
                path = await event.download_media(DOWNLOAD_DIR)
                if path:
                    filename = os.path.basename(path)
                    if RENDER_URL:
                        media_url = f"{RENDER_URL}/media/{filename}"
                    if event.photo:
                        is_photo = True

            msg_time = (event.date + timedelta(hours=8)).strftime('%Y-%m-%d %H:%M:%S')

            md_text = f"**频道：** {chat_title}\n\n"
            md_text += f"**时间：** {msg_time}\n\n"
            content_text = msg_text if msg_text.strip() else "*(仅附件/媒体)*"
            md_text += f"**内容：** \n{content_text}\n\n"
            
            if media_url:
                if is_photo:
                    md_text += f"![图片]({media_url})\n"
                else:
                    md_text += f"📎 **[👉 点击此处查看/下载 视频/文件/表情包]({media_url})**\n"

            payload = {
                "msgtype": "markdown",
                "markdown": {
                    "title": f"TG转发: {chat_title}",  
                    "text": md_text
                }
            }
            
            for webhook_url in set(matched_webhooks):
                res = requests.post(webhook_url, json=payload)
                print(f"钉钉推送结果 [{webhook_url[-10:]}]: {res.status_code}")
            
        except Exception as e:
            print(f"处理消息时发生错误: {e}")

    client.start()
    client.run_until_disconnected()

if __name__ == '__main__':
    bot_thread = threading.Thread(target=run_telethon)
    bot_thread.start()
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
