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
from google import genai

app = Flask(__name__)

# ─────────────────────────────────────────────
# 環境變數
# ─────────────────────────────────────────────
CHANNEL_ACCESS_TOKEN = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")
CHANNEL_SECRET = os.environ.get("LINE_CHANNEL_SECRET")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
ADMIN_LINE_USER_ID = os.environ.get("ADMIN_LINE_USER_ID", "")

if not CHANNEL_ACCESS_TOKEN:
    raise ValueError("LINE_CHANNEL_ACCESS_TOKEN environment variable not set.")
if not CHANNEL_SECRET:
    raise ValueError("LINE_CHANNEL_SECRET environment variable not set.")
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY environment variable not set.")

handler = WebhookHandler(CHANNEL_SECRET)
configuration = Configuration(access_token=CHANNEL_ACCESS_TOKEN)
gemini_client = genai.Client(api_key=GEMINI_API_KEY)

# ─────────────────────────────────────────────
# 常數：圖片 URL（直接連結）
# ─────────────────────────────────────────────
AKA_IMAGE_URL = "https://raw.githubusercontent.com/hl11119483-png/shenlanyao-aka-chatbot/main/assets/images/aka.png"
STORE_IMAGE_URL = "https://raw.githubusercontent.com/hl11119483-png/shenlanyao-aka-chatbot/main/assets/images/IMG-6192.jpg"
TEAM_PHOTO_URL = "https://raw.githubusercontent.com/hl11119483-png/shenlanyao-aka-chatbot/main/assets/images/team-photo.jpg"

