document.addEventListener('DOMContentLoaded', () => {
    const chatForm = document.getElementById('chat-form');
    const chatMessages = document.getElementById('chat-messages');
    const endpoint = document.getElementById('endpoint');
    const messageInput = document.getElementById('msg');
    const clearHistoryBtn = document.getElementById('clear-history');
    const debugModeBtn = document.getElementById('debug-mode');
    
    // テンプレート
    const userMessageTemplate = document.getElementById('user-message-template');
    const botMessageTemplate = document.getElementById('bot-message-template');
    
    // WebSocketの使用有無
    const useWebSocket = window.USE_WEBSOCKET === "true";
    let socket = null;
    
    // WebSocketが有効な場合、接続する
    if (useWebSocket) {
        // SocketIOの接続オプション
        const socketOptions = {
            reconnection: true,         // 再接続を有効化
            reconnectionAttempts: 5,    // 再接続の試行回数
            reconnectionDelay: 1000,    // 再接続の遅延（ミリ秒）
            timeout: 20000              // タイムアウト（ミリ秒）
        };
        
        socket = io(socketOptions);
        
        // WebSocketイベントの設定
        socket.on('connect', () => {
            console.log('WebSocket接続完了 - ID:', socket.id);
            addSystemMessage('WebSocketサーバーに接続しました', 'success');
            
            // 接続後に履歴データをリクエスト
            socket.emit('request_history');
        });
        
        socket.on('disconnect', () => {
            console.log('WebSocket切断');
            addSystemMessage('WebSocketサーバーから切断されました', 'error');
        });
        
        socket.on('connect_error', (error) => {
            console.error('WebSocket接続エラー:', error);
            addSystemMessage('WebSocketサーバーへの接続に失敗しました', 'error');
        });
        
        socket.on('chat_updated', (data) => {
            console.log('チャット更新イベント受信', data);
            // チャット履歴が更新された
            const history = data.history || [];
            console.log(`更新: ${history.length}件のメッセージ (前回: ${lastHistoryLength}件)`);
            updateChatHistoryDisplay(history);
            lastHistoryLength = history.length;
        });
    } else {
        // ポーリング間隔（ミリ秒）
        const POLLING_INTERVAL = 2000;
        let pollingTimer = null;
        
        // ポーリングを開始
        startPolling();
    }
    
    let lastHistoryLength = 0;
    
    // 初期状態で履歴を取得
    fetchChatHistory();
    
    // メッセージ送信
    chatForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const message = messageInput.value.trim();
        const endpointValue = endpoint.value.trim();
        
        if (!message || !endpointValue) {
            return;
        }
        
        // 入力フィールドをクリア（WebSocketの場合は即座にクリア）
        messageInput.value = '';
        
        // WebSocketを使わない場合のみUIを手動で更新
        if (!useWebSocket) {
            // UIに即座にユーザーメッセージを表示
            addUserMessage(message);
            
            // 問い合わせ中の表示を追加
            const pendingMessageId = addPendingMessage();
        }
        
        try {
            // WebSocketを使わない場合はポーリングを一時停止（重複防止のため）
            if (!useWebSocket && typeof stopPolling === 'function') {
                stopPolling();
            }
            
            const requestBody = {
                message: message,
                endpoint: endpointValue
            };
            
            // APIにメッセージを送信
            const response = await fetch('/api/send_message', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(requestBody)
            });
            
            // WebSocketを使わない場合のみ手動で表示を更新
            if (!useWebSocket) {
                // 問い合わせ中の表示を削除
                removePendingMessage(pendingMessageId);
            }
            
            const data = await response.json();
            
            if (data.error) {
                console.error('Error:', data.error);
                addSystemMessage('エラーが発生しました: ' + data.error, 'error');
                return;
            }
            
            // WebSocketを使用しない場合は手動で履歴を更新
            if (!useWebSocket) {
                // レスポンスメッセージを表示
                const history = data.history || [];
                updateChatHistoryDisplay(history);
                
                // ポーリングを再開
                if (typeof startPolling === 'function') {
                    startPolling();
                }
            }
        } catch (error) {
            console.error('Error:', error);
            addSystemMessage('通信エラーが発生しました', 'error');
            
            // WebSocketを使用しない場合はポーリングを再開
            if (!useWebSocket && typeof startPolling === 'function') {
                startPolling();
            }
        }
    });
    
    // 履歴クリア
    clearHistoryBtn.addEventListener('click', async () => {
        try {
            const response = await fetch('/api/clear_history', {
                method: 'POST'
            });
            
            const data = await response.json();
            
            if (data.success) {
                // WebSocketを使用しない場合は手動でクリア
                if (!useWebSocket) {
                    chatMessages.innerHTML = '';
                    addSystemMessage('履歴がクリアされました', 'success');
                    lastHistoryLength = 0;
                }
            }
        } catch (error) {
            console.error('Error clearing history:', error);
            addSystemMessage('履歴のクリアに失敗しました', 'error');
        }
    });
    
    // ポーリングを開始する関数（WebSocketを使用しない場合のみ）
    function startPolling() {
        if (!useWebSocket && pollingTimer === null) {
            pollingTimer = setInterval(pollChatHistory, POLLING_INTERVAL);
        }
    }
    
    // ポーリングを停止する関数（WebSocketを使用しない場合のみ）
    function stopPolling() {
        if (!useWebSocket && pollingTimer !== null) {
            clearInterval(pollingTimer);
            pollingTimer = null;
        }
    }
    
    // 定期的にチャット履歴を取得して表示を更新（WebSocketを使用しない場合のみ）
    async function pollChatHistory() {
        if (useWebSocket) return; // WebSocketを使用する場合はポーリングしない
        
        try {
            const response = await fetch('/api/chat_history');
            const history = await response.json();
            
            // 履歴の長さが変わった場合のみ更新
            if (history.length !== lastHistoryLength) {
                updateChatHistoryDisplay(history);
                lastHistoryLength = history.length;
            }
        } catch (error) {
            console.error('Error polling chat history:', error);
            // エラー表示は行わない（ポーリングなので）
        }
    }
    
    // チャット履歴を取得する関数
    async function fetchChatHistory() {
        try {
            const response = await fetch('/api/chat_history');
            const history = await response.json();
            
            // 履歴を表示
            updateChatHistoryDisplay(history);
            lastHistoryLength = history.length;
        } catch (error) {
            console.error('Error fetching chat history:', error);
            addSystemMessage('履歴の取得に失敗しました', 'error');
        }
    }
    
    // 履歴表示を更新する関数
    function updateChatHistoryDisplay(history) {
        // 履歴が空の場合
        if (history.length === 0) {
            chatMessages.innerHTML = '';
            return;
        }
        
        // 現在の最後のメッセージを取得
        const currentMessages = Array.from(chatMessages.children)
            .filter(el => !el.classList.contains('pending-message') && !el.classList.contains('system-message'));
        
        // 新しいメッセージがあるかどうか
        let hasNewMessages = false;

        // スクロール位置を保存
        const isScrolledToBottom = chatMessages.scrollHeight - chatMessages.clientHeight <= chatMessages.scrollTop + 10;
        
        // 問い合わせ中のメッセージを保持
        const pendingMessages = Array.from(chatMessages.children)
            .filter(el => el.classList.contains('pending-message'));
            
        // 新しいメッセージがあれば追加
        history.forEach((message, index) => {
            // 問い合わせ中のメッセージは表示しない
            if (message.is_pending) return;
            
            const timestamp = new Date(message.timestamp);
            const messageId = `msg-${message.role}-${index}`;
            
            // 既存のメッセージを探す
            const existingMessage = document.getElementById(messageId);
            
            if (!existingMessage) {
                hasNewMessages = true;
                
                if (message.role === 'user') {
                    addUserMessage(message.text, timestamp, messageId);
                } else if (message.role === 'assistant') {
                    addBotMessage(message.text, message.name, message.icon, timestamp, messageId);
                }
            }
        });
        
        // 問い合わせ中のメッセージを再追加（常に最後に表示）
        pendingMessages.forEach(el => {
            chatMessages.appendChild(el);
        });
        
        // 新しいメッセージがあれば、最下部にスクロール
        if (hasNewMessages && isScrolledToBottom) {
            scrollToBottom();
        }
    }
    
    // 問い合わせ中のメッセージを追加
    function addPendingMessage() {
        const pendingId = 'pending-' + Date.now();
        const div = document.createElement('div');
        div.id = pendingId;
        div.classList.add('message', 'bot-message', 'pending-message');
        div.innerHTML = `
            <div class="message-header">
                <span class="message-icon">🤖</span>
                <span class="message-sender">AI</span>
            </div>
            <p class="message-text typing-animation">応答を生成中...</p>
            <div class="message-time">${formatTime(new Date())}</div>
        `;
        
        chatMessages.appendChild(div);
        scrollToBottom();
        
        return pendingId;
    }
    
    // 問い合わせ中のメッセージを削除
    function removePendingMessage(pendingId) {
        const pendingMessage = document.getElementById(pendingId);
        if (pendingMessage) {
            pendingMessage.remove();
        }
    }
    
    // ユーザーメッセージを追加
    function addUserMessage(text, timestamp = new Date(), messageId = null) {
        const clone = userMessageTemplate.content.cloneNode(true);
        const messageDiv = clone.querySelector('.message');
        
        if (messageId) {
            messageDiv.id = messageId;
        }
        
        messageDiv.querySelector('.message-text').textContent = text;
        messageDiv.querySelector('.message-time').textContent = formatTime(timestamp);
        
        chatMessages.appendChild(messageDiv);
        scrollToBottom();
    }
    
    // ボットメッセージを追加
    function addBotMessage(text, sender, icon, timestamp = new Date(), messageId = null) {
        const clone = botMessageTemplate.content.cloneNode(true);
        const messageDiv = clone.querySelector('.message');
        
        if (messageId) {
            messageDiv.id = messageId;
        }
        
        messageDiv.querySelector('.message-text').textContent = text;
        messageDiv.querySelector('.message-sender').textContent = sender || 'Bot';
        messageDiv.querySelector('.message-icon').textContent = icon || '🤖';
        messageDiv.querySelector('.message-time').textContent = formatTime(timestamp);
        
        chatMessages.appendChild(messageDiv);
        scrollToBottom();
    }
    
    // システムメッセージを追加（エラーや通知）
    function addSystemMessage(text, type = 'info') {
        const messageDiv = document.createElement('div');
        messageDiv.classList.add('message', 'system-message', `system-message-${type}`);
        
        const messageText = document.createElement('p');
        messageText.classList.add('message-text');
        messageText.textContent = text;
        
        messageDiv.appendChild(messageText);
        chatMessages.appendChild(messageDiv);
        
        scrollToBottom();
    }
    
    // 最下部にスクロール
    function scrollToBottom() {
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }
    
    // 時刻をフォーマット
    function formatTime(date) {
        return date.toLocaleTimeString('ja-JP', {
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit'
        });
    }
}); 