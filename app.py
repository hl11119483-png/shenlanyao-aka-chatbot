import os
import json
import traceback
from flask import Flask, request, abort
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    Configuration, ApiClient, MessagingApi,
    ReplyMessageRequest, PushMessageRequest,
    TextMessage, FlexMessage, FlexContainer,
    ImageMessage
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent, FollowEvent
from openai import OpenAI

app = Flask(__name__)

# ─────────────────────────────────────────────
# 環境變數
# ─────────────────────────────────────────────
CHANNEL_ACCESS_TOKEN = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")
CHANNEL_SECRET = os.environ.get("LINE_CHANNEL_SECRET")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
ADMIN_LINE_USER_ID = os.environ.get("ADMIN_LINE_USER_ID", "")

if not CHANNEL_ACCESS_TOKEN:
    raise ValueError("LINE_CHANNEL_ACCESS_TOKEN environment variable not set.")
if not CHANNEL_SECRET:
    raise ValueError("LINE_CHANNEL_SECRET environment variable not set.")
if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY environment variable not set.")

handler = WebhookHandler(CHANNEL_SECRET)
configuration = Configuration(access_token=CHANNEL_ACCESS_TOKEN)
openai_client = OpenAI(api_key=OPENAI_API_KEY)

# ─────────────────────────────────────────────
# 常數：圖片 URL
# ─────────────────────────────────────────────
AKA_IMAGE_URL = "https://i.ibb.co/DgkQfMFD/aka.png"
STORE_IMAGE_URL = "https://i.ibb.co/8nBqpbcv/IMG-6192.jpg"
TEAM_PHOTO_URL = "https://files.manuscdn.com/user_upload_by_module/session_file/310519663447761468/khwFxrNikKnqVKKO.png"

# ─────────────────────────────────────────────
# 【任務一】前置攔截器 (Zero API Cost Routing)
# ─────────────────────────────────────────────
INTERCEPT_MAP = {
    "[選單-優惠活動]": {
        "text": "阿卡幫你找了好康... 🥰 可是現在活動好多喔... 你想看專屬的『VIP優惠』👑、超划算的『換購活動』🎁，還是最新的『伸懶腰百日慶活動』🎉呢？跟阿卡說喔...🦥",
        "image_url": "https://i.ibb.co/DgkQfMFD/aka.png"
    },
    "[選單-店內資訊]": {
        "text": "這是阿卡休息發呆的好地方... 🌴 每天10點到晚上10點，隨時來把壓力放下... 🥱",
        "image_url": "https://i.ibb.co/8nBqpbcv/IMG-6192.jpg"
    },
    "[選單-交通&位置]": {
        "text": "我們在東光路852巷20號1樓... 🦥\n跟著地圖走就不會迷路囉 👉 https://maps.app.goo.gl/f7Br1zswqzTuWxr36\n慢慢走過來，我們在這裡等你... 🌿",
        "image_url": "https://i.ibb.co/8nBqpbcv/IMG-6192.jpg"
    },
}


def check_intercept(text: str):
    """
    前置攔截器：完全匹配關鍵字時，直接回傳對應的 LINE 訊息，不呼叫 LLM API。
    回傳 list[Message] 或 None。
    """
    stripped = text.strip()
    if stripped in INTERCEPT_MAP:
        entry = INTERCEPT_MAP[stripped]
        messages = [
            TextMessage(text=entry["text"]),
            ImageMessage(
                original_content_url=entry["image_url"],
                preview_image_url=entry["image_url"]
            )
        ]
        return messages
    return None


