import os
import json
from flask import Flask, request, abort
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    Configuration, ApiClient, MessagingApi,
    ReplyMessageRequest, TextMessage, FlexMessage, FlexContainer,
    ImageMessage
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent, FollowEvent

from aka_chatbot import AkaChatbot

app = Flask(__name__)

# LINE Bot settings from environment variables
CHANNEL_ACCESS_TOKEN = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")
CHANNEL_SECRET = os.environ.get("LINE_CHANNEL_SECRET")

if not CHANNEL_ACCESS_TOKEN:
    raise ValueError("LINE_CHANNEL_ACCESS_TOKEN environment variable not set.")
if not CHANNEL_SECRET:
    raise ValueError("LINE_CHANNEL_SECRET environment variable not set.")

handler = WebhookHandler(CHANNEL_SECRET)
configuration = Configuration(access_token=CHANNEL_ACCESS_TOKEN)

# Initialize AkaChatbot
chatbot = AkaChatbot()

# 阿卡樹懶圖片公開 URL
AKA_IMAGE_URL = "https://files.manuscdn.com/user_upload_by_module/session_file/310519663447761468/ahewqFUOpDmcmiVR.png"

# 師傅團隊圖片 URL（整合大圖）
TEAM_PHOTO_URL = "https://files.manuscdn.com/user_upload_by_module/session_file/310519663447761468/khwFxrNikKnqVKKO.png"

# 五位師傅個人照片 URL
MASTER_PHOTOS = [
    {
        "name": "芸芸",
        "slogan": "啟動舒緩，回歸平衡",
        "specialty": "國家美容技術士技能檢定（乙/丙級），超過五年扎實整復推拿經驗",
        "url": "https://files.manuscdn.com/user_upload_by_module/session_file/310519663447761468/uFkmmbvdIBMNoHFn.jpeg"
    },
    {
        "name": "大可",
        "slogan": "智慧洞察，突破不適",
        "specialty": "台灣推拿整復協會養生保健證書、進階專業證書，抓準肌骨問題核心",
        "url": "https://files.manuscdn.com/user_upload_by_module/session_file/310519663447761468/NEddHqscbWyTHcVp.jpeg"
    },
    {
        "name": "阿YA",
        "slogan": "柔式手法，壓力釋放",
        "specialty": "民俗調理業傳統整復推拿技術士、A-Team柔式推拿菁英，肘法柔緊繃",
        "url": "https://files.manuscdn.com/user_upload_by_module/session_file/310519663447761468/CFbTUaBoElbylCwi.jpeg"
    },
    {
        "name": "阿駿",
        "slogan": "科班底蘊，重塑平衡",
        "specialty": "仁德醫專復健科專科畢業，學徒手藝三年、健祥中醫診所四年",
        "url": "https://files.manuscdn.com/user_upload_by_module/session_file/310519663447761468/fTGSxmHKrRjqbhKM.jpeg"
    },
    {
        "name": "阿瑜",
        "slogan": "溫柔以待，自在生活",
        "specialty": "民俗調理業傳統整復推拿技術士、摩根整復大師班，持證柔勁專業",
        "url": "https://files.manuscdn.com/user_upload_by_module/session_file/310519663447761468/sfGLVFotcndajTda.jpeg"
    },
]

# ─────────────────────────────────────────────
# Flex Message 卡片建立函式
# ─────────────────────────────────────────────

