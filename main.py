import os
import requests
import asyncio
import threading
from flask import Flask
from telethon import TelegramClient, events
from telethon.sessions import StringSession

# ================= 核心配置 =================
# 官方安卓客户端的开源 API
API_ID = 2040
API_HASH = 'b18441a1ff607e10a989891a5462e627'

# 从环境变量获取你之前提取到的 Session 和钉钉 Webhook
SESSION_STRING = os.environ.get('SESSION_STRING', '')
DINGTALK_WEBHOOK = os.environ.get('DINGTALK_WEBHOOK', '')

# 监听的目标群组和目标人
TARGET_CHAT = 'btcwhitelulu'  # 白露加密情报局
TARGET_USER = 'btcwhitelu'    # 只监听发件人为 @btcwhitelu 的消息
# ============================================

app = Flask(__name__)

# 这个简单的网页是为了应付 Render 的检查，防止程序被强行休眠
@app.route('/')
def index():
    return "Telegram 监听机器人运行中！正在监听白露的消息..."

def run_telethon():
    # 建立异步事件循环
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    # 使用你的账号凭证登录
    client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)

    # 核心监听逻辑：指定 chat 和 from_users
    @client.on(events.NewMessage(chats=TARGET_CHAT, from_users=TARGET_USER))
    async def handler(event):
        # 提取文本内容 (如果是图片则提取配文，如果没有配文则显示提示)
        msg_text = event.raw_text
        if not msg_text:
            msg_text = "[收到一张图片/表情包/文件，请前往 Telegram 查看]"

        # 构造发给钉钉的消息（注意：内容里包含了"TG转发"，请确保钉钉机器人的安全设置里填了这个关键词）
        payload = {
            "msgtype": "text",
            "text": {
                "content": f"【TG转发】白露发话啦：\n\n{msg_text}"
            }
        }
        
        try:
            requests.post(DINGTALK_WEBHOOK, json=payload)
            print("成功抓取并转发了一条白露的消息！")
        except Exception as e:
            print(f"转发钉钉失败: {e}")

    # 启动客户端
    print("开始监听白露的消息...")
    client.start()
    client.run_until_disconnected()

if __name__ == '__main__':
    # 开启一个后台线程运行 Telegram 监听脚本
    bot_thread = threading.Thread(target=run_telethon)
    bot_thread.start()
    
    # 主线程运行 Flask 网页服务，绑定 Render 分配的端口
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
