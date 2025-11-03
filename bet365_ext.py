# ========================================
# bet365_ext.py — Récupération automatique des cotes Bet365 via RapidAPI
# ========================================
import os
import requests
from dotenv import load_dotenv

# Charger les variables d'environnement (.env)
load_dotenv()

RAPIDAPI_KEY = os.getenv("BET365_API_KEY") or "b528065989msh3eaaa727584c2bfp1bb004jsncb1c00b50c4e"
RAPIDAPI_HOST = os.getenv("BET365_API_HOST") or "bet36528.p.rapidapi.com"
BASE_URL = f"https://{RAPIDAPI_HOST}"

HEADERS = {
    "x-rapidapi-key": RAPIDAPI_KEY,
    "x-rapidapi-host": RAPIDAPI_HOST
}

# ------------------------------------------------------------
# 🔍 Étape 1 — Rechercher le fixtureId par nom d'équipe
# ------------------------------------------------------------
def search_fixture_id_by_team(team_name: str):
    """
    Recherche le fixtureId Bet365 d'une équipe (ex: 'PSG', 'Marseille').
    Retourne le premier fixtureId trouvé, ou None.
    """
    if not team_name:
        print("[⚠️] Nom d'équipe manquant pour la recherche du fixtureId.")
        return None

    try:
        url = f"{BASE_URL}/search"
        params = {"query": team_name}
        response = requests.get(url, headers=HEADERS, params=params, timeout=10)

        if response.status_code != 200:
            print(f"[⚠️] Erreur HTTP {response.status_code} sur /search : {response.text}")
            return None

        data = response.json()
        # Structure : {"results": [{"id": "...", "title": "PSG - Marseille"}]}
        results = data.get("results") or []
        if not results:
            print(f"[ℹ️] Aucun résultat trouvé pour {team_name}")
            return None

        fixture_id = results[0].get("id")
        print(f"✅ Fixture trouvé pour {team_name} → {fixture_id}")
        return fixture_id

    except Exception as e:
        print(f"[⚠️] Erreur recherche fixtureId ({team_name}) : {e}")
        return None


# ------------------------------------------------------------
# ⚽ Étape 2 — Récupérer les cotes d’un match via fixtureId
# ------------------------------------------------------------
def get_bet365_odds(fixture_id: str):
    """
    Récupère les cotes Bet365 réelles pour un fixtureId donné.
    """
    if not fixture_id:
        print("[⚠️] Aucun fixtureId fourni à get_bet365_odds.")
        return {}

    try:
        url = f"{BASE_URL}/historical-odds"
        params = {"fixtureId": fixture_id}
        response = requests.get(url, headers=HEADERS, params=params, timeout=15)

        if response.status_code != 200:
            print(f"[⚠️] Erreur HTTP {response.status_code} sur /historical-odds : {response.text}")
            return {}

        data = response.json()
        print(f"✅ Cotes récupérées pour fixture {fixture_id}")
        return data

    except Exception as e:
        print(f"[⚠️] Erreur sur l'appel API Bet365 : {e}")
        return {}


# ------------------------------------------------------------
# 🧩 Étape 3 — Fonction combinée (cherche équipe + renvoie les cotes)
# ------------------------------------------------------------
def get_real_odds_from_bet365(home_team: str, away_team: str, date_str: str = None):
    """
    Recherche automatiquement le fixtureId via le nom d’équipe
    puis récupère les cotes Bet365 correspondantes.
    """
    print(f"🔍 Recherche du match {home_team} vs {away_team} sur Bet365...")

    try:
        search_query = f"{home_team} vs {away_team}" if away_team else home_team
        fixture_id = search_fixture_id_by_team(search_query)
        if not fixture_id:
            return {}

        odds_data = get_bet365_odds(fixture_id)
        if not odds_data:
            return {}

        # Extraction simplifiée des cotes clés
        odds_summary = {}
        try:
            markets = odds_data.get("results", [])[0].get("markets", [])
            for m in markets:
                name = m.get("name", "").lower()
                if "match winner" in name:
                    for o in m.get("odds", []):
                        val = o.get("name", "").lower()
                        if "home" in val:
                            odds_summary["odds_home"] = float(o.get("odds", 0))
                        elif "draw" in val:
                            odds_summary["odds_draw"] = float(o.get("odds", 0))
                        elif "away" in val:
                            odds_summary["odds_away"] = float(o.get("odds", 0))
                elif "over 1.5" in name:
                    odds_summary["odds_over_1_5"] = float(m.get("odds", [])[0].get("odds", 0))
                elif "both teams to score" in name:
                    odds_summary["odds_btts_yes"] = float(m.get("odds", [])[0].get("odds", 0))
        except Exception:
            pass

        print(f"✅ Cotes Bet365 récupérées : {odds_summary}")
        return odds_summary

    except Exception as e:
        print(f"[⚠️] Erreur get_real_odds_from_bet365 : {e}")
        return {}
