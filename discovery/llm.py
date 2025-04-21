import os
import openai
import google.generativeai as genai
from typing import Literal, Optional, List, Dict
from langchain.memory import ConversationBufferMemory

class LLMClient:
    """
    A client class to interact with different Large Language Models (LLMs)
    like OpenAI and Gemini, with conversation memory support.
    """

    def __init__(self, openai_api_key: Optional[str] = None, google_api_key: Optional[str] = None):
        """
        Initializes the LLMClient and the conversation memory.

        Args:
            openai_api_key: OpenAI API key. Defaults to OS environment variable 'OPENAI_API_KEY'.
            google_api_key: Google API key. Defaults to OS environment variable 'GOOGLE_API_KEY'.
        """
        self._openai_api_key = openai_api_key or os.getenv("OPENAI_API_KEY")
        self._google_api_key = google_api_key or os.getenv("GOOGLE_API_KEY")

        if self._openai_api_key:
            openai.api_key = self._openai_api_key
        if self._google_api_key:
            genai.configure(api_key=self._google_api_key)

        # 会話メモリを初期化
        self.memory = ConversationBufferMemory(return_messages=True)

    def get_response(
        self,
        system_prompt: str,
        user_prompt: str,
        service: Literal["openai", "gemini"],
        model: str,
        thinking_budget: Optional[int] = None,
        save_memory: bool = False,
        use_memory: bool = False,
    ) -> str:
        """
        指定されたLLMサービスとモデルからレスポンスを取得します。会話メモリ機能もサポートします。

        Args:
            system_prompt: モデルの動作を制御するシステムプロンプト。
            user_prompt: ユーザーのクエリまたは指示。
            service: 使用するLLMサービス ('openai' または 'gemini')。
            model: 使用する具体的なモデル名 (例: 'gpt-4', 'gemini-pro')。
            thinking_budget: Geminiの思考プロセスのためのオプショナルなトークン予算。
                             'gemini' サービスの場合のみ適用。
                             デフォルトはNone (モデルのデフォルト動作)。
                             0を設定すると思考を無効化。
            save_memory: Trueの場合、現在の会話をメモリに保存。
            use_memory: Trueの場合、過去の会話履歴をプロンプトに含める。

        Returns:
            モデルが生成したテキストレスポンス。

        Raises:
            ValueError: サービスが未対応、APIキーが未設定、
                      またはthinking_budgetが無効な場合。
            Exception: API呼び出し中のエラー。
        """
        history_messages: List[Dict[str, str]] = []
        history_text: str = ""

        if use_memory:
            # メモリから過去の会話履歴を取得
            # ConversationBufferMemory(return_messages=True) の場合、 .chat_memory.messages に BaseMessage のリストが入る
            # これを OpenAI/Gemini で使える形式に変換する
            loaded_memory = self.memory.load_memory_variables({})
            # loaded_memory['history'] は BaseMessage のリスト
            base_messages = loaded_memory.get('history', [])

            # OpenAI 形式のメッセージリストを作成
            for msg in base_messages:
                if hasattr(msg, 'content'): # HumanMessage, AIMessage など
                   role = "user" if msg.type == "human" else "assistant"
                   history_messages.append({"role": role, "content": msg.content})

            # Gemini 形式のテキスト履歴を作成 (単純な連結)
            history_text = "\n".join([f"{'User' if msg.type == 'human' else 'AI'}: {msg.content}" for msg in base_messages])


        response_text = ""
        if service == "openai":
            if not self._openai_api_key:
                raise ValueError("OpenAI API key is not configured.")
            try:
                client = openai.OpenAI(api_key=self._openai_api_key)

                # プロンプトの組み立て (メモリ使用時)
                messages = [{"role": "system", "content": system_prompt}]
                if use_memory:
                    messages.extend(history_messages) # 過去の履歴を追加
                messages.append({"role": "user", "content": user_prompt}) # 現在のユーザープロンプトを追加

                response = client.chat.completions.create(
                    model=model,
                    messages=messages,
                )
                content = response.choices[0].message.content
                if content is None:
                    raise ValueError("OpenAI API returned an empty response.")
                response_text = content
            except Exception as e:
                print(f"Error calling OpenAI API: {e}")
                raise
        elif service == "gemini":
            if not self._google_api_key:
                raise ValueError("Google API key is not configured.")
            try:
                # プロンプトの組み立て (メモリ使用時)
                prompt_parts = [system_prompt]
                if use_memory and history_text:
                    prompt_parts.append("\n\n--- Conversation History ---\n" + history_text)
                prompt_parts.append("\n\n--- Current Prompt ---\n" + user_prompt)
                full_prompt = "\n".join(prompt_parts)

                gen_model = genai.GenerativeModel(model)

                generation_config = None
                if thinking_budget is not None:
                    if not isinstance(thinking_budget, int) or thinking_budget < 0:
                         raise ValueError("thinking_budget must be a non-negative integer.")
                    from google.generativeai import types
                    generation_config = types.GenerationConfig(
                        thinking_config=types.ThinkingConfig(thinking_budget=thinking_budget)
                    )

                response = gen_model.generate_content(
                    full_prompt,
                    generation_config=generation_config
                )
                response_text = response.text
            except Exception as e:
                print(f"Error calling Google Generative AI API: {e}")
                raise
        else:
            raise ValueError(f"Unsupported service: {service}. Choose 'openai' or 'gemini'.")

        # メモリへの保存 (save_memory が True の場合)
        if save_memory:
            self.memory.save_context({"input": user_prompt}, {"output": response_text})

        return response_text

    # メモリをクリアするメソッドを追加しても良い (任意)
    def clear_memory(self):
        """会話メモリをクリアします。"""
        self.memory.clear()

    # メモリの内容を参照するメソッドを追加
    def get_memory_string(self) -> str:
        """現在の会話メモリの内容を整形された文字列として返します。"""
        loaded_memory = self.memory.load_memory_variables({})
        base_messages = loaded_memory.get('history', [])
        if not base_messages:
            return "メモリは空です。"

        history_string = "--- Conversation History ---\n"
        for msg in base_messages:
            if hasattr(msg, 'content'):
                role = "User" if msg.type == "human" else "AI"
                history_string += f"{role}: {msg.content}\n"
        return history_string.strip()


