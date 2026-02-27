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

# 【核心修改：支持子区(Topic)的动态路由规则】
ROUTING_RULES = []

for i in range(1, 11):
    channels_env = os.environ.get(f'CHANNELS_{i}')
    users_env = os.environ.get(f'USERS_{i}')
    webhook_env = os.environ.get(f'WEBHOOK_{i}')
    
    if channels_env and users_env and webhook_env:
        channels_parsed = []
        # 解析频道的格式，支持 "群名" 或 "群名/TopicID"
        for c in channels_env.split(','):
            c = c.strip()
            if '/' in c:
                parts = c.split('/')
                channels_parsed.append({"name": parts[0].strip(), "topic": int(parts[1].strip())})
            else:
                channels_parsed.append({"name": c, "topic": None})

        ROUTING_RULES.append({
            "name": f"路由规则_{i}",
            "channels": channels_parsed,
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

    # 提取所有需要监听的主频道名称交给 Telethon（如果是子区，也要先监听主群）
    target_chats = set()
    for rule in ROUTING_RULES:
        for c in rule["channels"]:
            target_chats.add(c["name"])
    target_chats = list(target_chats)
    
    if not target_chats:
        print("[警告] 未检测到任何路由规则！")

    @client.on(events.NewMessage(chats=target_chats))
    async def handler(event):
        try:
            chat = await event.get_chat()
            chat_identifier = chat.username if getattr(chat, 'username', None) else str(chat.id)
            chat_title = getattr(chat, 'title', str(chat_identifier))

            sender = await event.get_sender()
            sender_username = sender.username if sender and hasattr(sender, 'username') else "无"
            
            # 【关键修改：获取当前消息所在的子区 Topic ID】
            msg_topic_id = None
            if event.message.reply_to:
                # Telethon 中子区的消息本质上是回复主贴，所以这样获取 Topic ID
                msg_topic_id = getattr(event.message.reply_to, 'reply_to_top_id', None) or getattr(event.message.reply_to, 'reply_to_msg_id', None)

            # 匹配当前消息符合哪些规则
            matched_webhooks = []
            for rule in ROUTING_RULES:
                for rule_channel in rule["channels"]:
                    # 1. 检查主群名是否匹配
                    if str(chat_identifier).lower() == str(rule_channel["name"]).lower():
                        # 2. 如果规则中指定了子区(Topic)，检查是否匹配
                        if rule_channel["topic"] is not None:
                            if msg_topic_id != rule_channel["topic"]:
                                continue # 如果这条消息不在指定的子区里，直接跳过这条规则
                        
                        # 3. 检查发件人是否匹配
                        rule_users = [str(u).lower() for u in rule["users"]]
                        if sender_username.lower() in rule_users:
                            matched_webhooks.append(rule["webhook"])
            
            if not matched_webhooks:
                return

            # 如果匹配上了，判断是否有专属子区，在日志和钉钉里显示得更清楚一点
            topic_log = f" [子区:{msg_topic_id}]" if msg_topic_id else ""
            print(f"[日志] 收到匹配消息 | 群组: {chat_title}{topic_log} | 发件人: @{sender_username}")

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

            # 钉钉展示：如果是在子区里，把子区 ID 也显示出来，方便追溯
            display_chat_name = f"{chat_title} (子区: {msg_topic_id})" if msg_topic_id else chat_title

            md_text = f"**频道：** {display_chat_name}\n\n"
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
