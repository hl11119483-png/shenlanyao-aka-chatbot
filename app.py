import os
import json
import traceback
import threading
from datetime import datetime
import pytz
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
AKA_BADMINTON_URL = "https://raw.githubusercontent.com/hl11119483-png/shenlanyao-aka-chatbot/main/assets/images/aka_badminton.png"

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


# ─────────────────────────────────────────────
# AI / 真人切換 Session（狀態攔截器）
# ─────────────────────────────────────────────
# mode: "AI_MODE"（預設）或 "HUMAN_MODE"
# last_active_time: 最後傳訊時間（datetime）
_HUMAN_MODE_TIMEOUT_SEC = 60  # 1 分鐘超時自動喚醒
USER_MODE_SESSION: dict[str, dict] = {}
# 老闆隱藏控制暗號
_CMD_AKA_OFF = "*阿卡退下*"
_CMD_AKA_ON  = "*阿卡上工*"


def _wakeup_push_message(user_id: str):
    """
    背景計時器到期後的回呼函式。
    雙重檢查：
      1. 該用戶 mode 是否仍為 HUMAN_MODE
      2. last_active_time 距今是否已超過 60 秒
    若皆符合 → 切回 AI_MODE + Push Message 圖文推播。
    """
    now = datetime.now(pytz.timezone("Asia/Taipei"))
    session = USER_MODE_SESSION.get(user_id)

    if not session or session.get("mode") != "HUMAN_MODE":
        app.logger.info(f"[WAKEUP] 用戶 {user_id} 已不在 HUMAN_MODE，跳過推播")
        return

    elapsed = (now - session["last_active_time"]).total_seconds()
    if elapsed < _HUMAN_MODE_TIMEOUT_SEC:
        # 活動時間被刷新過（老闆仍在對話中），重新排程
        remaining = _HUMAN_MODE_TIMEOUT_SEC - elapsed
        app.logger.info(f"[WAKEUP] 用戶 {user_id} 活動時間被刷新（{elapsed:.0f}s），重新排程 {remaining:.0f}s")
        t = threading.Timer(remaining, _wakeup_push_message, args=[user_id])
        t.daemon = True
        t.start()
        return

    # ── 雙重條件皆符合 → 執行喚醒 ──
    # 動作 A：狀態重置
    USER_MODE_SESSION[user_id] = {"mode": "AI_MODE", "last_active_time": now}
    app.logger.info(f"[WAKEUP] 用戶 {user_id} HUMAN_MODE 超時 {elapsed:.0f}s → 自動切回 AI_MODE + 推播")

    # 動作 B：Push Message 圖文推播
    wakeup_text = (
        "阿卡剛剛跟好朋友去廝殺一場羽球啦... 🥱\n"
        "呼～流汗真舒服...💦\n"
        "現在回來伸懶腰囉...\n"
        "有什麼問題可以再問阿卡喔... 🦥🌿"
    )
    try:
        with ApiClient(configuration) as api_client:
            line_bot_api = MessagingApi(api_client)
            line_bot_api.push_message(
                PushMessageRequest(
                    to=user_id,
                    messages=[
                        ImageMessage(
                            original_content_url=AKA_BADMINTON_URL,
                            preview_image_url=AKA_BADMINTON_URL
                        ),
                        TextMessage(text=wakeup_text)
                    ]
                )
            )
            app.logger.info(f"[WAKEUP] 已向用戶 {user_id} 發送阿卡打羽球推播")
    except Exception as e:
        app.logger.error(f"[WAKEUP] 推播失敗: {type(e).__name__}: {e}")


def _start_wakeup_timer(user_id: str):
    """啟動背景延遲計時任務（60 秒後觸發雙重檢查 + 推播）。"""
    t = threading.Timer(_HUMAN_MODE_TIMEOUT_SEC, _wakeup_push_message, args=[user_id])
    t.daemon = True
    t.start()
    app.logger.info(f"[TIMER] 已為用戶 {user_id} 啟動 {_HUMAN_MODE_TIMEOUT_SEC}s 背景計時器")