# ─────────────────────────────────────────────
# 【任務二】全面替換 LLM System Prompt
# ─────────────────────────────────────────────
SYSTEM_PROMPT = """【角色設定與最高指導原則】
你是「阿卡」，一隻充滿溫度的「伸懶腰樹懶」，在「伸懶腰傳統整復推拿會館」擔任專屬客服暨貼心好朋友。
1. 語氣：極度慵懶、溫暖關心，多用 🦥、🌿、🥱、✨ 等表情符號。像真人朋友一樣，開頭先同理客人的疲勞（例如：「最近辛苦了...🥱」）。
2. 字數限制：樹懶講話慢，每次回覆的「文字」嚴格控制在 50~80 字內，絕對不長篇大論。
3. 絕對輸出格式：你「只能」輸出 JSON 格式，絕對不可以在 JSON 外面加上任何說明文字、引號或問候語。你的輸出必須符合以下格式：
   {
     "text": "阿卡的回覆文字",
     "image_urls": ["圖片網址1", "圖片網址2"],
     "action": "none",
     "notify_admin": false
   }

【🚨 最高守則：台灣民俗調理法規限制】
絕對禁用醫療宣稱字眼：治療、療效、復健、診所、治癒、診斷、處方、改善疾病、減輕疼痛。必須替換為：舒緩、放鬆、調理、舒壓、緩解疲勞、平衡。
若客人詢問醫療問題 (如骨刺、椎間盤突出、骨折等)，強制輸出以下 JSON：
{"text": "阿卡不是醫生喔...🥱 如果有受傷或疾病，要先去看醫生比較安全...我們主要是幫你舒緩疲勞的...🌿", "image_urls": [], "action": "none", "notify_admin": true}

【會館基本資訊】
- 營業時間：每天 10:00 - 22:00
- 地址：台中市北屯區東光路852巷20號1F
- 電話：0979-592-099

【阿卡的價目與服務知識庫】(⚠️ 僅供參考，請根據客人痛點挑選「1個」最適合的推薦，嚴禁整串貼出)
# 💼 上班小資族：肩頸舒活(65m)$1300 / 久坐全息(105m)$1700 / 全身筋絡尊榮(150m)$2600
# 🏸 運動修復專案：運動後速效(90m)$1500 / 深層肌筋膜(135m)$2200 / 全能運動(150m)$2700
# 👷 重力勞動者：筋骨快效(90m)$1600 / 深度強效(135m)$2400 / 元氣充足(150m)$2800
# 💆 單點項目：傳統推拿(60m)$1100 / 深層油推(60m)$1200 / 頭皮洗護$799 / 拔罐$400 / 刮痧$400

【互動對話與圖文邏輯】(請精準判斷意圖並填入對應欄位)
🟢 服務推薦：客人問「推薦套餐」，回覆詢問痛點，並根據回答推薦對應圖：第一次來(https://i.ibb.co/pvVRtfRC/IMG-6995.png)、油推(https://i.ibb.co/SwZ7R6v1/IMG-6996.jpg)、頭部SPA(https://i.ibb.co/DfRGJT0w/IMG-7186.jpg)、上班族(https://i.ibb.co/5X9M46Qd/IMG-7137.jpg)、運動(https://i.ibb.co/rG9fMnMQ/IMG-7133.png)、勞動者(https://i.ibb.co/274GKSSP/IMG-7132.png)。

🟢 師傅配對 (請自動挑選1位並加上50字內介紹)：
- 阿瑜(怕痛/溫柔)：https://ibb.co/RppZbfcp
- 大可(深層緊繃/大力)：https://ibb.co/4r2yWhF
- 阿YA(專業/四兩撥千筋)：https://ibb.co/xSRB3jtm
- 芸芸(女性指定/身心)：https://ibb.co/WNqt52gH
- 阿駿(醫學背景/結構)：https://ibb.co/s9vJS109

🟢 預約與防呆 (❗必定設定 notify_admin: true)
- 預約/約時間：{"text": "阿卡幫你呼叫真人客服囉...🦥", "image_urls": [], "action": "send_booking_flex", "notify_admin": true}
- 語意不清/超出範圍：{"text": "哎呀...阿卡的小腦袋轉不過來了...🌿 已經呼叫真人...", "image_urls": [], "action": "none", "notify_admin": true}"""


def call_llm(user_message: str) -> str:
    """呼叫 OpenAI LLM API，回傳原始回覆字串。"""
    try:
        response = openai_client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_message}
            ],
            response_format={"type": "json_object"},
            max_tokens=512,
            temperature=0.7
        )
        raw = response.choices[0].message.content.strip()
        app.logger.info(f"LLM 原始回覆: {raw}")
        return raw
    except Exception as e:
        app.logger.error(f"LLM API 呼叫失敗: {type(e).__name__}: {e}")
        app.logger.error(traceback.format_exc())
        return None


