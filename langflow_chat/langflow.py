import argparse
import json
from argparse import RawTextHelpFormatter
import requests
from typing import Optional, List, Dict, Any, Tuple
import warnings
from datetime import datetime

try:
    from langflow.load import upload_file
except ImportError:
    warnings.warn("Langflow provides a function to help you upload files to the flow. Please install langflow to use it.")
    upload_file = None

class Langflow:
    def __init__(self,
                 langflow_base_api_url: str = "http://127.0.0.1:7860"):
        self.langflow_base_api_url = langflow_base_api_url
        self.chat_history: List[Dict[str, Any]] = []

    def run_flow(
            self,
            message: str,
            endpoint: str,
            output_type: str = "chat",
            input_type: str = "chat",
            tweaks: Optional[dict] = None,
            api_key: Optional[str] = None,
            update_history: bool = True) -> Tuple[Dict[str, str], List[Dict[str, Any]]]:
        
        """
        Run a flow with a given message and optional tweaks.

        :param message: The message to send to the flow
        :param endpoint: The ID or the endpoint name of the flow
        :param output_type: Type of output, default is "chat"
        :param input_type: Type of input, default is "chat"
        :param tweaks: Optional tweaks to customize the flow
        :param api_key: Optional API key for authentication
        :param update_history: Whether to update chat history, default is True
        :return: The JSON response from the flow as (dict_data, list_data)
        """
        api_url = f"{self.langflow_base_api_url}/api/v1/run/{endpoint}"

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
        
        # ユーザーメッセージをヒストリーに追加
        if update_history:
            self._add_user_message_to_history(message)
            
            # 問い合わせ中のプレースホルダーを追加
            self._add_pending_message_to_history()
        
        try:
            response = requests.post(api_url, json=payload, headers=headers)
            response.encoding = 'utf-8'  # エンコーディングを明示的に設定
            data = response.json()
            
            # 問い合わせ中のプレースホルダーを削除
            if update_history:
                self._remove_pending_messages_from_history()
                
            # 結果を格納する辞書を初期化
            dict_data = {}
            list_data = []
    
            # データ構造を探索してメッセージを抽出
            for output in data.get('outputs', []):
                for in_output in output.get('outputs', []):
                    output_data = in_output.get('results', {}).get('message', {}).get('data', {})
                    if output_data:
                        list_data.append(output_data)
                        name = output_data.get('sender_name')
                        icon = output_data.get('properties', {}).get('icon')
                        component_id = output_data.get('properties', {}).get('source', {}).get('id')
                        text = output_data.get('text')
    
                        if name and text:
                            dict_data[name] = text
                            
                            # ボットの応答をヒストリーに追加
                            if update_history and name not in ["Skill Manager Code"]:
                                self._add_bot_response_to_history(name, text, icon, component_id)
                                
            return dict_data, list_data
            
        except Exception as e:
            # エラー発生時も問い合わせ中のプレースホルダーを削除
            if update_history:
                self._remove_pending_messages_from_history()
            raise e
    
    def _add_user_message_to_history(self, message: str) -> None:
        """
        ユーザーメッセージをチャット履歴に追加します。
        
        :param message: ユーザーからのメッセージ
        """
        self.chat_history.append({
            "role": "user",
            "name": "User",
            "text": message,
            "icon": "👤",
            "timestamp": datetime.now().isoformat()
        })
    
    def _add_pending_message_to_history(self) -> None:
        """
        問い合わせ中のプレースホルダーメッセージをチャット履歴に追加します。
        """
        self.chat_history.append({
            "role": "assistant",
            "name": "AI",
            "text": "応答を生成中...",
            "icon": "🤖",
            "is_pending": True,
            "timestamp": datetime.now().isoformat()
        })
    
    def _remove_pending_messages_from_history(self) -> None:
        """
        チャット履歴から問い合わせ中のメッセージを削除します。
        """
        self.chat_history = [msg for msg in self.chat_history if not msg.get('is_pending', False)]
    
    def _add_bot_response_to_history(
            self, 
            name: str, 
            text: str, 
            icon: Optional[str] = None, 
            component_id: Optional[str] = None
        ) -> None:
        """
        ボットの応答をチャット履歴に追加します。
        
        :param name: ボットの名前
        :param text: ボットからの応答テキスト
        :param icon: ボットのアイコン（オプション）
        :param component_id: コンポーネントID（オプション）
        """
        self.chat_history.append({
            "role": "assistant",
            "name": name,
            "text": text,
            "icon": icon or "🤖",
            "component_id": component_id,
            "timestamp": datetime.now().isoformat()
        })
    
    def get_chat_history(self) -> List[Dict[str, Any]]:
        """
        チャット履歴を取得します。
        
        :return: チャット履歴のリスト
        """
        return self.chat_history
    
    def clear_chat_history(self) -> None:
        """
        チャット履歴をクリアします。
        """
        self.chat_history = [] 