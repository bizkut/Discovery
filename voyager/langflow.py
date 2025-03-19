import argparse
import json
from argparse import RawTextHelpFormatter
import requests
from typing import Optional
import warnings
try:
    from langflow.load import upload_file
except ImportError:
    warnings.warn("Langflow provides a function to help you upload files to the flow. Please install langflow to use it.")
    upload_file = None

class Langflow:
    def __init__(self,
                 base_api_url: str = "http://127.0.0.1:7860",
                 flow_id: str = "b9b5f30d-835a-49ca-b76b-6d3b068af83a",
                 endpoint: str = "",
                 api_key: Optional[str] = None):
        self.base_api_url = base_api_url
        self.flow_id = flow_id
        self.endpoint = endpoint
        self.api_key = api_key



    def run_flow(
            self,
            message: str,
            endpoint: str,
            output_type: str = "chat",
            input_type: str = "chat",
            tweaks: Optional[dict] = None,
            api_key: Optional[str] = None) -> dict:
        
        """
        Run a flow with a given message and optional tweaks.

        :param message: The message to send to the flow
        :param endpoint: The ID or the endpoint name of the flow
        :param tweaks: Optional tweaks to customize the flow
        :return: The JSON response from the flow
        """
        api_url = f"{self.base_api_url}/api/v1/run/{endpoint}"

        payload = {
            "input_value": str(message),
            "output_type": output_type,
            "input_type": input_type,
        }
        headers = None
        if tweaks:
            payload["tweaks"] = tweaks
        if api_key:
            headers = {"x-api-key": api_key}
        response = requests.post(api_url, json=payload, headers=headers)
        response.encoding = 'utf-8'  # エンコーディングを明示的に設定
        data = response.json()
        # 結果を格納する辞書を初期化
        messages_by_component = {}

        # データ構造を探索してメッセージを抽出
        for output in data.get('outputs', []):
            for result in output.get('outputs', []):
                for message in result.get('messages', []):
                    component_id = message.get('component_id')
                    message_text = message.get('message')
                    
                    if component_id and message_text:
                        messages_by_component[component_id] = message_text
        return messages_by_component