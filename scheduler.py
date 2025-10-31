# ============================
# scheduler.py — FootBot Auto
# ============================
import schedule
import subprocess
import time
import shutil
import os
from datetime import datetime
import requests

BASE_DIR = os.path.dirname(__file__)
RAPPORTS_DIR = os.path.join(BASE_DIR, "rapports_quotidiens")

# === Configuration Telegram ===
TELEGRAM_TOKEN = "8367632752:AAHz_AV4d7oFDJYqqbnBKIctNv3l26TMQq8"
CHAT_ID = "810505075"  # Ton chat ID personnel

# === Fonction d'envoi Telegram ===
def send_telegram_message(text, file_path=None):
    """Envoie un message et optionnellement un fichier via Telegram."""
    try:
        # Envoi du message texte
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, data={"chat_id": CHAT_ID, "text": text})
        # Envoi d’un fichier (si fourni et existant)
        if file_path and os.path.exists(file_path):
            url_file = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendDocument"
            with open(file_path, "rb") as f:
                requests.post(url_file, data={"chat_id": CHAT_ID}, files={"document": f})
            print(f"📤 Fichier envoyé sur Telegram : {os.path.basename(file_path)}")
    except Exception as e:
        print(f"[⚠️] Erreur Telegram : {e}")

# === Analyse globale (02h00) ===
def run_analyse_globale():
    print("⏰ [02h00] Lancement de analyse_globale.py ...")
    subprocess.run(["python", os.path.join(BASE_DIR, "analyse_globale.py")], check=False)

    global_file = os.path.join(BASE_DIR, "analyse_globale_footbot.html")
    if os.path.exists(global_file):
        send_telegram_message("✅ Analyse globale terminée — IC mis à jour.", global_file)
    else:
        send_telegram_message("⚠️ Analyse globale terminée, mais le fichier HTML est introuvable.")

# === Rapport quotidien (11h00) ===
def run_main():
    print("⏰ [11h00] Lancement de main.py ...")
    subprocess.run(["python", os.path.join(BASE_DIR, "main.py")], check=False)

    today = datetime.now().strftime("%Y-%m-%d")
    report_name = f"FootBot — Profil Volume — {today}.html"
    src_path = os.path.join(BASE_DIR, report_name)
    dst_path = os.path.join(RAPPORTS_DIR, report_name)

    if os.path.exists(src_path):
        shutil.copy(src_path, dst_path)
        send_telegram_message(f"📊 Rapport quotidien {today} généré ✅", dst_path)
    else:
        send_telegram_message(f"⚠️ Rapport du {today} introuvable après exécution.")

# === Planification ===
schedule.every().day.at("02:00").do(run_analyse_globale)
schedule.every().day.at("11:00").do(run_main)

# === Mode exécution directe ou automatique ===
if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        if sys.argv[1] == "run_main":
            run_main()
        elif sys.argv[1] == "run_global":
            run_analyse_globale()
        else:
            print("Usage: python scheduler.py [run_main|run_global]")
    else:
        print("🕒 Scheduler FootBot actif. Les tâches quotidiennes sont planifiées.")
        print("   - analyse_globale à 02h00 (avec envoi du fichier HTML)")
        print("   - main.py à 11h00 (avec envoi du rapport quotidien)")
        print("   (laisser ce script tourner en arrière-plan)")
        while True:
            schedule.run_pending()
            time.sleep(30)
