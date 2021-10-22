import logging
import os

import azure.functions as func
from linebot import LineBotApi, WebhookHandler
from linebot.models import MessageEvent, TextMessage, TextSendMessage
from azure.cosmos import CosmosClient, PartitionKey
from linebot.models.actions import PostbackAction
from linebot.models.events import PostbackEvent
from linebot.models.template import ButtonsTemplate, TemplateSendMessage

channel_access_token = os.environ['channel_access_token']
channel_secret = os.environ['channel_secret']

handler = WebhookHandler(channel_secret)
linebot_api = LineBotApi(channel_access_token)

endpoint = os.environ['endpoint']
cosmoskey = os.environ['cosmoskey']
client = CosmosClient(endpoint, cosmoskey)

database = client.create_database_if_not_exists(id="line")
container = database.create_container_if_not_exists(
    id="shopping",
    partition_key=PartitionKey(path="/id")
)

def main(req: func.HttpRequest) -> func.HttpResponse:
    signature = req.headers["X-Line-Signature"]
    body = req.get_body().decode('utf-8')
    handler.handle(body, signature)
    return func.HttpResponse('OK')

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    sentMessage = event.message.text
    userId = event.source.user_id
    try:
        doc = container.read_item(item=userId, partition_key=userId)
    except:
        doc = {'id':userId, 'tobuy':[]}
    if sentMessage == "リスト":
        if not doc['tobuy']:
            msg = TextSendMessage(text='リストは空です')
        else:
            actions = []
            for item in doc['tobuy']:
                action = PostbackAction(label=item, data=item)
                actions.append(action)
            bt = ButtonsTemplate(title="買い物リスト",text="ボタンを押して削除",actions=actions)
            msg = TemplateSendMessage(
                alt_text='買い物リスト',
                template=bt
        )
    else:
        if len(doc['tobuy'])<=3:
            doc['tobuy'].append(sentMessage)
            txt = ','.join(doc['tobuy'])
            msg = TextSendMessage(text=f'買い物かご={txt}')
            container.upsert_item(doc)
        else:
            msg = TextSendMessage(text='買い物リストに入れられるのは四つまでですよ！買いすぎダメ！')

    linebot_api.reply_message(event.reply_token, msg)

@handler.add(PostbackEvent)
def handle_postback(event):
    data = event.postback.data
    userId = event.source.user_id
    try:
        doc = container.read_item(item=userId, partition_key=userId)
    except:
        doc = {'id':userId, 'tobuy':[]}
    
    if data in doc['tobuy']:
        doc['tobuy'].remove(data)
        t = f"{data}を削除しました"
    else:
        t = f"{data}って、もうリストに入ってないですけど？！"
    container.upsert_item(doc)
    linebot_api.reply_message(event.reply_token, TextSendMessage(text=t))