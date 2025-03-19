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
        self.tweaks = {
            "ChatOutput-LfK1l": {},
            "MinecraftDataFormatter-IHaIU": {},
            "LanguageTranslator-mzNKF": {},
            "ChatInput-DOdcW": {},
            "ChatOutput-Q7MzC": {},
            "CombineText-rKwk7": {},
            "TextInput-2JuA8": {},
            "TextInput-nk9Nz": {},
            "CombineText-0U3rh": {},
            "LanguageTranslator-5O13U": {},
            "Prompt-OvwRT": {},
            "CustomComponent-dequj": {},
            "Prompt-rVdLu": {},
            "Prompt-sWCJ6": {},
            "TextInput-i6PXB": {},
            "CombineText-QYYKl": {},
            "LanguageTranslator-tMJHM": {},
            "ChatOutput-sWSbt": {},
            "Agent-NWZia": {},
            "Agent-w6dVn": {},
            "AstraDB-On90D": {},
            "Prompt-kr33k": {},
            "TextInput-N8Zye": {},
            "MergeDataComponent-LzQjK": {},
            "Directory-sY9z8": {},
            "ParseDataFrame-cE0qI": {},
            "AlterMetadata-oTNIq": {},
            "CustomComponent-nd9EO": {},
            "Agent-mwbxB": {},
            "TextInput-L0Cgw": {},
            "CombineText-fWCzB": {},
            "LanguageTranslator-VvUP9": {},
            "ChatOutput-yR3Yo": {},
            "CustomComponent-qSzkx": {},
            "CombineText-ovBJG": {}
        }
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
            "input_value": message,
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
        return response.json()