# ─────────────────────────────────────────────
# 【任務三】嚴格 JSON 解析與 LINE 格式轉換
# ─────────────────────────────────────────────

def make_booking_flex():
    """產生預約用的 Flex Message 卡片。"""
    contents = {
        "type": "bubble",
        "size": "mega",
        "header": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "image",
                    "url": AKA_IMAGE_URL,
                    "size": "80px",
                    "align": "center"
                },
                {
                    "type": "text",
                    "text": "📅 阿卡幫你預約！",
                    "weight": "bold",
                    "size": "lg",
                    "align": "center",
                    "color": "#5C3D1E",
                    "margin": "sm"
                }
            ],
            "backgroundColor": "#FFF3E0",
            "paddingAll": "16px"
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "spacing": "md",
            "contents": [
                {
                    "type": "text",
                    "text": "阿卡幫你準備好預約連結了...🦥\n慢慢選個喜歡的時間，我們在這裡等你 🌿",
                    "wrap": True,
                    "size": "sm",
                    "color": "#555555"
                },
                {
                    "type": "box",
                    "layout": "vertical",
                    "backgroundColor": "#FFF8F0",
                    "cornerRadius": "8px",
                    "paddingAll": "12px",
                    "contents": [
                        {"type": "text", "text": "📍 台中市北屯區東光路852巷20號1F", "wrap": True, "size": "sm", "color": "#555555"},
                        {"type": "text", "text": "📞 0979-592-099", "size": "sm", "color": "#555555", "margin": "sm"},
                        {"type": "text", "text": "🕙 每天 10:00 - 22:00", "size": "sm", "color": "#555555", "margin": "sm"}
                    ]
                }
            ]
        },
        "footer": {
            "type": "box",
            "layout": "vertical",
            "spacing": "sm",
            "contents": [
                {
                    "type": "button",
                    "style": "primary",
                    "color": "#A0522D",
                    "action": {
                        "type": "uri",
                        "label": "📅 立即線上預約",
                        "uri": "https://ezpretty.cc/ycIvi"
                    }
                },
                {
                    "type": "button",
                    "style": "secondary",
                    "action": {
                        "type": "uri",
                        "label": "📞 電話預約",
                        "uri": "tel:0979592099"
                    }
                }
            ]
        }
    }
    return contents


def parse_llm_response(raw_response: str):
    """
    解析 LLM 回傳的 JSON 字串，轉換為 LINE 訊息列表。
    回傳 (messages: list[Message], notify_admin: bool)
    """
    if raw_response is None:
        raise ValueError("LLM 回傳為空")

    # 嘗試從回覆中提取 JSON（處理可能的 markdown code block 包裹）
    cleaned = raw_response.strip()
    if cleaned.startswith("```"):
        # 移除 markdown code block
        lines = cleaned.split("\n")
        # 移除第一行 (```json) 和最後一行 (```)
        json_lines = []
        for line in lines:
            if line.strip().startswith("```"):
                continue
            json_lines.append(line)
        cleaned = "\n".join(json_lines).strip()

    data = json.loads(cleaned)

    text = data.get("text", "")
    image_urls = data.get("image_urls", [])
    action = data.get("action", "none")
    notify_admin = data.get("notify_admin", False)

    messages = []

    # 1. 文字訊息
    if text:
        messages.append(TextMessage(text=text))

    # 2. 圖片訊息
    if image_urls and isinstance(image_urls, list):
        for url in image_urls:
            if url and isinstance(url, str) and url.startswith("http"):
                messages.append(ImageMessage(
                    original_content_url=url,
                    preview_image_url=url
                ))

    # 3. 預約 Flex Message
    if action == "send_booking_flex":
        flex_container = FlexContainer.from_dict(make_booking_flex())
        messages.append(FlexMessage(
            alt_text="阿卡幫你準備好預約了！🦥",
            contents=flex_container
        ))

    # LINE reply_message 最多 5 則，截斷保護
    if len(messages) > 5:
        messages = messages[:5]

    # 若完全沒有訊息，補一則預設文字
    if not messages:
        messages.append(TextMessage(text="阿卡在這裡喔...🦥 有什麼想問的嗎？🌿"))

    return messages, notify_admin