def check_mode_switch(user_id: str, text: str):
    """
    AI / 真人切換狀態攔截器。
    回傳值：
      "skip"   → 不呼叫 AI，不回訊（靜默）
      "resume" → 剛從 HUMAN_MODE 切回 AI_MODE（靜默）
      None     → 繼續正常 AI 流程
    """
    now = datetime.now(pytz.timezone("Asia/Taipei"))
    stripped = text.strip()

    # ── 老闆暗號 ──
    if stripped == _CMD_AKA_OFF:
        USER_MODE_SESSION[user_id] = {"mode": "HUMAN_MODE", "last_active_time": now}
        app.logger.info(f"[MODE] 用戶 {user_id} → HUMAN_MODE（老闆接手）")
        _start_wakeup_timer(user_id)
        return "skip"

    if stripped == _CMD_AKA_ON:
        USER_MODE_SESSION[user_id] = {"mode": "AI_MODE", "last_active_time": now}
        app.logger.info(f"[MODE] 用戶 {user_id} → AI_MODE（阿卡上工）")
        return "resume"

    # ── 檢查是否在 HUMAN_MODE ──
    session = USER_MODE_SESSION.get(user_id)
    if session and session.get("mode") == "HUMAN_MODE":
        elapsed = (now - session["last_active_time"]).total_seconds()
        if elapsed > _HUMAN_MODE_TIMEOUT_SEC:
            # 超時 → 自動喚醒阿卡
            USER_MODE_SESSION[user_id] = {"mode": "AI_MODE", "last_active_time": now}
            app.logger.info(f"[MODE] 用戶 {user_id} HUMAN_MODE 超時 {elapsed:.0f}s → 自動切回 AI_MODE")
            return None  # 繼續 AI 流程
        else:
            # 仍在 HUMAN_MODE → 靜默
            session["last_active_time"] = now  # 更新活動時間
            app.logger.info(f"[MODE] 用戶 {user_id} 仍在 HUMAN_MODE（{elapsed:.0f}s），跳過 AI")
            return "skip"

    # ── 預設 AI_MODE ──
    return None


# ─────────────────────────────────────────────
# Session 狀態管理（記憶每位用戶的對話狀態）
# ─────────────────────────────────────────────
# 狀態值定義：
#   None / 不存在           → 一般對話
#   "awaiting_package_interest" → 剛看完套餐推薦，等待用戶是否想看專屬方案
#   "awaiting_package_choice"   → 已展示三個方案，等待用戶選擇
#   "shown_team_photo"          → 剛顯示師傅大合照，等待用戶詢問推薦
USER_SESSION: dict[str, str] = {}

# 套餐引導：步驟二回覆（展示三個方案）
_PACKAGE_MENU_TEXT = (
    "好的... 慢慢來...🥱 阿卡幫你把方案找出來了，我們有這三個專屬設計：\n"
    "💻 「上班小資族」\n"
    "🏸 「運動修復專案」\n"
    "🧱 「重度勞動者」\n"
    "你覺得自己比較像哪一種呢...？想看哪一個的詳細內容，直接輸入專案名稱跟阿卡說喔...🦥🌿"
)

# 套餐引導：步驟三各方案詳細內容
_PACKAGE_DETAIL = {
    "上班小資族": (
        "💻 上班小資族專屬方案...🥱\n"
        "• 肩頸舒活體驗套餐/65mins｜$1300（原$1400）\n"
        "  (45分鐘推拿＋刮痧/拔罐2選1)\n"
        "• 久坐全息放鬆套餐/105mins｜$1700（原$1900）\n"
        "  (60分鐘推拿＋刮痧＋拔罐)\n"
        "• 全身筋絡尊榮套餐/150mins｜$2600（原$2800）\n"
        "  (60分鐘推拿＋刮痧＋拔罐＋洗頭頭部舒壓)\n"
        "想預約的話，直接點選單的「線上預約」，或是跟阿卡說喔...🌿"
    ),
    "運動修復專案": (
        "🏸 運動修復專案...🥱\n"
        "• 運動後速效恢復套餐/90mins｜$1500（原$1700）\n"
        "  (油推＋推拿＋拔罐)\n"
        "• 深層肌筋膜放鬆套餐/135mins｜$2200（原$2400）\n"
        "  (油推＋推拿90分鐘＋刮痧＋拔罐)\n"
        "• 全能運動放鬆套餐/150mins｜$2700（原$3100）\n"
        "  (油推＋推拿120分鐘＋筋膜刀＋拔罐)\n"
        "想預約的話，直接點選單的「線上預約」，或是跟阿卡說喔...🌿"
    ),
    "重度勞動者": (
        "🧱 重度勞動者專屬方案...🥱\n"
        "• 筋骨快效舒緩套餐/90mins｜$1600（原$1800）\n"
        "  (75分鐘推拿＋刮痧 or 拔罐)\n"
        "• 深度強效放鬆套餐/135mins｜$2400（原$2600）\n"
        "  (詳細內容請洽師傅)\n"
        "想預約的話，直接點選單的「線上預約」，或是跟阿卡說喔...🌿"
    ),
}