def make_service_flex():
    """服務介紹卡片"""
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
                    "text": "🦥 阿卡為你介紹服務！",
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
                    "type": "box",
                    "layout": "horizontal",
                    "contents": [
                        {"type": "text", "text": "💆", "size": "xl", "flex": 0},
                        {
                            "type": "box",
                            "layout": "vertical",
                            "flex": 1,
                            "margin": "sm",
                            "contents": [
                                {"type": "text", "text": "傳統整復推拿", "weight": "bold", "color": "#5C3D1E", "size": "md"},
                                {"type": "text", "text": "針對骨骼、肌肉、筋膜調整，舒展筋骨促進循環", "wrap": True, "size": "sm", "color": "#888888"}
                            ]
                        }
                    ]
                },
                {"type": "separator"},
                {
                    "type": "box",
                    "layout": "horizontal",
                    "contents": [
                        {"type": "text", "text": "🌿", "size": "xl", "flex": 0},
                        {
                            "type": "box",
                            "layout": "vertical",
                            "flex": 1,
                            "margin": "sm",
                            "contents": [
                                {"type": "text", "text": "深層肌筋膜油推", "weight": "bold", "color": "#5C3D1E", "size": "md"},
                                {"type": "text", "text": "天然植物精油結合深層手法，身心全面放鬆", "wrap": True, "size": "sm", "color": "#888888"}
                            ]
                        }
                    ]
                },
                {"type": "separator"},
                {
                    "type": "box",
                    "layout": "horizontal",
                    "contents": [
                        {"type": "text", "text": "🔴", "size": "xl", "flex": 0},
                        {
                            "type": "box",
                            "layout": "vertical",
                            "flex": 1,
                            "margin": "sm",
                            "contents": [
                                {"type": "text", "text": "刮痧 / 拔罐", "weight": "bold", "color": "#5C3D1E", "size": "md"},
                                {"type": "text", "text": "促進局部循環，快速舒緩悶脹緊繃感", "wrap": True, "size": "sm", "color": "#888888"}
                            ]
                        }
                    ]
                },
                {"type": "separator"},
                {
                    "type": "box",
                    "layout": "horizontal",
                    "contents": [
                        {"type": "text", "text": "💇", "size": "xl", "flex": 0},
                        {
                            "type": "box",
                            "layout": "vertical",
                            "flex": 1,
                            "margin": "sm",
                            "contents": [
                                {"type": "text", "text": "頭部 SPA 整復", "weight": "bold", "color": "#5C3D1E", "size": "md"},
                                {"type": "text", "text": "頭部氣節疏通 + 肩頸放鬆，神清氣爽", "wrap": True, "size": "sm", "color": "#888888"}
                            ]
                        }
                    ]
                }
            ]
        },
        "footer": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "button",
                    "style": "primary",
                    "color": "#A0522D",
                    "action": {
                        "type": "uri",
                        "label": "📅 立即預約",
                        "uri": "https://ezpretty.cc/ycIvi"
                    }
                }
            ]
        }
    }
    return contents


def make_promotion_flex():
    """優惠活動卡片"""
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
                    "text": "🎉 阿卡帶來最新優惠！",
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
                    "text": "🌟 集點好禮",
                    "weight": "bold",
                    "color": "#A0522D",
                    "size": "md"
                },
                {
                    "type": "text",
                    "text": "消費滿 $1,000 贈 1 點，累積點數換好禮！",
                    "wrap": True,
                    "size": "sm",
                    "color": "#555555"
                },
                {
                    "type": "text",
                    "text": "滿 3 點 → 薑黃艾草貼布 加價購 $150\n滿 6 點 → 石墨烯眼罩 加價購 $1,200\n滿 10 點 → 護髮素 加價購 $999",
                    "wrap": True,
                    "size": "sm",
                    "color": "#888888"
                },
                {"type": "separator"},
                {
                    "type": "text",
                    "text": "💎 套餐優惠",
                    "weight": "bold",
                    "color": "#A0522D",
                    "size": "md"
                },
                {
                    "type": "text",
                    "text": "上班族肩頸套餐 65分鐘 $1,300（原$1,400）\n運動速效恢復套餐 90分鐘 $1,500（原$1,700）\n全身筋絡尊榮套餐 150分鐘 $2,600（原$2,800）",
                    "wrap": True,
                    "size": "sm",
                    "color": "#888888"
                },
                {"type": "separator"},
                {
                    "type": "text",
                    "text": "👑 VIP 會員方案",
                    "weight": "bold",
                    "color": "#A0522D",
                    "size": "md"
                },
                {
                    "type": "text",
                    "text": "月付 $999 起，每月享免費推拿 + 生日好禮！",
                    "wrap": True,
                    "size": "sm",
                    "color": "#888888"
                }
            ]
        },
        "footer": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "button",
                    "style": "primary",
                    "color": "#A0522D",
                    "action": {
                        "type": "uri",
                        "label": "📅 立即預約享優惠",
                        "uri": "https://ezpretty.cc/ycIvi"
                    }
                }
            ]
        }
    }
    return contents


