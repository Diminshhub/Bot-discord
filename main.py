import os
import sys
import json
import time
import requests
import websocket
import schedule
from threading import Thread
from keep_alive import keep_alive

# Função para carregar tokens e configurações de status/call
def load_tokens():
    tokens_config = []
    for key in os.environ:
        if key.startswith("TOKEN"):
            token_index = key.replace("TOKEN", "")
            status = os.getenv(f"STATUS{token_index}", "online")
            custom_status = os.getenv(f"CUSTOM_STATUS{token_index}", "")
            join_call = os.getenv(f"JOIN_CALL{token_index}", "true").lower() == "true"
            tokens_config.append({
                "token": os.getenv(key),
                "status": status,
                "custom_status": custom_status,
                "join_call": join_call
            })
    return tokens_config

tokens_config = load_tokens()
if not tokens_config:
    print("[ERROR] No tokens found in environment variables. Please add TOKEN1, TOKEN2, etc.")
    sys.exit()

def validate_token(token):
    headers = {"Authorization": token, "Content-Type": "application/json"}
    try:
        response = requests.get("https://canary.discordapp.com/api/v9/users/@me", headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"[ERROR] Token validation failed: {e}")
        return None

def send_message(token, channel_id, message):
    url = f"https://discord.com/api/v9/channels/{channel_id}/messages"
    headers = {"Authorization": token, "Content-Type": "application/json"}
    data = {"content": message}
    try:
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()
        print(f"[INFO] Message sent to channel {channel_id}: {message}")
    except requests.exceptions.RequestException as e:
        print(f"[ERROR] Failed to send message: {e}")

def daily_task():
    for config in tokens_config:
        token = config["token"]
        # Substitua o ID abaixo pelo ID do canal correto
        send_message(token, "1292297163182702663", "/daily")

def onliner(token, status, custom_status):
    ws = websocket.WebSocket()
    try:
        ws.connect("wss://gateway.discord.gg/?v=9&encoding=json")
        start = json.loads(ws.recv())
        heartbeat = start["d"]["heartbeat_interval"]
        auth = {
            "op": 2,
            "d": {
                "token": token,
                "properties": {
                    "$os": "Windows 10",
                    "$browser": "Chrome",
                    "$device": "Windows",
                },
                "presence": {"status": status, "afk": False},
            },
        }
        ws.send(json.dumps(auth))
        online = {"op": 1, "d": None}
        while True:
            time.sleep(heartbeat / 1000)
            ws.send(json.dumps(online))
    except Exception as e:
        print(f"[ERROR] WebSocket error: {e}")
    finally:
        ws.close()

def schedule_runner():
    while True:
        schedule.run_pending()
        time.sleep(1)

# Configurar tarefa diária
schedule.every().day.at("03:00").do(daily_task)

# Manter o bot ativo
keep_alive()
Thread(target=schedule_runner).start()

for config in tokens_config:
    token = config["token"]
    status = config["status"]
    custom_status = config["custom_status"]

    userinfo = validate_token(token)
    if userinfo:
        print(f"Logged in as {userinfo['username']}#{userinfo['discriminator']} ({userinfo['id']}).")
        Thread(target=onliner, args=(token, status, custom_status)).start()
