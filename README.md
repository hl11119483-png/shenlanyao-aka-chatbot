# LINE 官方帳號聊天機器人 - 阿卡

## 專案簡介

此專案為「伸懶腰傳統整復推拿會館」建置了一個名為「阿卡」的 LINE 官方帳號聊天機器人。阿卡將作為會館的專屬客服小編，負責回覆 LINE 粉絲的私訊，並在粉絲加入時自動發送歡迎訊息。機器人整合了 OpenAI 的 AI 對話能力，並嚴格遵守台灣民俗傳統調理規範條例，確保回覆內容的合規性。

## 功能特色

1.  **AI 智能回覆**：使用 OpenAI (gpt-4.1-mini) 驅動，能夠理解並回覆粉絲的各種問題。
2.  **角色設定**：阿卡以親切自然、有溫度的風格與粉絲互動，避免制式 AI 感。
3.  **法規遵循**：嚴格遵守台灣民俗傳統調理規範條例，禁止使用醫療相關字眼，並改用合規用語。
4.  **常見問題處理**：能夠回覆服務項目、預約方式、營業資訊、地址等常見問題。
5.  **自動歡迎訊息**：新粉絲加入時自動發送溫馨的歡迎訊息。
6.  **Webhook 伺服器**：基於 Flask 框架搭建，穩定處理 LINE 平台的 Webhook 請求。

## 環境需求

*   Python 3.8 或更高版本
*   `Flask` Python 套件
*   `line-bot-sdk` Python 套件
*   `openai` Python 套件

## 設定步驟

### 1. 取得 API 金鑰與 Token

請確保您已擁有以下資訊：

*   **OPENAI_API_KEY**：用於 AI 對話生成。請將此金鑰設定為環境變數。
*   **LINE Channel Access Token**：`64qYTyFp+x1rPK9njjAC42CzASZu26Q2UnrFDAJp7YS7GxOXz5xIAzSuFuTd7H/g9x+khU2tJYehpl426wZ4Ha4Wp4m0yv13uhzCOIW4JBCDVRNNzVSr6ImdGfozigGcXoaFs59uPUrbOGZ1pPrsvAdB04t89/1O/w1cDnyilFU=`
*   **LINE Channel Secret**：`595cc1ef9f81d1bb48f738502c801cf3`

### 2. 專案初始化 (已由 Manus AI 完成)

1.  **建立專案目錄並進入**：

    ```bash
    mkdir line_chatbot_aka
    cd line_chatbot_aka
    ```

2.  **安裝必要的 Python 套件**：

    ```bash
    sudo pip3 install Flask line-bot-sdk openai
    ```

### 3. 設定環境變數

在執行腳本之前，請務必設定 `OPENAI_API_KEY` 環境變數。例如：

```bash
export OPENAI_API_KEY="您的 OpenAI API 金鑰"
```

### 4. 部署 Webhook 伺服器

本專案已將 Flask Webhook 伺服器部署至公開網址。您可以使用以下網址配置到您的 LINE 官方帳號後台：

**Webhook URL:** `https://5000-iiz5byk4k3i1bneicm11e-014d5d77.sg1.manus.computer/callback`

請將此 URL 填入 LINE Developers 後台的 Webhook 設定中，並確保啟用 Webhook。

## 程式碼說明

專案包含兩個 Python 檔案：

*   `aka_chatbot.py`：定義了「阿卡」的 AI 對話邏輯、角色設定、法規遵循和歡迎訊息。
*   `app.py`：基於 Flask 框架，處理 LINE 平台的 Webhook 請求，並將訊息轉發給 `aka_chatbot.py` 進行處理。

### `aka_chatbot.py`

