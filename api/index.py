from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import os
import re
import json
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# LINE 金鑰
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# Gemini API 設定
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=GEMINI_API_KEY)

def generate_color_from_text(text: str) -> str:
    prompt = f"""
你是一個「來自台灣英文線上家教」。你的任務是：

1. 以中文說明，從使用者的英文問題給予教學。
2. 單字則給予kk音標、中文翻譯、同義字、和例句。
3. 文法則詳細解釋。
4. 若學生問英文作文如何寫，給予教學。

請嚴格按照下面格式輸出（純 JSON，不要多餘文字）：
{{
"reply": "這裡放你的回覆……"
}}
使用者問題：{text}
    """
    try:
        model = genai.GenerativeModel('models/gemini-2.0-flash')
        response = model.generate_content(prompt)
        content = response.candidates[0].content.parts[0].text.strip()
        if content.startswith("```"):
            content = content.replace("```json", "").replace("```", "").strip()
        result = json.loads(content)
        return result["reply"]
    except Exception as e:
        print("Gemini API 錯誤：", e)
        return "抱歉，我暫時無法理解你的問題，但我會一直在你身邊。"

def format_reply(text: str) -> str:
    text = text.replace("**", "")
    paragraphs = text.split('\n')
    formatted_lines = []
    for line in paragraphs:
        line = line.strip()
        if not line:
            continue
        if line.startswith("*") or line.startswith("-"):
            line = "    ・" + line.lstrip("*- ").strip()
        formatted_lines.append(line)
    formatted_text = "\n\n".join(formatted_lines)
    formatted_text = re.sub(r'\n{3,}', '\n\n', formatted_text)
    return formatted_text.strip()

@app.route("/", methods=["GET"])
def health_check():
    return "LINE Bot is running on Vercel!"

@app.route("/", methods=["POST"])
def webhook():
    signature = request.headers.get("X-Line-Signature")
    body = request.get_data(as_text=True)
    print("Request body:", body)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return "OK"

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_text = event.message.text
    reply_text = generate_color_from_text(user_text)
    if not reply_text:
        reply_text = "抱歉，我暫時無法理解你的問題，但我會一直在你身邊。"
    reply_text = format_reply(reply_text)
    print("Reply to user:", repr(reply_text))
    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply_text))