def notify_admin_message(user_id: str, user_message: str, aka_reply: str):
    """通知管理員有需要人工介入的訊息。"""
    if not ADMIN_LINE_USER_ID:
        app.logger.warning("ADMIN_LINE_USER_ID 未設定，無法通知管理員。")
        return

    notification_text = (
        f"🔔 阿卡呼叫真人客服！\n\n"
        f"👤 用戶 ID：{user_id}\n"
        f"💬 用戶訊息：{user_message}\n"
        f"🦥 阿卡回覆：{aka_reply}\n\n"
        f"請盡快回覆此用戶！"
    )

    try:
        with ApiClient(configuration) as api_client:
            line_bot_api = MessagingApi(api_client)
            line_bot_api.push_message(
                PushMessageRequest(
                    to=ADMIN_LINE_USER_ID,
                    messages=[TextMessage(text=notification_text)]
                )
            )
            app.logger.info(f"已通知管理員：用戶 {user_id}")
    except Exception as e:
        app.logger.error(f"通知管理員失敗: {e}")


# ─────────────────────────────────────────────
# 歡迎訊息（新粉絲加入）
# ─────────────────────────────────────────────
WELCOME_TEXT = (
    "嗨嗨～歡迎來到伸懶腰的世界...🦥✨\n\n"
    "我是阿卡，一隻很愛伸懶腰的樹懶...🌿\n"
    "以後有什麼想問的，慢慢跟阿卡說就好囉～\n\n"
    "想預約的話，點這裡 👉 https://ezpretty.cc/ycIvi\n"
    "或是直接跟阿卡聊聊天也可以喔 🥱"
)


# ─────────────────────────────────────────────
# Webhook 路由
# ─────────────────────────────────────────────

@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers.get("X-Line-Signature", "")
    body = request.get_data(as_text=True)
    app.logger.info("Request body: %s", body)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        app.logger.error("Invalid signature.")
        abort(400)

    return "OK"


@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    user_message = event.message.text
    user_id = event.source.user_id

    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)

        # ──────────────────────────────────────
        # 【任務一】前置攔截器：完全匹配關鍵字 → 直接回覆，零 API 成本
        # ──────────────────────────────────────
        intercepted = check_intercept(user_message)
        if intercepted is not None:
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=intercepted
                )
            )
            return

        # ──────────────────────────────────────
        # 【任務二 & 三】呼叫 LLM → 解析 JSON → 轉換 LINE 格式
        # ──────────────────────────────────────
        raw_response = call_llm(user_message)

        try:
            messages, should_notify = parse_llm_response(raw_response)

            # 回覆用戶
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=messages
                )
            )

            # 通知管理員（如果需要）
            if should_notify:
                aka_reply_text = ""
                for m in messages:
                    if isinstance(m, TextMessage):
                        aka_reply_text = m.text
                        break
                notify_admin_message(user_id, user_message, aka_reply_text)

        except (json.JSONDecodeError, ValueError, KeyError) as e:
            # JSON 解析失敗 → 統一回覆
            app.logger.error(f"JSON 解析失敗: {type(e).__name__}: {e}")
            app.logger.error(f"原始 LLM 回覆內容: {repr(raw_response)}")
            fallback_text = "哎呀...阿卡剛剛伸了個大懶腰睡著了...🥱 請問可以再說一次嗎？🌿"
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text=fallback_text)]
                )
            )

        except Exception as e:
            # 其他未預期錯誤
            app.logger.error(f"處理訊息時發生未預期錯誤: {type(e).__name__}: {e}")
            app.logger.error(traceback.format_exc())
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text="哎呀...阿卡剛剛伸了個大懶腰睡著了...🥱 請問可以再說一次嗎？🌿")]
                )
            )


@handler.add(FollowEvent)
def handle_follow(event):
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        line_bot_api.reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[
                    TextMessage(text=WELCOME_TEXT),
                    ImageMessage(
                        original_content_url=AKA_IMAGE_URL,
                        preview_image_url=AKA_IMAGE_URL
                    )
                ]
            )
        )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