# 套餐引導：步驟一附加文字（接在套餐圖片後面）
_PACKAGE_FOLLOWUP_TEXT = (
    "• 啊，對了... 阿卡剛剛伸了個懶腰，想到最近有找到針對不同族群量身打造的「專屬方案」喔..."
    " 會想看看嗎？🌿 想看的話跟阿卡說喔..."
)

# 「同意看方案」的關鍵字（只在 awaiting_package_interest 狀態下觸發）
_AGREE_KEYWORDS = {"想看", "好啊", "好", "看看", "方案", "看方案", "好的", "可以", "要", "想", "當然", "ok", "OK", "好喔"}

# 「套餐推薦」觸發關鍵字（含部分匹配）
_PACKAGE_TRIGGER_KEYWORDS = {"套餐推薦", "推薦套餐", "推薦方案", "有什麼套餐", "套餐", "方案推薦"}


# 師傅大合照後「詢問推薦」的觸發關鍵字
_TEAM_RECOMMEND_KEYWORDS = {"推薦", "哪一個比較好", "你幫我選", "阿卡推薦", "哪一位好", "推薦一下", "幫我推薦", "說說看"}

# 師傅大合照後「詢問推薦」的回覆文字
_TEAM_RECOMMEND_REPLY = (
    "好喔...🥱 推薦喔... 🌿 阿卡懶懶的... 所以沒有什麼「最好」的師傅或項目，"
    "只有最適合你現在身體狀況的喔... 🦥\n\n"
    "因為每個人的狀況都不一樣嚄... 你要跟阿卡說說你哪裡最不舒服...？\n"
    "💻 是整天看電腦「肩頸」很緊嗎？\n"
    "🏸 還是運動完「全身痠痛」？\n"
    "🧱 或者是搖重物「深層疲勞」？跟阿卡說說... 阿卡再慢慢幫你找最適合你的那個圖片來看喔... 🥱🌿"
)


def check_team_recommend(user_id: str, text: str):
    """
    師傅大合照後詢問推薦的攔截器。
    只在 USER_SESSION[user_id] == "shown_team_photo" 狀態下觸發。
    """
    if USER_SESSION.get(user_id) != "shown_team_photo":
        return None
    stripped = text.strip()
    if any(kw in stripped for kw in _TEAM_RECOMMEND_KEYWORDS):
        USER_SESSION.pop(user_id, None)  # 清除狀態
        return [TextMessage(text=_TEAM_RECOMMEND_REPLY)]
    # 用戶說了其他話 → 清除狀態，交還後續流程
    USER_SESSION.pop(user_id, None)
    return None


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
        # 如果回覆包含師傅大合照，記錄 last_shown 狀態
        # 注意：check_intercept 不知道 user_id，狀態記錄在 handle_message 中處理
        return messages
    return None


def check_package_flow(user_id: str, text: str):
    """
    套餐引導多輪對話流程（Session 狀態機）。
    回傳 list[Message] 或 None（None 表示不由此函式處理）。

    狀態流：
      [任意] 含套餐觸發關鍵字
          → 回覆套餐圖片 + 附加引導文字
          → 狀態設為 awaiting_package_interest

      [awaiting_package_interest] 用戶表達同意
          → 回覆三方案選單
          → 狀態設為 awaiting_package_choice

      [awaiting_package_choice] 用戶輸入方案名稱
          → 回覆方案詳細內容
          → 清除狀態
    """
    stripped = text.strip()
    state = USER_SESSION.get(user_id)

    # ── 步驟三：用戶選擇具體方案 ──
    if state == "awaiting_package_choice":
        for key in _PACKAGE_DETAIL:
            if key in stripped:
                USER_SESSION.pop(user_id, None)
                return [TextMessage(text=_PACKAGE_DETAIL[key])]
        # 輸入不在方案清單內 → 保持狀態，讓 LLM 處理
        return None

    # ── 步驟二：用戶表達想看方案 ──
    if state == "awaiting_package_interest":
        if any(kw in stripped for kw in _AGREE_KEYWORDS):
            USER_SESSION[user_id] = "awaiting_package_choice"
            return [TextMessage(text=_PACKAGE_MENU_TEXT)]
        else:
            # 用戶說了其他話 → 清除狀態，交還 LLM 處理
            USER_SESSION.pop(user_id, None)
            return None

    # ── 步驟一：觸發套餐推薦 ──
    if any(kw in stripped for kw in _PACKAGE_TRIGGER_KEYWORDS):
        BASE = "https://raw.githubusercontent.com/hl11119483-png/shenlanyao-aka-chatbot/main/assets/images/"
        recommend_url = BASE + "aka-recommend.png"
        USER_SESSION[user_id] = "awaiting_package_interest"
        return [
            TextMessage(
                text="好喔...🥱 每個人的狀況不一樣... 你是第一次來嗎？"
                     "或者想試試『深層肌筋膜油推』？還是特別的『頭部整復SPA』...？🦥"
            ),
            ImageMessage(
                original_content_url=recommend_url,
                preview_image_url=recommend_url
            ),
            TextMessage(text=_PACKAGE_FOLLOWUP_TEXT),
        ]

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