def make_store_info_flex():
    """店內資訊卡片"""
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
                    "text": "🏠 伸懶腰傳統整復推拿會館",
                    "weight": "bold",
                    "size": "md",
                    "align": "center",
                    "color": "#5C3D1E",
                    "margin": "sm",
                    "wrap": True
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
                    "type": "box",
                    "layout": "baseline",
                    "spacing": "sm",
                    "contents": [
                        {"type": "text", "text": "📍", "size": "sm", "flex": 0},
                        {"type": "text", "text": "台中市北屯區東光路852巷20號1F", "wrap": True, "size": "sm", "flex": 5, "color": "#555555"}
                    ]
                },
                {
                    "type": "box",
                    "layout": "baseline",
                    "spacing": "sm",
                    "contents": [
                        {"type": "text", "text": "📞", "size": "sm", "flex": 0},
                        {"type": "text", "text": "0979-592-099", "size": "sm", "flex": 5, "color": "#555555"}
                    ]
                },
                {
                    "type": "box",
                    "layout": "baseline",
                    "spacing": "sm",
                    "contents": [
                        {"type": "text", "text": "🕙", "size": "sm", "flex": 0},
                        {"type": "text", "text": "每天 10:00 - 22:00", "size": "sm", "flex": 5, "color": "#555555"}
                    ]
                },
                {"type": "separator"},
                {
                    "type": "text",
                    "text": "💳 支付方式",
                    "weight": "bold",
                    "color": "#A0522D",
                    "size": "md"
                },
                {
                    "type": "text",
                    "text": "現金 / 轉帳 / LINE Pay / 全支付 / 無卡分期",
                    "wrap": True,
                    "size": "sm",
                    "color": "#888888"
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
                        "label": "📅 線上預約",
                        "uri": "https://ezpretty.cc/ycIvi"
                    }
                },
                {
                    "type": "button",
                    "style": "secondary",
                    "action": {
                        "type": "uri",
                        "label": "📞 撥打電話",
                        "uri": "tel:0979592099"
                    }
                }
            ]
        }
    }
    return contents


def make_traffic_flex():
    """交通與停車資訊卡片"""
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
                    "text": "🚗 交通 & 停車資訊",
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
                    "type": "box",
                    "layout": "baseline",
                    "spacing": "sm",
                    "contents": [
                        {"type": "text", "text": "📍", "size": "sm", "flex": 0},
                        {"type": "text", "text": "台中市北屯區東光路852巷20號1F", "wrap": True, "size": "sm", "flex": 5, "color": "#555555"}
                    ]
                },
                {"type": "separator"},
                {
                    "type": "text",
                    "text": "🅿️ 停車方式",
                    "weight": "bold",
                    "color": "#A0522D",
                    "size": "md"
                },
                {
                    "type": "text",
                    "text": "🛵 機車：可停店門口\n🚗 路邊停車：東光路沿線（優先）\n⏰ 收費：08:00-18:00，$20/hr（週日多免費）",
                    "wrap": True,
                    "size": "sm",
                    "color": "#888888"
                },
                {"type": "separator"},
                {
                    "type": "text",
                    "text": "🏢 特約停車場",
                    "weight": "bold",
                    "color": "#A0522D",
                    "size": "md"
                },
                {
                    "type": "text",
                    "text": "Acon-eco 台中太原停18停車場\n消費滿 $1,500 折抵1小時\n消費滿 $2,500 折抵2小時",
                    "wrap": True,
                    "size": "sm",
                    "color": "#888888"
                },
                {
                    "type": "text",
                    "text": "💡 小撇步：可用「台中交通網」App 查空位！",
                    "wrap": True,
                    "size": "sm",
                    "color": "#A0522D",
                    "margin": "sm"
                }
            ]
        },
        "footer": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "button",
                    "style": "primary",
                    "color": "#A0522D",
                    "action": {
                        "type": "uri",
                        "label": "🗺️ Google Maps 導航",
                        "uri": "https://maps.google.com/?q=台中市北屯區東光路852巷20號1F"
                    }
                }
            ]
        }
    }
    return contents