# Example Usage (Optional - illustrating memory usage)
if __name__ == '__main__':
    # Make sure to set OPENAI_API_KEY and GOOGLE_API_KEY environment variables
    # and install langchain (`pip install langchain`)
    try:
        client = LLMClient()
        client.clear_memory() # Start with fresh memory for the example

        print("--- Conversation with Memory (OpenAI) ---")
        prompt1 = "私の名前はKenです。"
        print(f"User: {prompt1}")
        response1 = client.get_response(
            system_prompt="あなたはユーザーの名前を覚えるアシスタントです。",
            user_prompt=prompt1,
            service="openai",
            model="gpt-3.5-turbo",
            save_memory=True, # 記憶する
            use_memory=False # 最初は履歴を使わない
        )
        print(f"AI: {response1}")

        prompt2 = "私の名前を覚えていますか？"
        print(f"User: {prompt2}")
        response2 = client.get_response(
            system_prompt="あなたはユーザーの名前を覚えるアシスタントです。",
            user_prompt=prompt2,
            service="openai",
            model="gpt-3.5-turbo",
            save_memory=True, # 今回も記憶する (任意)
            use_memory=True   # 履歴を使う
        )
        print(f"AI: {response2}")

        client.clear_memory() # Gemini の例のためにメモリをクリア

        print("\n--- Conversation with Memory (Gemini) ---")
        prompt3 = "What is the capital of Japan?"
        print(f"User: {prompt3}")
        response3 = client.get_response(
            system_prompt="You are a helpful assistant.",
            user_prompt=prompt3,
            service="gemini",
            model="gemini-pro",
            save_memory=True,
            use_memory=False
        )
        print(f"AI: {response3}")

        prompt4 = "Repeat the capital I just asked about."
        print(f"User: {prompt4}")
        response4 = client.get_response(
            system_prompt="You are a helpful assistant.",
            user_prompt=prompt4,
            service="gemini",
            model="gemini-pro",
            save_memory=True,
            use_memory=True
        )
        print(f"AI: {response4}")

        # メモリの内容を確認
        print("\n--- Current Memory ---")
        print(client.get_memory_string())

        # メモリをクリア
        client.clear_memory()
        print("\n--- Memory After Clearing ---")
        print(client.get_memory_string())


    except (ImportError, ValueError) as e:
        print(f"Error: {e}")
        print("Please ensure LangChain is installed ('pip install langchain') and API keys are set.")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
