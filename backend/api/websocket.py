# myapp/consumers.py

import json
from channels.generic.websocket import AsyncWebsocketConsumer

class ProgressConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        print('xxx')
        self.group_name = "progress_group"
        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.group_name,
            self.channel_name
        )

    # 接收来自 Channel Layer 的 send_progress 消息
    async def send_progress(self, event):
        progress = event['progress']
        await self.send(text_data=json.dumps({
            'progress': progress
        }))

    # 接收来自 Channel Layer 的 send_matched_results 消息
    async def send_matched_results(self, event):
        matched_results = event['matched_results']
        await self.send(text_data=json.dumps({
            'matched_results': matched_results
        }))