def make_vip_flex():
    """VIP 會員方案卡片"""
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
                    "text": "👑 VIP 會員專區",
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
                    "type": "box",
                    "layout": "vertical",
                    "backgroundColor": "#FFF8F0",
                    "cornerRadius": "8px",
                    "paddingAll": "12px",
                    "contents": [
                        {
                            "type": "text",
                            "text": "方案一：輕量保養",
                            "weight": "bold",
                            "color": "#A0522D",
                            "size": "md"
                        },
                        {
                            "type": "text",
                            "text": "月付 NT$999",
                            "weight": "bold",
                            "size": "xl",
                            "color": "#E8640C"
                        },
                        {
                            "type": "text",
                            "text": "✅ 每月 60 分鐘推拿（乙次）\n✅ 升級油壓只加 $100\n✅ 入會贈 $100 儲值金",
                            "wrap": True,
                            "size": "sm",
                            "color": "#555555",
                            "margin": "sm"
                        }
                    ]
                },
                {
                    "type": "box",
                    "layout": "vertical",
                    "backgroundColor": "#FFF8F0",
                    "cornerRadius": "8px",
                    "paddingAll": "12px",
                    "contents": [
                        {
                            "type": "text",
                            "text": "方案二：深層調理",
                            "weight": "bold",
                            "color": "#A0522D",
                            "size": "md"
                        },
                        {
                            "type": "text",
                            "text": "月付 NT$1,599",
                            "weight": "bold",
                            "size": "xl",
                            "color": "#E8640C"
                        },
                        {
                            "type": "text",
                            "text": "✅ 每月 100 分鐘推拿（乙次）\n✅ 贈伸呼吸靜養洗髮精一瓶\n✅ 入會贈 $100 儲值金\n✅ 生日贈 $200 儲值金 + 免費洗護",
                            "wrap": True,
                            "size": "sm",
                            "color": "#555555",
                            "margin": "sm"
                        }
                    ]
                },
                {
                    "type": "text",
                    "text": "💳 支援無卡分期（月付大人/遠信/銀角）",
                    "wrap": True,
                    "size": "sm",
                    "color": "#A0522D"
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
                        "label": "📅 立即預約諮詢",
                        "uri": "https://ezpretty.cc/ycIvi"
                    }
                },
                {
                    "type": "button",
                    "style": "secondary",
                    "action": {
                        "type": "uri",
                        "label": "📞 電話諮詢",
                        "uri": "tel:0979592099"
                    }
                }
            ]
        }
    }
    return contents


# ─────────────────────────────────────────────
# 關鍵字偵測函式
# ─────────────────────────────────────────────

