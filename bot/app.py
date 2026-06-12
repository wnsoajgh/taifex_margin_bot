import logging
import os

from fastapi import FastAPI, HTTPException, Request
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (ApiClient, Configuration, MessagingApi,
                                  ReplyMessageRequest, TextMessage)
from linebot.v3.webhooks import MessageEvent, TextMessageContent

from bot import service

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

app = FastAPI()
handler = WebhookHandler(os.environ.get("LINE_CHANNEL_SECRET", ""))
_configuration = Configuration(
    access_token=os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", ""))


def _reply(reply_token: str, text: str) -> None:
    with ApiClient(_configuration) as client:
        MessagingApi(client).reply_message(ReplyMessageRequest(
            reply_token=reply_token, messages=[TextMessage(text=text)]))


@handler.add(MessageEvent, message=TextMessageContent)
def on_text_message(event: MessageEvent) -> None:
    query = service.extract_query(event.message.text)
    if query is None:   # 非 P/ 開頭的訊息一律不回應（避免群組洗版）
        return
    user_id = getattr(event.source, "user_id", None)   # 訂閱功能以 userId 區分使用者
    _reply(event.reply_token, service.build_answer(query, user_id))


@app.get("/health")
def health() -> dict:
    return {"ok": True}


@app.post("/callback")
async def callback(request: Request) -> str:
    signature = request.headers.get("X-Line-Signature", "")
    body = (await request.body()).decode("utf-8")
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        raise HTTPException(status_code=400, detail="invalid signature")
    except Exception:
        # 簽章驗證後即確認收件：reply token 一次性，回 5xx 會觸發 LINE redelivery
        # 而重送必然再失敗（token 已耗用），故記 log 後回 200
        log.exception("unexpected error handling webhook")
    return "OK"