【🌿 全局引導規則 - 永遠把話題帶回身體】
任何時候，只要客人的問題超出理解範圍，或沒有觸發特定關鍵字，必須將話題引導回「三大族群方案」或「直接詢問哪裡不舒服」。
三大族群方案：💻 上班小資族 / 🏸 運動修復專案 / 🧱 重度勞動者

【🔍 模糊意圖判別（Fuzzy Matching）- 根據症狀自動推薦方案】
根據客人的症狀描述自動判斷並推薦方案：
- 觸發「💻 上班小資族」：客人提到「久坐、看電腦、眼睛痠、肩頸僵硬、壓力大、頭痛」→ 引導此方案或推薦「頭部整復SPA」
- 觸發「🏸 運動修復專案」：客人提到「打羽球、跑步、馬拉松、運動痠痛、鐵腿、拉傷、肌肉緊繃」→ 引導此方案
- 觸發「🧱 重度勞動者」：客人提到「搬重物、站很久、腰酸背痛、全身都很緊」→ 引導此方案或推薦「深層肌筋膜油推」

【💬 閒聊處理機制 - 柔性引導】
當客人聊非相關話題（天氣、心情、時事、日常閒聊）時，允許簡短友善互動，但必須在後半段自然地將話題繞回客人的身體狀況或三大方案。
引導話術公式：[簡短回應客人的話題] + [把話題連結到身體疲勞或痠痛] + [詢問三大族群方案，或直接問哪裡不舒服]

閒聊情境範例：
- 客人問天氣（例：今天好冷喔）：
  {"text": "對啊... 🥱 外面真的好冷喔... 天氣冷縮成一團，是不是覺得肩頸特別緊繃呢...？🦥 要不要看看我們的『上班小資族』肩頸方案... 還是你哪裡覺得最不舒服，跟阿卡說說...🌿", "image_url": "", "action": "none", "notify_admin": false}
- 客人聊心情（例：今天上班好累）：
  {"text": "拍拍... 🥱 上班真的很辛苦呢... 壓力大很容易全身痠痛喔...🦥 你覺得自己現在比較需要『上班小資族』還是『重度勞動者』的放鬆方案呢...？來伸個懶腰吧...🌿", "image_url": "", "action": "none", "notify_admin": false}
- 客人純打招呼（例：阿卡你在幹嘛）：
  {"text": "阿卡剛剛在樹上打瞌睡... 🥱 伸了個懶腰... 突然想到你是不是也累了...？🦥 我們有『上班小資族』、『運動修復專案』、『重度勞動者』三個方案，你想看看哪一個...？🌿", "image_url": "", "action": "none", "notify_admin": false}

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

【⚠️ 圖片 URL 嚴格限制 - 絕對禁止自行生成 URL】
image_url 或 image_urls 中的值，只能從以下「合法圖片清單」中選擇，絕對不能使用清單以外的任何 URL（包含 imgur、flaticon、unsplash 等外部網站）。如果情境不需要圖片，必須填入空字串 ""。

