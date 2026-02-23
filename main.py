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

    # 【改动1】放宽条件：只锁定群组，先把群里所有人的消息都抓进来看看
    @client.on(events.NewMessage(chats=TARGET_CHAT))
    async def handler(event):
        try:
            # 获取真实发件人
            sender = await event.get_sender()
            sender_username = sender.username if sender and hasattr(sender, 'username') else "无"
            
            # 【核心排错】把每一条消息的动态打印到 Render 日志里
            print(f"[日志] 收到群消息 | 发件人: @{sender_username} | 内容: {str(event.raw_text)[:20]}...")

            # 【改动2】手动精准核对是不是白露发出来的（忽略大小写）
            if not sender_username or sender_username.lower() != TARGET_USER.lower():
                return

            msg_text = event.raw_text or ""
            photo_url = ""

            # 【改动3】如果是转发的消息，加上专门的标记，防止文本为空
            if event.forward:
                msg_text = f"*(转发消息)* \n{msg_text}"

            # 处理图片
            if event.photo:
                print("检测到图片，正在下载...")
                path = await event.download_media(DOWNLOAD_DIR)
                filename = os.path.basename(path)
                if RENDER_URL:
                    photo_url = f"{RENDER_URL}/media/{filename}"
                print(f"图片下载成功：{photo_url}")

            md_text = f"### 【TG转发】白露发话啦：\n\n{msg_text}\n\n"
            
            if photo_url:
                md_text += f"![图片]({photo_url})\n"
            elif event.media and not event.photo:
                md_text += "\n> *(附带了一个视频/文件/动态表情包，请前往 Telegram 查看)*"

            payload = {
                "msgtype": "markdown",
                "markdown": {
                    "title": "TG转发",
                    "text": md_text
                }
            }
            
            # 【改动4】把钉钉的回执打印出来，看钉钉有没有偷偷拒收
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
