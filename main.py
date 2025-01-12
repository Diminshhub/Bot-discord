import os
import sys
import json
import time
import requests
import websocket
import schedule
from datetime import datetime
from threading import Thread
from keep_alive import keep_alive

# Função para carregar tokens e configurações de status/call
def load_tokens():
    tokens_config = []
    for key in os.environ:
        if key.startswith("TOKEN"):  # Verifica todas as variáveis que começam com 'TOKEN'
            token_index = key.replace("TOKEN", "")
            status = os.getenv(f"STATUS{token_index}", "online")  # Status padrão: online
            custom_status = os.getenv(f"CUSTOM_STATUS{token_index}", "")  # Sem status personalizado por padrão
            join_call = os.getenv(f"JOIN_CALL{token_index}", "true").lower() == "true"  # Default: entra na call
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
    validate = requests.get("https://canary.discordapp.com/api/v9/users/@me", headers=headers)
    if validate.status_code != 200:
        print(f"[ERROR] Invalid token: {token}")
        return None
    return validate.json()

def send_message(token, channel_id, message):
    url = f"https://discord.com/api/v9/channels/{channel_id}/messages"
    headers = {"Authorization": token, "Content-Type": "application/json"}
    data = {"content": message}
    response = requests.post(url, headers=headers, json=data)
    if response.status_code == 200:
        print(f"[INFO] Message sent: {message}")
    else:
        print(f"[ERROR] Failed to send message: {response.text}")

def daily_task():
    for config in tokens_config:
        token = config["token"]
        send_message(token, "1292297163182702663", "/daily")  # Substitua CANAL_ID pelo ID do canal específico

def onliner(token, status, custom_status):
    ws = websocket.WebSocket()
    ws.connect("wss://gateway.discord.gg/?v=9&encoding=json")
    start = json.loads(ws.recv())
    heartbeat = start["d"]["heartbeat_interval"]
    auth = {
        "op": 2,
        "d": {
            "token": token,
            "properties": {
                "$os": "Windows 10",
                "$browser": "Google Chrome",
                "$device": "Windows",
            },
            "presence": {"status": status, "afk": False},
        },
        "s": None,
        "t": None,
    }
    ws.send(json.dumps(auth))
    cstatus = {
        "op": 3,
        "d": {
            "since": 0,
            "activities": [
                {
                    "type": 4,
                    "state": custom_status,
                    "name": "Custom Status",
                    "id": "custom",
                }
            ],
            "status": status,
            "afk": False,
        },
    }
    ws.send(json.dumps(cstatus))
    online = {"op": 1, "d": "None"}
    time.sleep(heartbeat / 1000)
    ws.send(json.dumps(online))

def join_voice_channel(token, channel_id, guild_id):
    ws = websocket.WebSocket()
    ws.connect("wss://gateway.discord.gg/?v=9&encoding=json")
    start = json.loads(ws.recv())
    auth = {
        "op": 2,
        "d": {
            "token": token,
            "properties": {
                "$os": "Windows 10",
                "$browser": "Google Chrome",
                "$device": "Windows",
            },
        },
    }
    ws.send(json.dumps(auth))
    voice_state_update = {
        "op": 4,
        "d": {
            "guild_id": guild_id,
            "channel_id": channel_id,
            "self_mute": True,
            "self_deaf": False,
        },
    }
    ws.send(json.dumps(voice_state_update))
    print(f"Token {token[:10]}... joined voice channel {channel_id} and stayed muted.")

def run_onliner():
    for config in tokens_config:
        token = config["token"]
        status = config["status"]
        custom_status = config["custom_status"]
        
        userinfo = validate_token(token)
        if userinfo:
            username = userinfo["username"]
            discriminator = userinfo["discriminator"]
            userid = userinfo["id"]
            print(f"Logged in as {username}#{discriminator} ({userid}).")
        else:
            continue

        # Atualiza o status do token
        onliner(token, status, custom_status)

        # Faz o bot entrar no canal de voz, se necessário
        if config["join_call"]:
            join_voice_channel(token, channel_id, guild_id)

# IDs do canal de voz e servidor
channel_id = "1305648119173615626"
guild_id = "1226910384569585664"

# Agendar tarefa diária às 3 da manhã
schedule.every().day.at("03:00").do(daily_task)

def schedule_runner():
    while True:
        schedule.run_pending()
        time.sleep(1)

# Manter o bot ativo
keep_alive()
Thread(target=schedule_runner).start()
run_onliner()
