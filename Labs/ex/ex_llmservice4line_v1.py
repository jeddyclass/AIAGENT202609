import hmac, hashlib, base64, json, requests, os
from flask import Flask, request, abort
from pathlib import Path

CONFIG_FILE = Path.home() / '.config/rc-bot/config.env'

app = Flask(__name__)

def load_config():
    cfg = {}
    for line in CONFIG_FILE.read_text().splitlines():
        if '=' in line and not line.startswith('#'):
            k, v = line.split('=', 1)
            cfg[k.strip()] = v.strip()
    return cfg

def verify_signature(body, signature, secret):
    h = hmac.new(secret.encode('utf-8'), body, hashlib.sha256).digest()
    return hmac.compare_digest(base64.b64encode(h).decode(), signature)

def reply_line(reply_token, text, token):
    if len(text) > 4900:
        text = text[:4900] + '...'
    requests.post(
        'https://api.line.me/v2/bot/message/reply',
        headers={'Content-Type': 'application/json',
                 'Authorization': f'Bearer {token}'},
        json={'replyToken': reply_token,
              'messages': [{'type': 'text', 'text': text}]}
    )

def ask_local_llm(user_message, cfg):
    headers = {
        'Authorization': f"Bearer {cfg['OPENWEBUI_API_KEY']}",
        'Content-Type': 'application/json'
    }
    payload = {
        'model': cfg['LLM_MODEL'],
        'messages': [
            {"role": "system", "content": "你是一個部署在 Homelab 地端的 AI 助手。請用繁體中文親切、簡短地回答問題。"},
            {"role": "user", "content": user_message}
        ],
        'temperature': 0.7
    }
    try:
        response = requests.post(cfg['OPENWEBUI_API_URL'], headers=headers, json=payload, timeout=60)
        if response.status_code == 200:
            res_json = response.json()
            return res_json['choices'][0]['message']['content'].strip()
        else:
            return f"❌ 地端 LLM 回傳錯誤 (Status: {response.status_code}): {response.text}"
    except Exception as e:
        return f"❌ 無法連線至地端 LLM: {str(e)}"

@app.route('/webhook', methods=['POST'])
def webhook():
    cfg  = load_config()
    body = request.get_data()
    sig  = request.headers.get('X-Line-Signature', '')

    if not verify_signature(body, sig, cfg['LINE_CHANNEL_SECRET']):
        abort(400)

    for event in json.loads(body).get('events', []):
        if event.get('type') != 'message':
            continue
        if event['message'].get('type') != 'text':
            continue

        sender_uid = event.get('source', {}).get('userId', '')
        reply_token = event.get('replyToken')
        user_text   = event['message']['text'].strip()
        token       = cfg['LINE_CHANNEL_ACCESS_TOKEN']

        # ── 臨時功能：讓管理者查自己的 LINE UID ──
        if user_text == '#uid':
            reply_line(reply_token, f'你的 LINE UID：{sender_uid}', token)
            continue

        # ── 白名單檢查 ──
        # 如果 ALLOWED_UID 還沒設定，允許所有人傳送 #uid，但拒絕 LLM 對話
        if cfg.get('ALLOWED_UID', '') == '' or cfg.get('ALLOWED_UID') == '先留空_等Step5取得後再填入':
            reply_line(reply_token, f'⚠️ 系統尚未設定安全白名單。請傳送 #uid 取得您的 UID 並寫入設定檔。', token)
            continue

        if sender_uid != cfg.get('ALLOWED_UID', ''):
            # 非白名單用戶，直接無視
            continue

        # ── 呼叫地端 LLM ──
        llm_response = ask_local_llm(user_text, cfg)
        reply_line(reply_token, llm_response, token)

    return 'OK'

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5050)
