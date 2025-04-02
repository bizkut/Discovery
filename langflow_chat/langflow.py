import argparse
import json
from langflow.load import run_flow_from_json
from deep_translator import GoogleTranslator
from typing import Optional, List, Dict, Any, Tuple, Callable
import warnings
from datetime import datetime
import uuid

try:
    from langflow.load import upload_file
except ImportError:
    warnings.warn("Langflow provides a function to help you upload files to the flow. Please install langflow to use it.")
    upload_file = None

class LangflowChat:
    def __init__(self,translate_mode: bool = False,translate_language: str = "ja"):
        self.chat_history: List[Dict[str, Any]] = []
        # メッセージ更新時のコールバック関数
        self.on_message_update: Optional[Callable] = None
        self.translate_mode = translate_mode
        self.translate_language = translate_language

    def register_update_callback(self, callback: Callable) -> None:
        """
        メッセージ更新時のコールバック関数を登録します。

        :param callback: メッセージ更新時に呼び出される関数
        """
        self.on_message_update = callback

    def run_flow(
            self,
            message: str,
            json_path: str = None,
            fallback_to_env_vars_at_json_mode: bool = True,
            env_file_at_json_mode: str = ".env",
            tweaks: Optional[dict] = {},
            update_history: bool = True,
            session_id: str = None) -> Tuple[Dict[str, str], List[Dict[str, Any]]]:
        
        """
        Run a flow with a given message and optional tweaks.

        :param message: The message to send to the flow
        :param json_mode: Whether to use JSON mode, default is False
        :param endpoint: The ID or the endpoint name of the flow
        :param output_type: Type of output, default is "chat"
        :param input_type: Type of input, default is "chat"
        :param tweaks: Optional tweaks to customize the flow
        :param api_key: Optional API key for authentication
        :param update_history: Whether to update chat history, default is True
        :return: The JSON response from the flow as (dict_data, list_data)
        """
        
        # ユーザーメッセージをヒストリーに追加
        if update_history:
            self._add_user_message_to_history(message)
            self._add_pending_message_to_history()

        if session_id is None:
            session_id = str(uuid.uuid4())

        # すべてのコンポーネントのsession_idフィールドを更新
        for component_id, component_data in tweaks.items():
            if isinstance(component_data, dict) and "session_id" in component_data:
                component_data["session_id"] = session_id
            
            # Agentコンポーネントの場合、sender_nameが空でないことを確認
            if component_id.startswith("Agent-") and isinstance(component_data, dict):
                if not component_data.get("sender_name"):
                    component_data["sender_name"] = "Agent"
                if not component_data.get("sender"):
                    component_data["sender"] = "Machine"
        
        # フローの実行
        try:
            data = run_flow_from_json(
                flow=json_path,
                input_value=message,
                tweaks=tweaks,
                fallback_to_env_vars=fallback_to_env_vars_at_json_mode,
                env_file=env_file_at_json_mode,
                session_id=session_id
            )
                
            # 問い合わせ中のプレースホルダーを削除
            if update_history:
                self._remove_pending_messages_from_history()
            
            list_data = [] 

            for item in data:
                if hasattr(item, 'outputs'):
                    for output in item.outputs:
                        if hasattr(output, 'results') and 'message' in output.results:
                            message_obj = output.results['message']
                            
                            message_data = {}

                            if hasattr(message_obj, 'data'):
                                data_dict = self.object_to_dict(message_obj.data)
                                if isinstance(data_dict, dict):
                                    for key, value in data_dict.items():
                                        message_data[key] = value
                            
                            if hasattr(message_obj, 'properties'):
                                props_dict = self.object_to_dict(message_obj.properties)
                                if isinstance(props_dict, dict):
                                    for key, value in props_dict.items():
                                        message_data[key] = value
                            
                            if message_data: # 空でなければ追加
                                if message_data['sender_name'] == 'Skill Manager Code':
                                    pass
                                elif message_data['sender'] and message_data['sender'] == 'Machine':
                                    self._add_bot_response_to_history(
                                        name=message_data['sender_name'],
                                        text=message_data['text'],
                                        icon=message_data['icon']
                                    )
                                elif message_data['sender'] and message_data['sender'] == 'User':
                                    self._add_user_message_to_history(
                                        message=message_data['text']
                                    )
                                list_data.append(message_data)
   
            return list_data
            
        except Exception as e:
            print(f"Error: {e}")
            
            # エラー発生時も問い合わせ中のプレースホルダーを削除
            if update_history:
                self._remove_pending_messages_from_history()
            raise e

    def object_to_dict(self,obj):
        """
        オブジェクトのすべての公開属性を辞書に変換する関数
        
        Args:
            obj: 変換対象のオブジェクト
            
        Returns:
            dict: オブジェクトの属性を含む辞書
        """
        if obj is None:
            return None
            
        # オブジェクトが基本型（文字列、数値、真偽値など）の場合はそのまま返す
        if isinstance(obj, (str, int, float, bool, list, dict)) or obj is None:
            return obj
            
        # vars() が動作する一般的なオブジェクトの場合
        try:
            result = {}
            # __dict__ がある場合はそれを使用
            attributes = vars(obj)
            for key, value in attributes.items():
                # アンダースコアで始まる内部属性は除外（オプション）
                if not key.startswith('_'):
                    # 再帰的に処理（ネストされたオブジェクトも辞書に変換）
                    result[key] = self.object_to_dict(value)
            return result
        except TypeError:
            # vars() が動作しないオブジェクトの場合は dir() を使用
            result = {}
            for attr in dir(obj):
                # アンダースコアで始まる内部属性やメソッドは除外
                if not attr.startswith('_'):
                    value = getattr(obj, attr)
                    # callable はメソッドなので除外
                    if not callable(value):
                        result[attr] = self.object_to_dict(value)
            return result
        
    def _add_user_message_to_history(self, message: str) -> None:
        """
        ユーザーメッセージをチャット履歴に追加します。
        
        :param message: ユーザーからのメッセージ
        """
        if self.translate_mode:
            message = GoogleTranslator(source='auto', target=self.translate_language).translate(message)
        self.chat_history.append({
            "role": "user",
            "name": "User",
            "text": message,
            "icon": "👤",
            "timestamp": datetime.now().isoformat()
        })
        
        # メッセージ更新時のコールバックを呼び出し
        if self.on_message_update:
            self.on_message_update()
    
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
        
        # メッセージ更新時のコールバックを呼び出し
        if self.on_message_update:
            self.on_message_update()
    
    def _remove_pending_messages_from_history(self) -> None:
        """
        チャット履歴から問い合わせ中のメッセージを削除します。
        """
        self.chat_history = [msg for msg in self.chat_history if not msg.get('is_pending', False)]
        
        # メッセージ更新時のコールバックを呼び出し
        if self.on_message_update:
            self.on_message_update()
    
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
        if self.translate_mode:
            text = GoogleTranslator(source='auto', target=self.translate_language).translate(text)
        self.chat_history.append({
            "role": "assistant",
            "name": name,
            "text": text,
            "icon": icon or "🤖",
            "component_id": component_id,
            "timestamp": datetime.now().isoformat()
        })
        
        # メッセージ更新時のコールバックを呼び出し
        if self.on_message_update:
            self.on_message_update()
    
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
        
        # メッセージ更新時のコールバックを呼び出し
        if self.on_message_update:
            self.on_message_update() 