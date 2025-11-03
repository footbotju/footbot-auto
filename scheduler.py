# ============================
# scheduler.py — FootBot Auto (post-match refresh)
# ============================
import schedule
import subprocess
import time
import shutil
import os
from datetime import datetime, timedelta
import requests

BASE_DIR = os.path.dirname(__file__)
RAPPORTS_DIR = os.path.join(BASE_DIR, "rapports_quotidiens")

# === Configuration Telegram ===
TELEGRAM_TOKEN = "8367632752:AAHz_AV4d7oFDJYqqbnBKIctNv3l26TMQq8"
CHAT_IDS = [810505075, 751391176]

# === Fonction d'envoi Telegram ===
def send_telegram_message(text, file_path=None):
    """Envoie un message et optionnellement un fichier via Telegram."""
    try:
        for CHAT_ID in CHAT_IDS:
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

# === Mise à jour post-match (09h00) ===
def run_refresh_yesterday():
    """Exécute main.py --refresh pour mettre à jour les scores du jour précédent."""
    print("⏰ [09h00] Lancement de main.py --refresh pour mettre à jour les scores du jour précédent...")
    subprocess.run(["python", os.path.join(BASE_DIR, "main.py"), "--refresh"], check=False)

    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    report_name = f"FootBot — Profil Volume — {yesterday}.html"
    src_path = os.path.join(BASE_DIR, report_name)
    dst_path = os.path.join(RAPPORTS_DIR, report_name)

    if os.path.exists(src_path):
        shutil.copy(src_path, dst_path)
        send_telegram_message(f"📊 Rapport du {yesterday} mis à jour avec les scores finaux ✅", dst_path)
    else:
        send_telegram_message(f"⚠️ Rapport du {yesterday} introuvable après refresh.")

# === Analyse globale (09h30) ===
def run_analyse_globale():
    print("⏰ [09h30] Lancement de analyse_globale.py ...")
    subprocess.run(["python", os.path.join(BASE_DIR, "analyse_globale.py")], check=False)

    global_file = os.path.join(BASE_DIR, "analyse_globale_footbot.html")
    if os.path.exists(global_file):
        send_telegram_message("✅ Analyse globale terminée — IC et seuils mis à jour.", global_file)
    else:
        send_telegram_message("⚠️ Analyse globale terminée, mais le fichier HTML est introuvable.")

# === Planification ===
schedule.every().day.at("09:00").do(run_refresh_yesterday)
schedule.every().day.at("09:30").do(run_analyse_globale)

# === Mode exécution directe ou automatique ===
if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        if sys.argv[1] == "run_refresh":
            run_refresh_yesterday()
        elif sys.argv[1] == "run_global":
            run_analyse_globale()
        else:
            print("Usage: python scheduler.py [run_refresh|run_global]")
    else:
        print("🕒 Scheduler FootBot actif. Les tâches quotidiennes sont planifiées.")
        print("   - main.py --refresh (jour précédent) à 09h00 → mise à jour des scores + envoi Telegram")
        print("   - analyse_globale.py à 09h30 → recalcul global + envoi Telegram")
        print("   (laisser ce script tourner en arrière-plan sous Termux avec nohup)")
        while True:
            schedule.run_pending()
            time.sleep(30)
