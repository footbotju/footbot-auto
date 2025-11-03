import os, requests, json
from dotenv import load_dotenv
load_dotenv()

API_HOST = os.getenv("BET365_API_HOST")
API_KEY  = os.getenv("BET365_API_KEY")
HEADERS  = {"x-rapidapi-key": API_KEY, "x-rapidapi-host": API_HOST}

date = "2025-11-03"
params = {"sportId": "10", "from": date, "to": date, "hasOdds": "true"}

r = requests.get(f"https://{API_HOST}/fixtures", headers=HEADERS, params=params)
print("Status:", r.status_code)

try:
    data = r.json()
    matches = data.get("results") or data
    print(f"\nNombre de matchs trouvés Bet365 : {len(matches)}\n")
    print(json.dumps(matches[:10], indent=2, ensure_ascii=False))  # affiche les 10 premiers VRAIS
except:
    print("\nRéponse brute :", r.text)
