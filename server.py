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
    """Envoie un message texte Telegram"""
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, data={"chat_id": CHAT_ID, "text": msg})
    except Exception as e:
        print(f"[⚠️] Erreur Telegram message : {e}")

def send_file(file_path, caption=None):
    """Envoie un fichier (HTML, CSV...) sur Telegram"""
    try:
        if os.path.exists(file_path):
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendDocument"
            with open(file_path, "rb") as f:
                requests.post(url, data={"chat_id": CHAT_ID, "caption": caption or ""}, files={"document": f})
        else:
            send_message(f"⚠️ Fichier introuvable : {file_path}")
    except Exception as e:
        print(f"[⚠️] Erreur Telegram fichier : {e}")


@app.route("/")
def home():
    return "FootBot Flask API en ligne 🚀"


@app.route("/run_global")
def run_global():
    """Lance analyse_globale.py + envoie le fichier global"""
    send_message("⏰ Lancement automatique de l’analyse globale (analyse_globale.py)...")

    try:
        subprocess.run(["python", "analyse_globale.py"], check=False)
        send_message("✅ Analyse globale terminée — IC mis à jour.")
        
        # Envoi du rapport HTML global
        base = os.path.dirname(__file__)
        global_path = os.path.join(base, "analyse_globale_footbot.html")
        send_file(global_path, "📈 Rapport global FootBot — IC recalibrés")
    except Exception as e:
        send_message(f"⚠️ Erreur lors de l’exécution d’analyse_globale.py : {e}")

    return "Analyse globale exécutée avec succès."


@app.route("/run_main")
def run_main():
    """Lance main.py + envoie le rapport du jour"""
    send_message("⏰ Lancement automatique du rapport quotidien (main.py)...")

    try:
        subprocess.run(["python", "main.py"], check=False)

        today = datetime.now().strftime("%Y-%m-%d")
        base = os.path.dirname(__file__)
        report_name = f"FootBot — Profil Volume — {today}.html"
        report_path = os.path.join(base, report_name)

        if os.path.exists(report_path):
            send_file(report_path, f"📊 Rapport quotidien FootBot — {today}")
            send_message("✅ Rapport FootBot envoyé avec succès.")
        else:
            send_message(f"⚠️ Rapport du {today} introuvable après exécution.")
    except Exception as e:
        send_message(f"⚠️ Erreur lors de l’exécution de main.py : {e}")

    return "Rapport FootBot exécuté avec succès."


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
