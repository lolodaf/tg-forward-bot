import os
import requests
import asyncio
import threading
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

# 获取 Render 自动分配的公网域名 (用来给图片生成外链)
RENDER_URL = os.environ.get('RENDER_EXTERNAL_URL', '')
# ============================================

app = Flask(__name__)

# 创建一个临时文件夹用来存放下载的图片
DOWNLOAD_DIR = 'downloads'
if not os.path.exists(DOWNLOAD_DIR):
    os.makedirs(DOWNLOAD_DIR)

# 网页首页 (用于 UptimeRobot 保活)
@app.route('/')
def index():
    return "Telegram 监听机器人运行中（支持图片转发）！"

# 新增功能：将下载的图片暴露为外链，供钉钉读取
@app.route('/media/<path:filename>')
def serve_media(filename):
    return send_from_directory(DOWNLOAD_DIR, filename)

def run_telethon():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)

    @client.on(events.NewMessage(chats=TARGET_CHAT, from_users=TARGET_USER))
    async def handler(event):
        msg_text = event.raw_text or ""
        photo_url = ""

        # 【核心逻辑】如果消息包含图片，则下载并生成外链
        if event.photo:
            try:
                print("检测到图片，正在下载...")
                # 下载图片到 downloads 文件夹
                path = await event.download_media(DOWNLOAD_DIR)
                filename = os.path.basename(path)
                # 拼接成能在公网访问的图片 URL
                if RENDER_URL:
                    photo_url = f"{RENDER_URL}/media/{filename}"
                print(f"图片下载成功：{photo_url}")
            except Exception as e:
                print(f"下载图片失败: {e}")

        # 构造钉钉 Markdown 消息 (支持图文并茂)
        # 这里的 title 必须包含你设定的关键词（如"TG转发"）
        md_text = f"### 【TG转发】白露发话啦：\n\n{msg_text}\n\n"
        
        if photo_url:
            # 插入图片 Markdown 语法
            md_text += f"![图片]({photo_url})\n"
        elif event.media and not event.photo:
            # 如果是视频、文件、动态表情包等非静态图片，提示文字
            md_text += "\n> *(附带了一个视频/文件/动态表情包，请前往 Telegram 查看)*"

        payload = {
            "msgtype": "markdown",
            "markdown": {
                "title": "TG转发",
                "text": md_text
            }
        }
        
        try:
            requests.post(DINGTALK_WEBHOOK, json=payload)
            print("成功转发一条 Markdown 消息到钉钉！")
        except Exception as e:
            print(f"转发钉钉失败: {e}")

    print("开始监听白露的消息...")
    client.start()
    client.run_until_disconnected()

if __name__ == '__main__':
    bot_thread = threading.Thread(target=run_telethon)
    bot_thread.start()
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
