import os
import sys
import json
import time
import requests
import websocket
from threading import Thread
from keep_alive import keep_alive
import schedule

# Carrega tokens e configurações do ambiente
def load_tokens():
    tokens_config = []
    for key in os.environ:
        if key.startswith("TOKEN"):
            token_index = key.replace("TOKEN", "")
            status = os.getenv(f"STATUS{token_index}", "online")
            custom_status = os.getenv(f"CUSTOM_STATUS{token_index}", "")
            join_call = os.getenv(f"JOIN_CALL{token_index}", "true").lower() == "true"
            channel_id = os.getenv(f"CHANNEL_ID{token_index}")
            guild_id = os.getenv(f"GUILD_ID{token_index}")
            tokens_config.append({
                "token": os.getenv(key),
                "status": status,
                "custom_status": custom_status,
                "join_call": join_call,
                "channel_id": channel_id,
                "guild_id": guild_id,
            })
    return tokens_config

tokens_config = load_tokens()
if not tokens_config:
    print("[ERROR] No tokens found in environment variables. Please add TOKEN1, TOKEN2, etc.")
    sys.exit()

# Valida o token com a API do Discord
def validate_token(token):
    headers = {"Authorization": token, "Content-Type": "application/json"}
    validate = requests.get("https://discord.com/api/v9/users/@me", headers=headers)
    if validate.status_code != 200:
        print(f"[ERROR] Invalid token: {token}")
        return None
    return validate.json()

# Obtém o application_id automaticamente
def get_application_id(token):
    headers = {"Authorization": token, "Content-Type": "application/json"}
    response = requests.get("https://discord.com/api/v9/applications/@me", headers=headers)
    if response.status_code == 200:
        return response.json()["id"]
    else:
        print(f"[ERROR] Failed to fetch application ID for token {token[:10]}... Error: {response.status_code}")
        return None

# Envia o comando /daily como interação
def send_daily_interaction(token, channel_id):
    application_id = get_application_id(token)
    if not application_id:
        print(f"[ERROR] Could not send /daily. Application ID is missing.")
        return

    url = "https://discord.com/api/v9/interactions"
    headers = {
        "Authorization": token,
        "Content-Type": "application/json"
    }
    data = {
        "type": 2,  # Tipo 2 é para comandos Slash
        "application_id": application_id,
        "channel_id": channel_id,
        "data": {
            "name": "daily",  # Nome do comando
            "type": 1  # Tipo do comando Slash
        }
    }
    response = requests.post(url, headers=headers, json=data)
    if response.status_code == 204:
        print(f"[SUCCESS] Sent /daily command in channel {channel_id}.")
    else:
        print(f"[ERROR] Failed to send /daily command in channel {channel_id}. Error: {response.status_code} - {response.text}")

# Mantém o bot online e envia batidas de coração
def onliner(token, status, custom_status, channel_id=None, guild_id=None):
    while True:
        try:
            ws = websocket.WebSocket()
            ws.connect("wss://gateway.discord.gg/?v=9&encoding=json")
            start = json.loads(ws.recv())
            heartbeat = start["d"]["heartbeat_interval"]
            
            # Autenticação inicial
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
            }
            ws.send(json.dumps(auth))
            
            # Atualização de status personalizado
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
            
            # Se configurado, entra no canal de voz
            if channel_id and guild_id:
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
                print(f"Token {token[:10]}... joined voice channel {channel_id} in guild {guild_id}.")
            
            # Mantém a conexão enviando heartbeat regularmente
            while True:
                ws.send(json.dumps({"op": 1, "d": None}))
                time.sleep(max(heartbeat / 1000, 40))  # Garante um intervalo de no máximo 40 segundos
        except Exception as e:
            print(f"[ERROR] Connection lost for token {token[:10]}... Reconnecting. Error: {e}")
            time.sleep(5)  # Aguarda 5 segundos antes de tentar reconectar

# Inicia múltiplos bots em threads separadas
def run_onliner():
    threads = []
    for config in tokens_config:
        token = config["token"]
        status = config["status"]
        custom_status = config["custom_status"]
        channel_id = config.get("channel_id")
        
        userinfo = validate_token(token)
        if userinfo:
            username = userinfo["username"]
            discriminator = userinfo["discriminator"]
            userid = userinfo["id"]
            print(f"Logged in as {username}#{discriminator} ({userid}).")
        else:
            continue
        
        # Cria uma nova thread para manter o bot online
        t = Thread(target=onliner, args=(token, status, custom_status, channel_id))
        t.start()
        threads.append(t)

        # Agenda o envio do comando /daily
        if channel_id:
            schedule.every().day.at("14:00").do(send_daily_interaction, token=token, channel_id=channel_id)

    # Aguarda todas as threads finalizarem (em execução contínua)
    while True:
        schedule.run_pending()
        time.sleep(1)

# Inicia o servidor para manter vivo
keep_alive()
run_onliner()