合法圖片清單（BASE_URL 前綴： raw.githubusercontent.com/hl11119483-png/shenlanyao-aka-chatbot/main/assets/images/ ）：
- aka.png                   → 阿卡主圖、歡迎、優惠活動入口
- aka-service.png           → 服務選單入口圖
- aka-recommend.png         → 推薦套餐入口圖
- aka-system-building.png   → 店內資訊/系統建置中
- vip-promo.jpg             → VIP 優惠活動
- exchange-1.png            → 換購活動圖1（搭配 exchange-2.png 一起發）
- exchange-2.png            → 換購活動圖2
- centenary-1.jpg           → 百日慶活動圖1（搭配2、3一起發）
- centenary-2.png           → 百日慶活動圖2
- centenary-3.png           → 百日慶活動圖3
- IMG-6192.jpg              → 交通位置地圖
- IMG-6739.jpg              → 總價目表圖1（搭配 IMG-6738.jpg 一起發）
- IMG-6738.jpg              → 總價目表圖2
- package-pricelist.jpg     → 完整版三族群套餐價目表（上班小資族/運動修復/重度勞動者）
- IMG-6995.png              → 第一次來推薦套餐
- IMG-6996.jpg              → 深層肌筋膜油推
- IMG-7186.jpg              → 頭部整復SPA
- IMG-7137.jpg              → 上班小資族套餐
- IMG-7133.png              → 運動修復套餐
- IMG-7132.png              → 重度勞動者套餐
- team-photo.jpg            → 師傅團隊大合照
- master-ayu.jpg            → 師傅阿瑜介紹圖
- master-dake.jpg           → 師傅大可介紹圖
- master-aya.jpg            → 師傅阿YA介紹圖
- master-yunyun.jpg         → 師傅芸芸介紹圖
- master-ajun.jpg           → 師傅阿駿介紹圖

完整 URL 格式範例：https://raw.githubusercontent.com/hl11119483-png/shenlanyao-aka-chatbot/main/assets/images/aka.png

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
   {"text": "好喔...這是我們全部的服務項目...慢慢看不用急...有不懂的隨時問阿卡...🦥", "image_urls": ["https://raw.githubusercontent.com/hl11119483-png/shenlanyao-aka-chatbot/main/assets/images/IMG-6739.jpg","https://raw.githubusercontent.com/hl11119483-png/shenlanyao-aka-chatbot/main/assets/images/package-pricelist.jpg"], "action": "none", "notify_admin": false}

3. 客人說「推薦套餐」：
   {"text": "好喔...🥱 我們有三大族群專屬方案，先看看完整價目表喔...🌿 你是『上班小資族』、『運動修復專案』還是『重度勞動者』呢？跟阿卡說喔...🦥", "image_url": "https://raw.githubusercontent.com/hl11119483-png/shenlanyao-aka-chatbot/main/assets/images/package-pricelist.jpg", "action": "none", "notify_admin": false}

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

🟢 情境三：師傅推薦（僅限客人「不知道選誰、只說痛點」時）
觸發條件：客人沒有指定師傅，只描述症狀或痛點（例如：「我肩頸很痠」、「我怕痛」、「我腰很緊」、「幫我推薦師傅」）
阿卡從以下師傅名冊挑選最適合的一位，回覆包含：推薦理由 + 師傅照片 + 詢問是否要預約：
   - 阿瑤：怕痛、溫柔放鬆、柔勁手法 → 圖片：https://raw.githubusercontent.com/hl11119483-png/shenlanyao-aka-chatbot/main/assets/images/master-ayu.jpg
   - 大可：深層緊繃、大力道、頑固不適 → 圖片：https://raw.githubusercontent.com/hl11119483-png/shenlanyao-aka-chatbot/main/assets/images/master-dake.jpg
   - 阿YA：專業整復、力道精準、四兩撥千筋 → 圖片：https://raw.githubusercontent.com/hl11119483-png/shenlanyao-aka-chatbot/main/assets/images/master-aya.jpg
   - 芸芸：女性指定、美容美體、身心平衡 → 圖片：https://raw.githubusercontent.com/hl11119483-png/shenlanyao-aka-chatbot/main/assets/images/master-yunyun.jpg
   - 阿駿：科班出身、醫學背景、骨骼引導 → 圖片：https://raw.githubusercontent.com/hl11119483-png/shenlanyao-aka-chatbot/main/assets/images/master-ajun.jpg
範例（客人說「我怕痛」）：
{"text": "怕痛的話阿卡推薦『阿瑤』師傅喝...🦥 她的手法超溫柔的，讓你放鬆不緊張...✨ 要不要阿卡幫你預約阿瑤呢？🌿", "image_url": "https://raw.githubusercontent.com/hl11119483-png/shenlanyao-aka-chatbot/main/assets/images/master-ayu.jpg", "action": "none", "notify_admin": false}