def detect_keyword(text: str):
    """
    偵測訊息中的關鍵字，回傳對應的 Flex Message 或特殊指令。
    回傳值：
      - ("flex", <flex_dict>)  → 回覆 Flex Message
      - ("url", <url_str>)     → 回覆純文字預約連結
      - None                   → 交給 AI 處理
    """
    t = text.strip()

    # 師傅/團隊介紹 → 傳送師傅大圖 + 文字說明
    if any(kw in t for kw in ["師傅", "介紹師傅", "有哪些師傅", "師傅介紹", "師傅團隊", "認識師傅"]):
        return ("team", None)

    # 服務/團隊 → 師傅介紹 + 師傅大圖 + 服務價目表（最多 5 則訊息）
    if any(kw in t for kw in ["服務/團隊", "團隊", "服務介紹", "有哪些服務", "服務項目"]):
        return ("service_team", None)

    # 優惠&活動
    if any(kw in t for kw in ["優惠&活動", "優惠活動", "目前活動", "有什麼優惠", "活動"]):
        return ("flex", make_promotion_flex())

    # 店內資訊
    if any(kw in t for kw in ["店內資訊", "店家資訊", "店家介紹"]):
        return ("flex", make_store_info_flex())

    # 交通&位置
    if any(kw in t for kw in ["交通&位置", "交通位置", "怎麼去", "停車", "在哪", "地址", "位置"]):
        return ("flex", make_traffic_flex())

    # 線上預約
    if any(kw in t for kw in ["線上預約", "我想預約", "預約連結", "怎麼預約", "如何預約"]):
        return ("url", "哈囉～想預約的話，直接點這個連結就可以囉！阿卡幫你準備好了🦥\n\n👉 https://ezpretty.cc/ycIvi\n\n有任何問題，隨時問阿卡喔～慢慢來不急！")

    # 會員專區
    if any(kw in t for kw in ["會員專區", "VIP方案", "VIP 方案", "會員方案", "訂閱", "月費", "加入會員"]):
        return ("url", "哈囉～歡迎進入阿卡的會員專區！🦥\n\n👉 https://liff.line.me/2008250851-egjPOXgO\n\n在這裡可以查看 VIP 方案、管理會員資訊，慢慢來不急～")

    return None


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
    result = detect_keyword(user_message)

    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)

        if result is None:
            # 交給 AI 處理
            reply_text = chatbot.generate_response(user_message)
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text=reply_text)]
                )
            )
        elif result[0] == "url":
            # 純文字預約連結
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text=result[1])]
                )
            )
        elif result[0] == "flex":
            # Flex Message 卡片
            flex_container = FlexContainer.from_dict(result[1])
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[
                        FlexMessage(
                            alt_text="阿卡為你整理的資訊卡片",
                            contents=flex_container
                        )
                    ]
                )
            )
        elif result[0] == "team":
            # 師傅團隊介紹：先傳文字說明，再傳師傅大圖
            intro_text = (
                "🦥 阿卡來介紹我們的專業師傅團隊！\n\n"
                "✨ 芸芸 — 啟動舒緩，回歸平衡\n"
                "   國家美容技術士（乙/丙級），五年以上扎實經驗\n\n"
                "✨ 大可 — 智慧洞察，突破不適\n"
                "   台灣推拿整復協會養生保健 + 進階證書\n\n"
                "✨ 阿YA — 柔式手法，壓力釋放\n"
                "   傳統整復推拿技術士、A-Team柔式推拿菁英\n\n"
                "✨ 阿駿 — 科班底蘊，重塑平衡\n"
                "   仁德醫專復健科畢業，臨床實戰七年以上\n\n"
                "✨ 阿瑜 — 溫柔以待，自在生活\n"
                "   傳統整復推拿技術士、摩根整復大師班\n\n"
                "每位師傅都持有專業證照，用心為你調理保養！\n"
                "想預約指定師傅，歡迎來電或線上預約 👉 https://ezpretty.cc/ycIvi"
            )
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[
                        TextMessage(text=intro_text),
                        ImageMessage(
                            original_content_url=TEAM_PHOTO_URL,
                            preview_image_url=TEAM_PHOTO_URL
                        )
                    ]
                )
            )

        elif result[0] == "service_team":
            # 服務/團隊：師傅介紹文字 + 師傅大圖 + 服務價目表（共 3 則，不超過 LINE 限制 5 則）
            team_intro = (
                "🦥 阿卡來介紹我們的專業師傅團隊！\n\n"
                "✨ 芸芸 — 啟動舒緩，回歸平衡\n"
                "   國家美容技術士（乙/丙級），五年以上扎實經驗\n\n"
                "✨ 大可 — 智慧洞察，突破不適\n"
                "   台灣推拿整復協會養生保健 + 進階證書\n\n"
                "✨ 阿YA — 柔式手法，壓力釋放\n"
                "   傳統整復推拿技術士、A-Team柔式推拿菁英\n\n"
                "✨ 阿駿 — 科班底蘊，重塑平衡\n"
                "   仁德醫專復健科畢業，臨床實戰七年以上\n\n"
                "✨ 阿瑜 — 溫柔以待，自在生活\n"
                "   傳統整復推拿技術士、摩根整復大師班"
            )
            price_text = (
                "🦥 伸懶腰的服務項目與價格\n\n"
                "📌 推拿整復\n"
                "・簡單保養 30分鐘 $600\n"
                "・全身保養 60分鐘 $1,100\n"
                "・深層保養 90分鐘 $1,600\n"
                "・大保養 120分鐘 $2,100\n\n"
                "📌 深層肌筋膜油推\n"
                "・基礎舒緩 60分鐘 $1,200\n"
                "・深層平衡 90分鐘 $1,700\n"
                "・深度修護 120分鐘 $2,200\n\n"
                "🏋️ 運動修復專案\n"
                "・運動後快速恢復套餐 90分鐘 $1,600\n"
                "・深層肌筋膜放鬆套餐 135分鐘 $2,400\n"
                "・全能運動放鬆套餐 150分鐘 $2,800\n\n"
                "💼 上班小資族肩頸革命\n"
                "・肩頸舒活體驗套餐 65分鐘 $1,300\n"
                "・久坐全息放鬆套餐 105分鐘 $1,700\n"
                "・全身經絡尊榮套餐 150分鐘 $2,600\n\n"
                "⚒️ 重度勞動者專案\n"
                "・筋骨快效舒緩套餐 90分鐘 $1,600\n"
                "・深層強效放鬆套餐 135分鐘 $2,400\n"
                "・元氣充足放鬆套餐 150分鐘 $2,800\n\n"
                "想預約請點 👉 https://ezpretty.cc/ycIvi\n"
                "有問題隨時問阿卡喔～🦥"
            )
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[
                        TextMessage(text=team_intro),
                        ImageMessage(
                            original_content_url=TEAM_PHOTO_URL,
                            preview_image_url=TEAM_PHOTO_URL
                        ),
                        TextMessage(text=price_text)
                    ]
                )
            )


@handler.add(FollowEvent)
def handle_follow(event):
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        welcome_message = chatbot.get_welcome_message()
        line_bot_api.reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=welcome_message)]
            )
        )


if __name__ == "__main__":
    if "OPENAI_API_KEY" not in os.environ:
        print("錯誤：OPENAI_API_KEY 環境變數未設定。請先設定此變數再執行。")
        exit(1)
    app.run(host="0.0.0.0", port=5000)