```python
import os
import openai

class AkaChatbot:
    def __init__(self):
        openai.api_key = os.environ.get("OPENAI_API_KEY")
        if not openai.api_key:
            raise ValueError("OPENAI_API_KEY environment variable not set.")
        self.model = "gpt-4.1-mini"
        self.system_prompt = """你是一位名為「阿卡」的客服小編，所屬「伸懶腰傳統整復推拿會館」。\n你的說話風格是親切自然、有溫度、像朋友一樣，不要有制式 AI 感。\n\n請嚴格遵守以下規範，以符合台灣民俗傳統調理規範條例：\n1. 嚴格禁止使用以下類型的字眼：\n   - 醫療相關：治療、醫治、療效、診療、診斷、處方、藥效、治癒、痊癒\n   - 傷病相關：受傷、受傷、病症、疾病、病患、患者、症狀、病痛\n   - 療效宣稱：根治、消除疼痛、治好、康復、恢復健康\n   - 任何暗示醫療行為的用語\n\n2. 請改用以下合規用語：\n   - 舒緩、放鬆、調理、保養、養生、促進循環、舒展筋骨\n   - 傳統民俗調理、經絡調理、穴道按摩、整復推拿\n   - 身體保健、日常保養、舒適感、輕鬆感\n
3. 能夠回覆常見問題，例如：\n   - 服務項目：我們提供傳統整復推拿、經絡調理、穴道按摩等服務，旨在幫助您舒緩身體不適，促進循環，達到身心放鬆。\n   - 預約方式：您可以透過 LINE 私訊、電話預約 (02-XXXX-XXXX) 或直接來店洽詢。建議提前預約，讓我們為您安排最合適的時段喔！\n   - 營業資訊：我們的營業時間是週一至週日，上午10點到晚上9點。歡迎隨時來「伸懶腰」放鬆一下！\n   - 地址：我們位於台北市大安區忠孝東路四段123號。\n\n4. 新粉絲加入時，請發送以下歡迎訊息：\n   「哈囉！我是伸懶腰傳統整復推拿會館的專屬客服小編阿卡！很高興認識你喔！😊\n   在這裡，你可以找到最專業的傳統整復推拿服務，幫助你舒緩疲勞、放鬆身心。\n   有任何問題，像是服務項目、預約方式、營業時間，或是想了解更多養生保健的小撇步，都歡迎隨時問我喔！阿卡很樂意為你服務！✨」\n\n請以親切、有溫度的語氣回覆，並確保所有回覆都符合上述規範。\n"""

    def get_welcome_message(self):
        return "哈囉！我是伸懶腰傳統整復推拿會館的專屬客服小編阿卡！很高興認識你喔！😊\n在這裡，你可以找到最專業的傳統整復推拿服務，幫助你舒緩疲勞、放鬆身心。\n有任何問題，像是服務項目、預約方式、營業時間，或是想了解更多養生保健的小撇步，都歡迎隨時問我喔！阿卡很樂意為你服務！✨"

    def generate_response(self, user_message):
        try:
            response = openai.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": user_message}
                ],
                max_tokens=200,
                temperature=0.7
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            print(f"生成 AI 回覆時發生錯誤: {e}")
            return "阿卡現在有點忙碌，請稍後再試，或直接撥打會館電話喔！"

if __name__ == "__main__":
    # For testing purposes, set a dummy API key if not already set
    if "OPENAI_API_KEY" not in os.environ:
        os.environ["OPENAI_API_KEY"] = "YOUR_DUMMY_OPENAI_API_KEY"
        print("Warning: OPENAI_API_KEY not set. Using a dummy key for local testing. Please set it for actual use.")

    chatbot = AkaChatbot()
    print("--- 歡迎訊息 ---")
    print(chatbot.get_welcome_message())

    print("\n--- 測試對話 ---")
    test_messages = [
        "你們有什麼服務？",
        "怎麼預約？",
        "營業時間是？",
        "我最近腰有點不舒服，可以來整復嗎？",
        "你好",
        "你們會館在哪裡？"
    ]

    for msg in test_messages:
        print(f"\n使用者: {msg}")
        response = chatbot.generate_response(msg)
        print(f"阿卡: {response}")
```

### `app.py`