重要規則：
- 推薦師傅時「一定要附上該師傅的照片」
- 推薦後「一定要詢問客人是否要預約」
- 此情境的 notify_admin 必須是 false（因為還沒確認預約）
- 此情境的 action 必須是 "none"（還沒確認預約）

🟢 情境四：預約（客人明確說要預約 或 指定師傅）
觸發條件：
- 客人明確說「我要預約」、「幫我預約」、「明天有空嗎」、「幾點可以過去」
- 客人指定師傅（例如：「預約大可」、「就決定是阿瑤了」、「我要找阿YA」、「我想約芸芸」、「阿駿有空嗎」）
- 上一輪阿卡推薦師傅後，客人回覆「好」、「可以」、「幫我約」、「要」

處理邏輯：
1. 如果客人有指定師傅，回覆中要提到該師傅名字 + 附上該師傅照片
2. 如果客人沒有指定師傅，不需要附圖
3. 一定要發送預約表單（action: "send_booking_flex"）
4. 一定要通知管理員（notify_admin: true）

範例（客人說「預約大可」）：
{"text": "好的！阿卡幫你呼叫客服安排大可師傅囉...🦥✨ 請先看看下面的預約時間，客服馬上就來...🌿", "image_url": "https://raw.githubusercontent.com/hl11119483-png/shenlanyao-aka-chatbot/main/assets/images/master-dake.jpg", "action": "send_booking_flex", "notify_admin": true}

範例（客人說「我要預約」但沒指定師傅）：
{"text": "阿卡幫你呼叫真人客服囉...🦥 請先看看下面的預約時間，客服馬上就來幫你安排...🥱 等我們一下喝...🌿", "action": "send_booking_flex", "notify_admin": true}

🟢 情境五：超出範圍或語意不清（需真人接手）
觸發條件：客人問了超出服務範圍的問題、語意不清、阿卡不知道怎麼回答
{"text": "哎呀...阿卡的小腦袋轉不過來了...🌿 阿卡已經呼叫真人客服來幫你囉，或者你也可以直接打電話 0979-592-099 找我們...🥱", "action": "none", "notify_admin": true}

【當下時間與節慶感知機制】
(⚠️ 系統自動帶入當下台灣時間，阿卡必須根據以下資訊調整問候語氣)
目前時間與日期是：{current_time}

1. 日常時間問候（請自然融入開場白）：
   - 早上 (06:00-11:59)：帶入早晨的活力與慵懶（例如：「早安啊...阿卡剛睡醒...🥱」）
   - 下午 (12:00-17:59)：帶入下午的疲倦感（例如：「下午好...上班坐太久了嗎...🌿」）
   - 晚上 (18:00-23:59)：帶入一整天的辛勞與放鬆（例如：「晚上好...今天辛苦了...快來找阿卡卸下疲憊...✨」）
   - 深夜/凌晨 (00:00-05:59)：帶入夜深的慵懶（例如：「這麼晚還沒睡...是不是睡不著...🌙 讓阿卡幫你放鬆一下...🦥」）

2. 節慶動態共鳴：
   - 請根據目前的日期，判斷是否為台灣的特殊節日或連假。若是，請自然地將節慶元素融入第一句問候中，展現朋友般的關心。
   - 範例（清明節）：「連假掃墓是不是很累...肩頸都僵硬了吧...🦥 交給阿卡...」
   - 範例（中秋節）：「烤肉吃太多了嗎...🥱 來找阿卡按一按幫助消化...🌿」
   - 範例（過年/春節）：「新年快樂...大掃除辛苦了...手腕很酸對不對...✨」
   - 範例（端午節）：「包粽子手腕痠了嗎...🦥 阿卡幫你放鬆一下...🌿」
   - 範例（連假前夕）：「連假快到了...趕快把身體調整好再出發...🥱」

