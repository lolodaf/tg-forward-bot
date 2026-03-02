import os
import requests
import asyncio
import threading
from datetime import timedelta  # 新增：用于处理时区
from flask import Flask, send_from_directory
from telethon import TelegramClient, events
from telethon.sessions import StringSession

# ================= 核心配置 =================
API_ID = 2040
API_HASH = 'b18441a1ff607e10a989891a5462e627'

SESSION_STRING = os.environ.get('SESSION_STRING', '')
DINGTALK_WEBHOOK = os.environ.get('DINGTALK_WEBHOOK', '')

TARGET_CHAT = 'btcwhitelulu'  
TARGET_USER = 'btcwhitelu'    
RENDER_URL = os.environ.get('RENDER_EXTERNAL_URL', '')
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

    @client.on(events.NewMessage(chats=TARGET_CHAT))
    async def handler(event):
        try:
            # 获取真实发件人
            sender = await event.get_sender()
            sender_username = sender.username if sender and hasattr(sender, 'username') else "无"
            
            print(f"[日志] 收到群消息 | 发件人: @{sender_username} | 内容: {str(event.raw_text)[:20]}...")

            if not sender_username or sender_username.lower() != TARGET_USER.lower():
                return

            msg_text = event.raw_text or ""
            media_url = ""
            is_photo = False

            if event.forward:
                msg_text = f"*(转发消息)* \n{msg_text}"

            # 【修改点1：处理所有媒体文件，包括视频、文件、表情包】
            if event.media:
                print("检测到媒体文件，正在下载...")
                # download_media 默认支持下载图片、视频、文件、动态表情包等
                path = await event.download_media(DOWNLOAD_DIR)
                if path:
                    filename = os.path.basename(path)
                    if RENDER_URL:
                        media_url = f"{RENDER_URL}/media/{filename}"
                    print(f"媒体文件下载成功：{media_url}")
                    
                    # 标记是否为纯图片，用于后续钉钉展示逻辑
                    if event.photo:
                        is_photo = True

            # 【修改点2：格式化时间为北京时间 (UTC+8)】
            msg_time = (event.date + timedelta(hours=8)).strftime('%Y-%m-%d %H:%M:%S')

            # 【修改点3：按照“频道： 时间 内容”的格式排版】
            md_text = f"**频道：** {TARGET_CHAT}\n\n"
            md_text += f"**时间：** {msg_time}\n\n"
            
            # 如果没有文字，补充一下提示避免“内容：”后面是空的
            content_text = msg_text if msg_text.strip() else "*(仅附件/媒体)*"
            md_text += f"**内容：** \n{content_text}\n\n"
            
            # 【修改点4：分别处理图片和其他附件的展示】
            if media_url:
                if is_photo:
                    md_text += f"![图片]({media_url})\n"
                else:
                    # 钉钉不支持直接嵌入播放视频，所以用超链接让用户点击查看/下载
                    md_text += f"📎 **[👉 点击此处查看/下载 视频/文件/表情包]({media_url})**\n"

            payload = {
                "msgtype": "markdown",
                "markdown": {
                    "title": "TG转发",
                    "text": md_text
                }
            }
            
            res = requests.post(DINGTALK_WEBHOOK, json=payload)
            print(f"钉钉发送结果: {res.status_code} - {res.text}")
            
        except Exception as e:
            print(f"处理消息时发生错误: {e}")

    print("开始监听白露的消息...")
    client.start()
    client.run_until_disconnected()

if __name__ == '__main__':
    bot_thread = threading.Thread(target=run_telethon)
    bot_thread.start()
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