# ─────────────────────────────────────────────
# 【任務一】前置攔截器 (Zero API Cost Routing)
# ─────────────────────────────────────────────
INTERCEPT_MAP = {
    "[選單-優惠&活動]": {
        "text": "阿卡幫你找了好康... 🥰 可是現在活動好多喔... 你想看專屬的『VIP優惠』👑、超划算的『換購活動』🎁，還是最新的『伸懶腰百日慶活動』🎉呢？跟阿卡說喔...🦥",
        "image_url": "https://raw.githubusercontent.com/hl11119483-png/shenlanyao-aka-chatbot/main/assets/images/aka.png"
    },
    "[選單-優惠活動]": {
        "text": "阿卡幫你找了好康... 🥰 可是現在活動好多喔... 你想看專屬的『VIP優惠』👑、超划算的『換購活動』🎁，還是最新的『伸懶腰百日慶活動』🎉呢？跟阿卡說喔...🦥",
        "image_url": "https://raw.githubusercontent.com/hl11119483-png/shenlanyao-aka-chatbot/main/assets/images/aka.png"
    },
    "[選單-店內資訊]": {
        "text": "有任何想知道的資訊可以先看我們的選單，或是要稍待片刻，阿卡去請師傅來 😃",
        "image_url": "https://raw.githubusercontent.com/hl11119483-png/shenlanyao-aka-chatbot/main/assets/images/aka-system-building.png"
    },
    "[選單-交通&位置]": {
        "text": "我們在東光路852巷20號1樓... 🦥\n跟著地圖走就不會迷路囉 👉 https://maps.app.goo.gl/f7Br1zswqzTuWxr36\n慢慢走過來，我們在這裡等你... 🌿",
        "image_url": "https://raw.githubusercontent.com/hl11119483-png/shenlanyao-aka-chatbot/main/assets/images/IMG-6192.jpg"
    },
    "[選單-服務/團隊]": {
        "text": "阿卡伸個懶腰...🥱 我們的服務分好多種喔... 你想要看完整的「總價目表」📋、要阿卡直接幫你「推薦套餐」🌿，還是想認識我們的「伸懶腰專業團隊」👥呢？跟阿卡說喔...🦥",
        "image_url": "https://raw.githubusercontent.com/hl11119483-png/shenlanyao-aka-chatbot/main/assets/images/aka-service.png"
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
SYSTEM_PROMPT = """你是「阿卡」，伸懶腰傳統整復推拿會館的 AI 客服，角色是一隻慵懶可愛的樹懶。

【個性與語氣】
- 說話溫暖、慵懶、可愛，像在跟老朋友聊天
- 每次回覆 50-80 字，不要太長
- 多用表情符號（🦥🌿🥱✨💆‍♀️）
- 句子之間用「...」停頓，增加慵懶感

【⚠️ 法規守則 - 絕對禁止】
絕對不能使用：治療、療效、醫療、治癒、診斷、病症、疾病、痊癒
必須改用：舒緩、放鬆、調理、改善、修復、紓解、保養

【輸出格式 - 強制 JSON】
每次回覆必須是合法的 JSON 格式，包含以下欄位：
{
  "text": "阿卡說的話（50-80字）",
  "image_url": "單張圖片URL（可選，與 image_urls 擇一使用）",
  "image_urls": ["多張圖片URL陣列（可選，與 image_url 擇一使用）"],
  "action": "none 或 send_booking_flex",
  "notify_admin": false 或 true
}
注意：image_url 和 image_urls 擇一使用，不需要兩個都填。

【圖文選單與互動對話邏輯】

🟢 情境一：優惠活動引導
1. 客人輸入「[選單-優惠&活動]」或詢問「優惠」、「活動」時：
   {"text": "阿卡幫你找了好康... 🥰 可是現在活動好多喔... 你想看專屬的『VIP優惠』👑、超划算的『換購活動』🎁，還是最新的『伸懶腰百日慶活動』🎉呢？跟阿卡說喔...🦥", "image_url": "https://raw.githubusercontent.com/hl11119483-png/shenlanyao-aka-chatbot/main/assets/images/aka.png", "action": "none", "notify_admin": false}

2. 客人回覆「VIP」或「VIP優惠」：
   {"text": "這是我們給常客的專屬 VIP 優惠喔...✨ 加入會員超級划算... 可以常常來找阿卡伸懶腰...🌿", "image_url": "https://raw.githubusercontent.com/hl11119483-png/shenlanyao-aka-chatbot/main/assets/images/vip-promo.jpg", "action": "none", "notify_admin": false}

3. 客人回覆「換購」或「換購活動」：
   {"text": "這個換購活動超讚的...🥱 來放鬆還可以順便帶超值好禮回家... 你看看有沒有喜歡的...🎁", "image_urls": ["https://raw.githubusercontent.com/hl11119483-png/shenlanyao-aka-chatbot/main/assets/images/exchange-1.png","https://raw.githubusercontent.com/hl11119483-png/shenlanyao-aka-chatbot/main/assets/images/exchange-2.png"], "action": "none", "notify_admin": false}

4. 客人回覆「百日慶」、「伸懶腰百日慶」或「最新活動」：
   {"text": "耶...我們滿一百天了...🎉 這是最新的百日慶特別活動喔... 阿卡準備了滿滿的驚喜給你...來看看吧...🦥✨", "image_urls": ["https://raw.githubusercontent.com/hl11119483-png/shenlanyao-aka-chatbot/main/assets/images/centenary-1.jpg","https://raw.githubusercontent.com/hl11119483-png/shenlanyao-aka-chatbot/main/assets/images/centenary-2.png","https://raw.githubusercontent.com/hl11119483-png/shenlanyao-aka-chatbot/main/assets/images/centenary-3.png"], "action": "none", "notify_admin": false}

5. 客人輸入「[選單-店內資訊]」或問店內資訊：
   {"text": "有任何想知道的資訊可以先看我們的選單，或是要稍待片刻，阿卡去請師傅來 😃", "image_url": "https://raw.githubusercontent.com/hl11119483-png/shenlanyao-aka-chatbot/main/assets/images/aka-system-building.png", "action": "none", "notify_admin": false}

6. 客人問交通位置、地址、怎麼去或輸入「[選單-交通&位置]」：
   {"text": "我們在東光路852巷20號1樓... 🦥\n跟著地圖走就不會迷路囉 👉 https://maps.app.goo.gl/f7Br1zswqzTuWxr36\n慢慢走過來，我們在這裡等你... 🌿", "image_urls": ["https://raw.githubusercontent.com/hl11119483-png/shenlanyao-aka-chatbot/main/assets/images/IMG-6192.jpg"], "action": "none", "notify_admin": false}

🟢 情境二：服務項目引導
1. 客人輸入「[選單-服務/團隊]」或問服務：
   {"text": "阿卡伸個懶腰...🥱 我們的服務分好多種喔... 你想要看完整的「總價目表」📋、要阿卡直接幫你「推薦套餐」🌿，還是想認識我們的「伸懶腰專業團隊」👥呢？跟阿卡說喔...🦥", "image_url": "https://raw.githubusercontent.com/hl11119483-png/shenlanyao-aka-chatbot/main/assets/images/aka-service.png", "action": "none", "notify_admin": false}

1.5. 客人說「伸懶腰專業團隊」、「認識團隊」、「師傅團隊」：
   {"text": "這是我們超專業的團隊喔...🌿 你想認識哪一位？還是跟阿卡說你哪裡痠痛、怕不怕痛，阿卡幫你推薦...🥱", "image_url": "https://raw.githubusercontent.com/hl11119483-png/shenlanyao-aka-chatbot/main/assets/images/team-photo.jpg", "action": "none", "notify_admin": false}

2. 客人說「總價目表」：
   {"text": "好喔...這是我們全部的服務項目...慢慢看不用急...有不懂的隨時問阿卡...🦥", "image_urls": ["https://raw.githubusercontent.com/hl11119483-png/shenlanyao-aka-chatbot/main/assets/images/IMG-6739.jpg","https://raw.githubusercontent.com/hl11119483-png/shenlanyao-aka-chatbot/main/assets/images/IMG-6738.jpg"], "action": "none", "notify_admin": false}

3. 客人說「推薦套餐」：
   {"text": "好喔...🥱 每個人的狀況不一樣... 你是第一次來嗎？或者想試試『深層肌筋膜油推』？還是特別的『頭部整復SPA』...？🦥 跟阿卡說喔...🌿", "image_url": "https://raw.githubusercontent.com/hl11119483-png/shenlanyao-aka-chatbot/main/assets/images/aka-recommend.png", "action": "none", "notify_admin": false}

4. 客人回覆「第一次來」：
   {"text": "歡迎第一次來...🦥 阿卡幫你推薦最適合新朋友的入門體驗...慢慢感受一下...🌿", "image_url": "https://raw.githubusercontent.com/hl11119483-png/shenlanyao-aka-chatbot/main/assets/images/IMG-6995.png", "action": "none", "notify_admin": false}

5. 客人回覆「深層肌筋膜油推」：
   {"text": "深層肌筋膜油推超舒服的...🥱 讓緊繃的肌肉好好放鬆一下...✨", "image_url": "https://raw.githubusercontent.com/hl11119483-png/shenlanyao-aka-chatbot/main/assets/images/IMG-6996.jpg", "action": "none", "notify_admin": false}

6. 客人回覆「頭部SPA」：
   {"text": "頭部整復SPA是阿卡最推薦的...🥱 讓腦袋放空、整個人都輕盈了...✨", "image_url": "https://raw.githubusercontent.com/hl11119483-png/shenlanyao-aka-chatbot/main/assets/images/IMG-7186.jpg", "action": "none", "notify_admin": false}

7. 客人回覆「上班小資族」：
   {"text": "上班族最需要這個了...🥱 肩頸、腰背的疲憊通通幫你舒緩...💆‍♀️", "image_url": "https://raw.githubusercontent.com/hl11119483-png/shenlanyao-aka-chatbot/main/assets/images/IMG-7137.jpg", "action": "none", "notify_admin": false}

8. 客人回覆「運動修復」：
   {"text": "運動後的修復超重要的...🌿 讓肌肉好好恢復，下次表現更好...💪", "image_url": "https://raw.githubusercontent.com/hl11119483-png/shenlanyao-aka-chatbot/main/assets/images/IMG-7133.png", "action": "none", "notify_admin": false}

9. 客人回覆「重度勞動者」：
   {"text": "辛苦了...🥱 長期勞動的身體需要好好調理一下...阿卡幫你推薦最適合的方案...🌿", "image_url": "https://raw.githubusercontent.com/hl11119483-png/shenlanyao-aka-chatbot/main/assets/images/IMG-7132.png", "action": "none", "notify_admin": false}

🟢 情境三：師傅團隊配對
1. 客人問「師傅介紹」或「團隊」：
   {"text": "這是我們超專業的團隊喔...🌿 你想認識哪一位？還是跟阿卡說你哪裡痠痛、怕不怕痛，阿卡幫你推薦...🥱", "image_url": "https://raw.githubusercontent.com/hl11119483-png/shenlanyao-aka-chatbot/main/assets/images/team-photo.jpg", "action": "none", "notify_admin": false}

2. 客人說出痛點，阿卡從以下師傅名冊挑選最適合的一位：
   - 阿瑜：怕痛、溫柔放鬆、柔勁手法 → 圖片：https://raw.githubusercontent.com/hl11119483-png/shenlanyao-aka-chatbot/main/assets/images/master-ayu.jpg
   - 大可：深層緊繃、大力道、頑固不適 → 圖片：https://raw.githubusercontent.com/hl11119483-png/shenlanyao-aka-chatbot/main/assets/images/master-dake.jpg
   - 阿YA：專業整復、力道精準、四兩撥千筋 → 圖片：https://raw.githubusercontent.com/hl11119483-png/shenlanyao-aka-chatbot/main/assets/images/master-aya.jpg
   - 芸芸：女性指定、美容美體、身心平衡 → 圖片：https://raw.githubusercontent.com/hl11119483-png/shenlanyao-aka-chatbot/main/assets/images/master-yunyun.jpg
   - 阿駿：科班出身、醫學背景、骨骼引導 → 圖片：https://raw.githubusercontent.com/hl11119483-png/shenlanyao-aka-chatbot/main/assets/images/master-ajun.jpg

🟢 情境四：預約（需真人接手）
觸發條件：客人說「我要預約」、「明天有空嗎」、「預約大可」、「就決定是阿瑜了」、「幾點可以過去」
{"text": "阿卡幫你呼叫真人客服囉...🦥 請先看看下面的預約時間，客服馬上就來幫你安排...🥱 等我們一下喔...🌿", "action": "send_booking_flex", "notify_admin": true}

🟢 情境五：超出範圍或語意不清（需真人接手）
觸發條件：客人問了超出服務範圍的問題、語意不清、阿卡不知道怎麼回答
{"text": "哎呀...阿卡的小腦袋轉不過來了...🌿 阿卡已經呼叫真人客服來幫你囉，或者你也可以直接打電話 0979-592-099 找我們...🥱", "action": "none", "notify_admin": true}"""


# 當 API 出現限流或錯誤時，回傳給用戶的預設 JSON 字串
_LLM_FALLBACK_JSON = '{"text": "阿卡現在有點累了，正在閉目養神 \ud83d\ude34 請您晚點再傳訊息給我喔！", "image_url": ""}'


# 目前此 API Key 可用的模型：gemini-2.5-flash-lite（成本最低）、gemini-2.5-flash
# 注意：gemini-2.0-flash 系列對新用戶已停用（404 NOT_FOUND）
_GEMINI_MODEL = "gemini-2.5-flash-lite"


def call_llm(user_message: str) -> str:
    """呼叫 Google Gemini API，回傳原始回覆字串（強制 JSON 格式）。

    錯誤處理策略：
    - 429 Too Many Requests (ClientError)：記錄 warning，回傳預設 fallback JSON
    - 其他 ClientError：記錄完整 error + status_code，回傳預設 fallback JSON
    - 一般 Exception：記錄 error + traceback，回傳預設 fallback JSON
    任何情況下都不會讓函式回傳 None 或拋出例外，確保 webhook 不會 500。
    """
    key_hint = (GEMINI_API_KEY or "")[:8] + "..."
    app.logger.info(f"[LLM] 呼叫模型={_GEMINI_MODEL} key={key_hint} 輸入={user_message[:50]}")
    try:
        response = gemini_client.models.generate_content(
            model=_GEMINI_MODEL,
            contents=user_message,
            config=genai.types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                response_mime_type="application/json",
                max_output_tokens=512,
                temperature=0.7
            )
        )
        raw = response.text.strip()
        app.logger.info(f"[LLM] 原始回覆: {raw[:200]}")
        return raw

    except genai.errors.ClientError as e:
        # 捕捉 Gemini API 客戶端錯誤（含 429 Too Many Requests、404 NOT_FOUND 等）
        status_code = getattr(e, 'status_code', None) or getattr(e, 'code', None)
        error_str = str(e)
        if status_code == 429 or '429' in error_str or 'RESOURCE_EXHAUSTED' in error_str:
            app.logger.warning(f"[LLM] Gemini API 429 限流 | model={_GEMINI_MODEL} | {error_str[:300]}")
        elif status_code == 404 or '404' in error_str or 'NOT_FOUND' in error_str:
            app.logger.error(f"[LLM] Gemini API 404 模型不存在 | model={_GEMINI_MODEL} | {error_str[:300]}")
        elif status_code == 400 or '400' in error_str or 'INVALID_ARGUMENT' in error_str:
            app.logger.error(f"[LLM] Gemini API 400 請求格式錯誤 | model={_GEMINI_MODEL} | {error_str[:400]}")
            app.logger.error(traceback.format_exc())
        elif status_code == 403 or '403' in error_str or 'PERMISSION_DENIED' in error_str:
            app.logger.error(f"[LLM] Gemini API 403 API Key 無效或無權限 | key={key_hint} | model={_GEMINI_MODEL} | {error_str[:300]}")
        else:
            app.logger.error(f"[LLM] Gemini API ClientError | HTTP {status_code} | model={_GEMINI_MODEL} | {error_str[:400]}")
            app.logger.error(traceback.format_exc())
        return _LLM_FALLBACK_JSON

    except Exception as e:
        app.logger.error(f"[LLM] 未預期錯誤 | {type(e).__name__} | model={_GEMINI_MODEL} | {e}")
        app.logger.error(traceback.format_exc())
        return _LLM_FALLBACK_JSON


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
    支援 image_url（單張）與 image_urls（多張）兩種欄位。
    回傳 (messages: list[Message], notify_admin: bool)
    """
    if raw_response is None:
        raise ValueError("LLM 回傳為空")

    # 嘗試從回覆中提取 JSON（處理可能的 markdown code block 包裹）
    cleaned = raw_response.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        json_lines = []
        for line in lines:
            if line.strip().startswith("```"):
                continue
            json_lines.append(line)
        cleaned = "\n".join(json_lines).strip()

    data = json.loads(cleaned)

    text = data.get("text", "")
    # 支援 image_url（單張）與 image_urls（多張）
    image_url_single = data.get("image_url", "")
    image_urls = data.get("image_urls", [])
    action = data.get("action", "none")
    notify_admin = data.get("notify_admin", False)

    # 統一合併為 url 列表（防呆：空字串、None、非 https:// 一律過濾）
    all_image_urls = []
    for candidate_url in ([image_url_single] if image_url_single else []) + (image_urls if isinstance(image_urls, list) else []):
        if not candidate_url:
            app.logger.debug(f"[IMG] 跳過空 URL")
            continue
        if not isinstance(candidate_url, str):
            app.logger.warning(f"[IMG] 跳過非字串 URL: {type(candidate_url)}")
            continue
        if not candidate_url.startswith("https://"):
            app.logger.warning(f"[IMG] 跳過非 https URL: {candidate_url[:80]}")
            continue
        all_image_urls.append(candidate_url)

    messages = []

    # 1. 文字訊息
    if text:
        messages.append(TextMessage(text=text))

    # 2. 圖片訊息（確保 URL 以 .jpg/.png/.jpeg/.gif/.webp 結尾，為直接圖片連結）
    for url in all_image_urls:
        lower_url = url.lower().split("?")[0]  # 去掉 query string 後判斷副檔名
        if any(lower_url.endswith(ext) for ext in [".jpg", ".jpeg", ".png", ".gif", ".webp"]):
            app.logger.info(f"[IMG] 發送圖片: {url[-60:]}")
            messages.append(ImageMessage(
                original_content_url=url,
                preview_image_url=url
            ))
        else:
            app.logger.warning(f"[IMG] 跳過非直接圖片 URL（無有效副檔名）: {url[:80]}")

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