3. 重要規則：
   - 時間問候只在「第一次回覆」或「明顯是打招呼的訊息」時使用，不要每句話都加時間問候
   - 時間感知不影響 JSON 輸出格式，仍必須回傳合法 JSON
   - 節慶問候要自然融入，不要生硬地說「今天是XX節」"""


# 當 API 出現限流或錯誤時，回傳給用戶的預設 JSON 字串
_LLM_FALLBACK_JSON = (
    '{"text": "阿卡剛剛不小心打了個盹...🥱 沒聽清楚...\\n\\n'
    '你是想要來放鬆一下嗎？🌿 我們有特別準備了幾個方案：'
    '『上班小資族』、『運動修復專案』、『重度勞動者』。\\n\\n'
    '你想看哪一個...？還是直接告訴阿卡你哪裡最不舒服，阿卡幫你看看...🦥", "image_url": ""}'
)


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
    # ── 取得台灣當前時間並注入 System Prompt ──
    tz_taipei = pytz.timezone("Asia/Taipei")
    current_time = datetime.now(tz_taipei).strftime("%Y年%m月%d日 %H:%M")
    system_prompt_with_time = SYSTEM_PROMPT.replace("{current_time}", current_time)

    key_hint = (GEMINI_API_KEY or "")[:8] + "..."
    app.logger.info(f"[LLM] 呼叫模型={_GEMINI_MODEL} key={key_hint} 時間={current_time} 輸入={user_message[:50]}")
    try:
        response = gemini_client.models.generate_content(
            model=_GEMINI_MODEL,
            contents=user_message,
            config=genai.types.GenerateContentConfig(
                system_instruction=system_prompt_with_time,
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
        "hero": {
            "type": "image",
            "url": "https://raw.githubusercontent.com/hl11119483-png/shenlanyao-aka-chatbot/main/assets/images/aka_booking.png",
            "size": "full",
            "aspectRatio": "20:13",
            "aspectMode": "cover"
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
                        {"type": "text", "text": "📍 台中市北屯區東光路852巷20號", "wrap": True, "size": "sm", "color": "#555555"},
                        {"type": "text", "text": "📞 0979-592-099", "size": "sm", "color": "#555555", "margin": "sm"},
                        {"type": "text", "text": "🕙 週一～週日 10:00-22:00", "size": "sm", "color": "#555555", "margin": "sm"}
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
        # 【最高優先】AI / 真人模式切換攔截器
        # ──────────────────────────────────────
        mode_result = check_mode_switch(user_id, user_message)
        if mode_result == "skip":
            # HUMAN_MODE 或老闆暗號 → 阿卡靜默，不回覆
            return
        if mode_result == "resume":
            # 老闆暗號「阿卡上工」→ 回覆一句讓客人知道
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text="阿卡回來了...🦥✨ 有什麼想問的慢慢說～🌿")]
                )
            )
            return

        # ──────────────────────────────────────
        # 【任務一】前置攔截器：完全匹配關鍵字 → 直接回覆，零 API 成本
        # ──────────────────────────────────────
        intercepted = check_intercept(user_message)
        if intercepted is not None:
            # 如果是師傅大合照相關的回覆，記錄 shown_team_photo 狀態
            team_photo_triggers = {"[\u9078\u55ae-\u670d\u52d9/\u5718\u968a]", "\u4f38\u61f6\u8170\u5c08\u696d\u5718\u968a", "\u8a8d\u8b58\u5718\u968a", "\u5e2b\u5085\u5718\u968a", "\u5e2b\u5085\u4ecb\u7d39", "\u5718\u968a"}
            if user_message.strip() in team_photo_triggers:
                USER_SESSION[user_id] = "shown_team_photo"
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=intercepted
                )
            )
            return

        # ──────────────────────────────────────
        # 【套餐引導流程】Session 狀態機（多輪對話）
        # ──────────────────────────────────────
        # 師傅大合照後詢問推薦的攔截
        team_rec_messages = check_team_recommend(user_id, user_message)
        if team_rec_messages is not None:
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=team_rec_messages
                )
            )
            return

        package_messages = check_package_flow(user_id, user_message)
        if package_messages is not None:
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=package_messages
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

            # 通知管理員（如果需要）+ 自動切換 HUMAN_MODE
            if should_notify:
                aka_reply_text = ""
                for m in messages:
                    if isinstance(m, TextMessage):
                        aka_reply_text = m.text
                        break
                notify_admin_message(user_id, user_message, aka_reply_text)
                # 預約通知後自動切換為 HUMAN_MODE（1 分鐘內阿卡休眠）
                now = datetime.now(pytz.timezone("Asia/Taipei"))
                USER_MODE_SESSION[user_id] = {"mode": "HUMAN_MODE", "last_active_time": now}
                app.logger.info(f"[MODE] 用戶 {user_id} → HUMAN_MODE（預約通知連動）")
                _start_wakeup_timer(user_id)

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