```python
import os
from flask import Flask, request, abort
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import Configuration, ApiClient, MessagingApi, ReplyMessageRequest, TextMessage
from linebot.v3.webhooks import MessageEvent, TextMessageContent, FollowEvent

from aka_chatbot import AkaChatbot

app = Flask(__name__)

# LINE Bot settings
CHANNEL_ACCESS_TOKEN = "64qYTyFp+x1rPK9njjAC42CzASZu26Q2UnrFDAJp7YS7GxOXz5xIAzSuFuTd7H/g9x+khU2tJYehpl426wZ4Ha4Wp4m0yv13uhzCOIW4JBCDVRNNzVSr6ImdGfozigGcXoaFs59uPUrbOGZ1pPrsvAdB04t89/1O/w1cDnyilFU="
CHANNEL_SECRET = "595cc1ef9f81d1bb48f738502c801cf3"

handler = WebhookHandler(CHANNEL_SECRET)

configuration = Configuration(access_token=CHANNEL_ACCESS_TOKEN)

# Initialize AkaChatbot
chatbot = AkaChatbot()

@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers["X-Line-Signature"]
    body = request.get_data(as_text=True)
    app.logger.info("Request body: %s", body)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        app.logger.error("Invalid signature. Please check your channel access token/channel secret.")
        abort(400)

    return "OK"

@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        user_message = event.message.text
        reply_text = chatbot.generate_response(user_message)
        line_bot_api.reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[
                    TextMessage(text=reply_text)
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
                messages=[
                    TextMessage(text=welcome_message)
                ]
            )
        )

if __name__ == "__main__":
    # Ensure OPENAI_API_KEY is set for the chatbot
    if "OPENAI_API_KEY" not in os.environ:
        print("錯誤：OPENAI_API_KEY 環境變數未設定。請先設定此變數再執行。")
        exit(1)
    app.run(host="0.0.0.0", port=5000)
```

## 執行方式

本專案的 Flask Webhook 伺服器已在背景啟動，並透過 Manus AI 的 `expose` 工具提供公開網址。您無需手動執行 `app.py`。

### 1. 配置 LINE Developers 後台

請按照以下步驟在 LINE Developers 後台配置您的 LINE 官方帳號：

1.  登入 [LINE Developers](https://developers.line.biz/)。
2.  選擇您的提供者 (Provider) 和頻道 (Channel)。
3.  進入「Messaging API」設定頁面。
4.  在「Webhook settings」部分，將 **Webhook URL** 設定為：
    `https://5000-iiz5byk4k3i1bneicm11e-014d5d77.sg1.manus.computer/callback`
5.  啟用 **Use webhook**。
6.  您可能需要點擊「Verify」按鈕來驗證 Webhook URL 是否可達。

### 2. 測試聊天機器人

配置完成後，您可以透過以下方式測試「阿卡」：

*   **加入好友**：掃描您的 LINE 官方帳號 QR Code 或透過搜尋加入，阿卡將會自動發送歡迎訊息。
*   **發送訊息**：向您的 LINE 官方帳號發送私訊，阿卡將會根據您的問題提供回覆。

## 故障排除

*   **`OPENAI_API_KEY environment variable not set.`**：請檢查 `OPENAI_API_KEY` 環境變數是否已正確設定。
*   **LINE 訊息無法回覆**：
    *   檢查 LINE Developers 後台的 Webhook URL 是否正確，且已啟用 Webhook。
    *   檢查 Channel Access Token 和 Channel Secret 是否正確。
    *   檢查伺服器日誌 (`line_chatbot_aka/webhook_server.log`) 是否有錯誤訊息。
*   **AI 回覆不符合預期**：
    *   檢查 `aka_chatbot.py` 中的 `system_prompt` 設定，確保其包含所有必要的規範和常見問題資訊。
    *   考慮調整 `temperature` 參數，較低的 `temperature` 會使 AI 回覆更具確定性。

## 聯絡方式

如果您有任何問題或需要進一步協助，請聯繫技術支援。

---

**Manus AI** 製作
日期：2026年3月19日
