from flask import Flask
import subprocess
import os
import requests
from datetime import datetime

app = Flask(__name__)

# === CONFIGURATION TELEGRAM ===
TELEGRAM_TOKEN = "8367632752:AAHz_AV4d7oFDJYqqbnBKIctNv3l26TMQq8"
CHAT_ID = "810505075"  # Ton ID Telegram

def send_message(msg):
    """Envoie un message Telegram"""
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, data={"chat_id": CHAT_ID, "text": msg})
    except Exception as e:
        print(f"[⚠️] Erreur Telegram : {e}")

@app.route("/")
def home():
    return "FootBot Flask API en ligne 🚀"

@app.route("/run_global")
def run_global():
    send_message("⏰ Lancement automatique de l’analyse globale (analyse_globale.py)...")
    subprocess.run(["python", "analyse_globale.py"], check=False)
    send_message("✅ Analyse globale terminée et IC mis à jour.")
    return "Analyse globale exécutée avec succès."

@app.route("/run_main")
def run_main():
    send_message("⏰ Lancement automatique du rapport quotidien (main.py)...")
    subprocess.run(["python", "main.py"], check=False)
    today = datetime.now().strftime("%Y-%m-%d")
    send_message(f"✅ Rapport quotidien FootBot du {today} généré.")
    return "Rapport FootBot exécuté avec succès."

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
