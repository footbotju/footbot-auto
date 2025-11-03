# ================================
# api_football_ext.py — FootBot PRO
# Compatibles: Python 3.9+
# Dernier patch: 2025-10-23
# ================================
import os
import time
import json
import math
import requests
from datetime import datetime, timezone, timedelta

# ----------------------------------------------------
# Configuration (.env) — lu par main.py via dotenv
# ----------------------------------------------------
API_KEY = os.getenv("API_FOOTBALL_KEY", "").strip()
API_BASE = "https://v3.football.api-sports.io"
SLEEP_API = float(os.getenv("SLEEP_API", "0.2"))
MAX_FIXTURES = int(os.getenv("MAX_FIXTURES", "0"))  # 0 = illimité ✅
USE_INJURIES = os.getenv("USE_INJURIES", "true").lower() == "true"

DEFAULT_TIMEOUT = 12
HEADERS = {"x-apisports-key": API_KEY, "Accept": "application/json"}


# =======================================
#  CACHE COTES FOOTBOT (Over 1.5 / BTTS)
# =======================================
CACHE_FILE = os.path.join(os.path.dirname(__file__), "cache_odds.json")

def _load_cache():
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

# ===================== CACHE GLOBAL INTELLIGENT =====================
GLOBAL_CACHE = {}
TEAM_FORM_CACHE = {}

def cache_call(key, fn, *args, **kwargs):
    """Mémorise le résultat d’une fonction lente pour éviter les appels multiples."""
    if key in GLOBAL_CACHE:
        return GLOBAL_CACHE[key]
    val = fn(*args, **kwargs)
    GLOBAL_CACHE[key] = val
    return val

def get_recent_form_cached_smart(team_id, league_id, season, side):
    """Version ultra-rapide de get_recent_form avec cache d’équipe."""
    key = (team_id, league_id, season, side)
    if key not in TEAM_FORM_CACHE:
        TEAM_FORM_CACHE[key] = get_recent_form(team_id, league_id, season, side)
    return TEAM_FORM_CACHE[key]


def _save_cache(cache):
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache, f, indent=2, ensure_ascii=False)
    except Exception:
        pass

ODDS_CACHE = _load_cache()
TODAY = datetime.now().strftime("%Y-%m-%d")

# ----------------------------------------------------
# Helpers
# ----------------------------------------------------
def _api_get(path: str, params: dict):
    """
    Appel GET avec gestion de clé, timeout, backoff simple.
    path: "/fixtures" etc.
    """
    if not API_KEY:
        raise RuntimeError("API_FOOTBALL_KEY manquant dans .env")

    url = API_BASE + (path if path.startswith("/") else f"/{path}")
    backoff = 0.5
    for attempt in range(3):
        try:
            r = requests.get(url, headers=HEADERS, params=params, timeout=DEFAULT_TIMEOUT)
            r.raise_for_status()
            j = r.json()
            # API renvoie {"response":[...]} ou {"response":{...}}
            return j.get("response", [])
        except Exception:
            if attempt == 2:
                raise
            time.sleep(backoff)
            backoff *= 2
    return []

def _sleep():
    if SLEEP_API > 0:
        time.sleep(SLEEP_API)

def _safe_float(x, default=0.0):
    try:
        return float(x)
    except Exception:
        return default

# ----------------------------------------------------
# 1) FIXTURES DU JOUR (version France UTC+2)
# ----------------------------------------------------
from datetime import datetime, timedelta

def get_fixtures_by_date(yyyy_mm_dd: str):
    """
    Récupère les matchs de la date donnée en heure française (UTC+2).
    Exemple : si on entre 2025-10-24 → on obtient bien les matchs du 24 octobre heure FR.
    """
    # ⚙️ Ajuste pour que la France (UTC+2) corresponde aux bons créneaux API
    date_obj = datetime.strptime(yyyy_mm_dd, "%Y-%m-%d") + timedelta(hours=2)
    params = {"date": date_obj.strftime("%Y-%m-%d")}
    data = _api_get("/fixtures", params)
    _sleep()

    fixtures = []
    for it in data[:MAX_FIXTURES if MAX_FIXTURES > 0 else len(data)]:
        try:
            f = it["fixture"]
            l = it["league"]
            t = it["teams"]

            fixtures.append({
                "id": f["id"],
                "date_utc": f.get("date"),
                "league_id": l["id"],
                "league_name": l["name"],
                "country": l.get("country", ""),
                "season": l.get("season"),
                "referee": f.get("referee"),
                "venue": f.get("venue", {}),
                "home_id": t["home"]["id"],
                "away_id": t["away"]["id"],
                "home_team": t["home"]["name"],
                "away_team": t["away"]["name"],

                # ✅ Récupération correcte du score réel et statut du match
                "score_home": it.get("goals", {}).get("home"),
                "score_away": it.get("goals", {}).get("away"),
                "status": f.get("status", {}).get("short"),  # ex: "FT", "NS", "LIVE"
            })

        except Exception:
            continue

    return fixtures



# ==========================================================
#  COTES : Injection via fetch_odds_for_date (API-Football)
# ==========================================================
from api_football_odds import fetch_odds_for_date
from datetime import datetime

def enrich_with_odds_and_markets(fixtures):
    """
    Ajoute les cotes dans chaque fixture depuis l'API-Football (requête globale par date)
    Champs ajoutés :
      - odds_home / odds_draw / odds_away
      - odds_over_1_5
      - odds_btts_yes
      - odds_team_home / odds_team_away
    ✅ 100 % pré-match
    ✅ Priorité Bet365, fallback bookmaker suivant
    """
    if not fixtures:
        return fixtures

    # Force date au format YYYY-MM-DD
    today = (fixtures[0].get("date_utc") or "").split("T")[0]


    print(f"[ODDS] Récupération des cotes pour {today} ...")
    odds_map = fetch_odds_for_date(today)

    for fx in fixtures:
        fid = fx.get("id") or fx.get("fixture_id")
        if not fid:
            continue

        if fid in odds_map:
            fx.update(odds_map[fid])   # merge dict of odds into fixture
            print(f"[ODDS OK] {fx.get('home_team')} vs {fx.get('away_team')}")
        else:
            print(f"[ODDS MISS] {fx.get('home_team')} vs {fx.get('away_team')} (id={fid})")

    return fixtures



# ----------------------------------------------------
# 3) FORME RÉCENTE — 5–10 derniers matchs
# ----------------------------------------------------
def get_recent_form(team_id: int, league_id: int, season: int, side="overall", ref_date=None):
    """
    Calcule la forme offensive/défensive réelle :
      - sur la même compétition et saison
      - selon la position (home/away)
      - avant la date de référence (si donnée)
    Retourne :
      {wins, draws, losses, goals_for, goals_against, n, xg_for, xg_against}
    """
    try:
        params = {"team": team_id, "league": league_id, "season": season, "last": 10}
        data = _api_get("/fixtures", params)
        _sleep()

        if not data:
            return {"wins":0,"draws":0,"losses":0,"goals_for":0,"goals_against":0,"n":0,"xg_for":1.2,"xg_against":1.1}

        w = d = l = gf = ga = 0
        xg_for_total = xg_against_total = 0.0
        match_count = 0

        # référence temporelle : ne pas compter les matchs futurs
        ref_dt = None
        if ref_date:
            try:
                ref_dt = datetime.fromisoformat(str(ref_date).replace("Z", "+00:00"))
            except Exception:
                pass

        for f in data:
            fix = f.get("fixture", {})
            status = fix.get("status", {}).get("short", "")
            if status not in ("FT", "AET"):
                continue  # uniquement matchs terminés

            # filtre sur la date
            if ref_dt:
                try:
                    f_date = datetime.fromisoformat(fix["date"].replace("Z", "+00:00"))
                    if f_date > ref_dt:
                        continue
                except Exception:
                    pass

            is_home = f["teams"]["home"]["id"] == team_id
            g_home, g_away = f["goals"]["home"], f["goals"]["away"]

            # 🔹 filtre sur la position
            if side == "home" and not is_home:
                continue
            if side == "away" and is_home:
                continue

            if is_home:
                gf += g_home
                ga += g_away
                win = f["teams"]["home"]["winner"]
                lose = f["teams"]["away"]["winner"]
            else:
                gf += g_away
                ga += g_home
                win = f["teams"]["away"]["winner"]
                lose = f["teams"]["home"]["winner"]

            if win:
                w += 1
            elif lose:
                l += 1
            else:
                d += 1

            # 🔹 récupération xG si dispo (API-Football "statistics" ou "xG")
            stats = f.get("statistics", [])
            if stats:
                for s in stats:
                    if s["team"]["id"] == team_id:
                        xg_for_total += s.get("xG", 0.0)
                    else:
                        xg_against_total += s.get("xG", 0.0)

            match_count += 1

        if match_count == 0:
            return {"wins":0,"draws":0,"losses":0,"goals_for":0,"goals_against":0,"n":0,"xg_for":1.2,"xg_against":1.1}

        # Moyennes par match
        gf_avg = gf / match_count
        ga_avg = ga / match_count
        xg_for_avg = (xg_for_total / match_count) if xg_for_total else gf_avg
        xg_against_avg = (xg_against_total / match_count) if xg_against_total else ga_avg

        return {
            "wins": w,
            "draws": d,
            "losses": l,
            "goals_for": round(gf_avg, 2),
            "goals_against": round(ga_avg, 2),
            "n": match_count,
            "xg_for": round(xg_for_avg, 2),
            "xg_against": round(xg_against_avg, 2)
        }

    except Exception as e:
        print(f"[⚠️ get_recent_form error {team_id}] {e}")
        return {
            "wins":0,"draws":0,"losses":0,
            "goals_for":0,"goals_against":0,
            "n":0,"xg_for":1.2,"xg_against":1.1
        }


# ----------------------------------------------------
# 4) BLESSÉS INFLUENTS
# ----------------------------------------------------
def add_injuries_influents(fx: dict):
    """
    Ajoute fx["injuries"][team_id] = [noms...]
    (simple: liste, tu peux pondérer côté main.py)
    """
    if not USE_INJURIES:
        return fx

    try:
        for team_id in (fx["home_id"], fx["away_id"]):
            params = {"team": team_id, "league": fx["league_id"], "season": fx["season"]}
            data = _api_get("/injuries", params)
            _sleep()
            fx.setdefault("injuries", {})
            fx["injuries"][team_id] = []
            for row in data:
                nm = row.get("player", {}).get("name")
                if nm:
                    fx["injuries"][team_id].append(nm)
    except Exception:
        pass
    return fx

# ----------------------------------------------------
# 5) xG / xGA via API-Football (réel ou proxy)
# ----------------------------------------------------
def get_team_expected(team_id: int, league_id: int, season: int):
    """
    Récupère expected goals (for/against) via /teams/statistics.
    Si le bloc 'expected.goals' est vide (ex: débuts de saison ou data manquante),
    calcule un proxy basé sur tirs cadrés + buts récents.
    Retour :
        {"xg_for": float, "xga": float}
    """
    try:
        # --- 1️⃣ Tentative API-Football réelle
        params = {"team": team_id, "league": league_id, "season": season}
        data = _api_get("/teams/statistics", params)
        _sleep()

        if isinstance(data, list):
            data = data[0] if data else {}
        expected = data.get("expected", {}).get("goals", {}) if data else {}

        if expected:
            xg_for = expected.get("for", {}).get("total")
            xga = expected.get("against", {}).get("total")

            if xg_for is not None and xga is not None:
                val = {"xg_for": _safe_float(xg_for), "xga": _safe_float(xga)}
                print(f"[✅ xG API] team={team_id} league={league_id} xG={val}")
                return val

        # --- 2️⃣ Fallback : calcule un xG proxy crédible
        s = get_shots_on_target_avgs(team_id, league_id, season, last=5)
        f = get_recent_form(team_id, league_id, season)

        sog_for, sog_against = s["for"], s["against"]
        goals_for = f["goals_for"] / max(f["n"], 1)
        goals_against = f["goals_against"] / max(f["n"], 1)

        # Formule pondérée (tirs cadrés + buts)
        xg_for = round(0.35 * sog_for + 0.65 * goals_for, 2)
        xga = round(0.35 * sog_against + 0.65 * goals_against, 2)

        if xg_for == 0:
            xg_for = 1.2
        if xga == 0:
            xga = 1.1

        val = {"xg_for": xg_for, "xga": xga}
        print(f"[ℹ️ xG proxy] team={team_id} league={league_id} xG={val}")

                # --- Incrément compteur API si disponible ---
        try:
            globals()["STATS"]["n_api"] += 1
        except Exception:
            pass


        return val

    except Exception as e:
        print(f"[⚠️ get_team_expected error {team_id}] {e}")
        return {"xg_for": 1.25, "xga": 1.15}


# ----------------------------------------------------
# 5B) xG via Understat API JSON (Top 5 ligues)
# ----------------------------------------------------
import json, unicodedata

UNDERSTAT_LEAGUE_SLUGS = {
    "Premier League": "epl",
    "La Liga": "laliga",
    "Bundesliga": "bundesliga",
    "Serie A": "serie_a",
    "Ligue 1": "ligue_1",
}

UNDERSTAT_TEAM_MAP = {
    # 🇬🇧 Premier League
    "Arsenal": "Arsenal",
    "Aston Villa": "Aston_Villa",
    "Bournemouth": "Bournemouth",
    "Brentford": "Brentford",
    "Brighton": "Brighton",
    "Burnley": "Burnley",
    "Chelsea": "Chelsea",
    "Crystal Palace": "Crystal_Palace",
    "Everton": "Everton",
    "Fulham": "Fulham",
    "Liverpool": "Liverpool",
    "Luton": "Luton_Town",
    "Luton Town": "Luton_Town",
    "Man City": "Manchester_City",
    "Manchester City": "Manchester_City",
    "Man United": "Manchester_United",
    "Manchester Utd": "Manchester_United",
    "Manchester United": "Manchester_United",
    "Newcastle": "Newcastle_United",
    "Newcastle Utd": "Newcastle_United",
    "Nottingham Forest": "Nottingham_Forest",
    "Nottm Forest": "Nottingham_Forest",
    "Sheffield United": "Sheffield_United",
    "Sheffield Utd": "Sheffield_United",
    "Tottenham": "Tottenham",
    "Spurs": "Tottenham",
    "West Ham": "West_Ham",
    "West Ham Utd": "West_Ham",
    "Wolves": "Wolverhampton",
    "Wolverhampton": "Wolverhampton",

    # 🇫🇷 Ligue 1
    "Angers": "Angers",
    "Auxerre": "Auxerre",
    "Brest": "Brest",
    "Clermont": "Clermont",
    "Clermont Foot": "Clermont",
    "Havre AC": "Le_Havre",
    "Le Havre": "Le_Havre",
    "Lens": "Lens",
    "Lille": "Lille",
    "Lorient": "Lorient",
    "Lyon": "Lyon",
    "Marseille": "Marseille",
    "OM": "Marseille",
    "Metz": "Metz",
    "Monaco": "Monaco",
    "Montpellier": "Montpellier",
    "Nantes": "Nantes",
    "Nice": "Nice",
    "OGC Nice": "Nice",
    "Paris SG": "Paris_Saint_Germain",
    "PSG": "Paris_Saint_Germain",
    "Paris Saint Germain": "Paris_Saint_Germain",
    "Reims": "Reims",
    "Rennes": "Rennes",
    "Strasbourg": "Strasbourg",
    "Toulouse": "Toulouse",
    "Saint Etienne": "Saint_Etienne",
    "St Etienne": "Saint_Etienne",

    # 🇮🇹 Serie A
    "AC Milan": "Milan",
    "Milan": "Milan",
    "Atalanta": "Atalanta",
    "Bologna": "Bologna",
    "Cagliari": "Cagliari",
    "Empoli": "Empoli",
    "Fiorentina": "Fiorentina",
    "Frosinone": "Frosinone",
    "Genoa": "Genoa",
    "Genoa CFC": "Genoa",
    "Inter": "Inter",
    "Inter Milano": "Inter",
    "Juventus": "Juventus",
    "Lazio": "Lazio",
    "Lazio Roma": "Lazio",
    "Lecce": "Lecce",
    "Monza": "Monza",
    "Napoli": "Napoli",
    "AS Roma": "Roma",
    "Roma": "Roma",
    "Salernitana": "Salernitana",
    "Sassuolo": "Sassuolo",
    "Spezia": "Spezia",
    "Torino": "Torino",
    "Torino FC": "Torino",
    "Udinese": "Udinese",
    "Verona": "Verona",
    "Hellas Verona": "Verona",

    # 🇩🇪 Bundesliga
    "Augsburg": "Augsburg",
    "Bayer Leverkusen": "Bayer_Leverkusen",
    "Bayern Munich": "Bayern_Munich",
    "Bayern München": "Bayern_Munich",
    "Bochum": "Bochum",
    "Borussia Dortmund": "Dortmund",
    "Dortmund": "Dortmund",
    "Borussia Mönchengladbach": "Borussia_Monchengladbach",
    "Mönchengladbach": "Borussia_Monchengladbach",
    "Cologne": "Koln",
    "FC Cologne": "Koln",
    "Eintracht Frankfurt": "Eintracht_Frankfurt",
    "Francfort": "Eintracht_Frankfurt",
    "Freiburg": "Freiburg",
    "Fribourg": "Freiburg",
    "Hamburg": "Hamburger_SV",
    "Heidenheim": "Heidenheim",
    "Hoffenheim": "Hoffenheim",
    "Leipzig": "RB_Leipzig",
    "RB Leipzig": "RB_Leipzig",
    "Leverkusen": "Bayer_Leverkusen",
    "Mainz": "Mainz",
    "Mayence": "Mainz",
    "St. Pauli": "St_Pauli",
    "St Pauli": "St_Pauli",
    "Stuttgart": "Stuttgart",
    "Union Berlin": "Union_Berlin",
    "Werder Bremen": "Werder_Bremen",
    "Wolfsburg": "Wolfsburg",

    # 🇪🇸 La Liga
    "Alaves": "Alaves",
    "Almeria": "Almeria",
    "Athletic Club": "Athletic_Club",
    "Athletic Bilbao": "Athletic_Club",
    "Atletico Madrid": "Atletico_Madrid",
    "Atl. Madrid": "Atletico_Madrid",
    "Barcelona": "Barcelona",
    "Cadiz": "Cadiz",
    "Celta Vigo": "Celta_Vigo",
    "Celta": "Celta_Vigo",
    "Espanyol": "Espanyol",
    "Getafe": "Getafe",
    "Girona": "Girona",
    "Granada": "Granada",
    "Las Palmas": "Las_Palmas",
    "Mallorca": "Mallorca",
    "Osasuna": "Osasuna",
    "Rayo Vallecano": "Rayo_Vallecano",
    "Real Betis": "Real_Betis",
    "Betis": "Real_Betis",
    "Real Madrid": "Real_Madrid",
    "Real Sociedad": "Real_Sociedad",
    "Sociedad": "Real_Sociedad",
    "Sevilla": "Sevilla",
    "Sevilla FC": "Sevilla",
    "Valencia": "Valencia",
    "Villarreal": "Villarreal",
}



def normalize_name(name: str):
    """Nettoie et supprime les accents pour comparaison."""
    name = UNDERSTAT_TEAM_MAP.get(name, name)
    name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("utf-8")
    return name.strip().lower()

# ----------------------------------------------------
# ✅ Understat v2 — Parser Hybride (NUXT → JS → Fallback)
# ----------------------------------------------------
import re, json, unicodedata, html as _html
import requests

def get_understat_xg_v2(team_name: str, league_name: str, season: int = 2025, fallback_func=None):
    import json, requests, unicodedata

    def _safe_return(src="default", xf=1.25, xa=1.15):
        return {"xg_for": xf, "xg_against": xa, "n": 1, "source": src}

    UNDERSTAT_TEAM_MAP = {
    # 🇬🇧 Premier League
    "Arsenal": "Arsenal",
    "Aston Villa": "Aston_Villa",
    "Bournemouth": "Bournemouth",
    "Brentford": "Brentford",
    "Brighton": "Brighton",
    "Burnley": "Burnley",
    "Chelsea": "Chelsea",
    "Crystal Palace": "Crystal_Palace",
    "Everton": "Everton",
    "Fulham": "Fulham",
    "Liverpool": "Liverpool",
    "Luton": "Luton_Town",
    "Luton Town": "Luton_Town",
    "Man City": "Manchester_City",
    "Manchester City": "Manchester_City",
    "Man United": "Manchester_United",
    "Manchester Utd": "Manchester_United",
    "Manchester United": "Manchester_United",
    "Newcastle": "Newcastle_United",
    "Newcastle Utd": "Newcastle_United",
    "Nottingham Forest": "Nottingham_Forest",
    "Nottm Forest": "Nottingham_Forest",
    "Sheffield United": "Sheffield_United",
    "Sheffield Utd": "Sheffield_United",
    "Tottenham": "Tottenham",
    "Spurs": "Tottenham",
    "West Ham": "West_Ham",
    "West Ham Utd": "West_Ham",
    "Wolves": "Wolverhampton",
    "Wolverhampton": "Wolverhampton",

    # 🇫🇷 Ligue 1
    "Angers": "Angers",
    "Auxerre": "Auxerre",
    "Brest": "Brest",
    "Clermont": "Clermont",
    "Clermont Foot": "Clermont",
    "Havre AC": "Le_Havre",
    "Le Havre": "Le_Havre",
    "Lens": "Lens",
    "Lille": "Lille",
    "Lorient": "Lorient",
    "Lyon": "Lyon",
    "Marseille": "Marseille",
    "OM": "Marseille",
    "Metz": "Metz",
    "Monaco": "Monaco",
    "Montpellier": "Montpellier",
    "Nantes": "Nantes",
    "Nice": "Nice",
    "OGC Nice": "Nice",
    "Paris SG": "Paris_Saint_Germain",
    "PSG": "Paris_Saint_Germain",
    "Paris Saint Germain": "Paris_Saint_Germain",
    "Reims": "Reims",
    "Rennes": "Rennes",
    "Strasbourg": "Strasbourg",
    "Toulouse": "Toulouse",
    "Saint Etienne": "Saint_Etienne",
    "St Etienne": "Saint_Etienne",

    # 🇮🇹 Serie A
    "AC Milan": "Milan",
    "Milan": "Milan",
    "Atalanta": "Atalanta",
    "Bologna": "Bologna",
    "Cagliari": "Cagliari",
    "Empoli": "Empoli",
    "Fiorentina": "Fiorentina",
    "Frosinone": "Frosinone",
    "Genoa": "Genoa",
    "Genoa CFC": "Genoa",
    "Inter": "Inter",
    "Inter Milano": "Inter",
    "Juventus": "Juventus",
    "Lazio": "Lazio",
    "Lazio Roma": "Lazio",
    "Lecce": "Lecce",
    "Monza": "Monza",
    "Napoli": "Napoli",
    "AS Roma": "Roma",
    "Roma": "Roma",
    "Salernitana": "Salernitana",
    "Sassuolo": "Sassuolo",
    "Spezia": "Spezia",
    "Torino": "Torino",
    "Torino FC": "Torino",
    "Udinese": "Udinese",
    "Verona": "Verona",
    "Hellas Verona": "Verona",

    # 🇩🇪 Bundesliga
    "Augsburg": "Augsburg",
    "Bayer Leverkusen": "Bayer_Leverkusen",
    "Bayern Munich": "Bayern_Munich",
    "Bayern München": "Bayern_Munich",
    "Bochum": "Bochum",
    "Borussia Dortmund": "Dortmund",
    "Dortmund": "Dortmund",
    "Borussia Mönchengladbach": "Borussia_Monchengladbach",
    "Mönchengladbach": "Borussia_Monchengladbach",
    "Cologne": "Koln",
    "FC Cologne": "Koln",
    "Eintracht Frankfurt": "Eintracht_Frankfurt",
    "Francfort": "Eintracht_Frankfurt",
    "Freiburg": "Freiburg",
    "Fribourg": "Freiburg",
    "Hamburg": "Hamburger_SV",
    "Heidenheim": "Heidenheim",
    "Hoffenheim": "Hoffenheim",
    "Leipzig": "RB_Leipzig",
    "RB Leipzig": "RB_Leipzig",
    "Leverkusen": "Bayer_Leverkusen",
    "Mainz": "Mainz",
    "Mayence": "Mainz",
    "St. Pauli": "St_Pauli",
    "St Pauli": "St_Pauli",
    "Stuttgart": "Stuttgart",
    "Union Berlin": "Union_Berlin",
    "Werder Bremen": "Werder_Bremen",
    "Wolfsburg": "Wolfsburg",

    # 🇪🇸 La Liga
    "Alaves": "Alaves",
    "Almeria": "Almeria",
    "Athletic Club": "Athletic_Club",
    "Athletic Bilbao": "Athletic_Club",
    "Atletico Madrid": "Atletico_Madrid",
    "Atl. Madrid": "Atletico_Madrid",
    "Barcelona": "Barcelona",
    "Cadiz": "Cadiz",
    "Celta Vigo": "Celta_Vigo",
    "Celta": "Celta_Vigo",
    "Espanyol": "Espanyol",
    "Getafe": "Getafe",
    "Girona": "Girona",
    "Granada": "Granada",
    "Las Palmas": "Las_Palmas",
    "Mallorca": "Mallorca",
    "Osasuna": "Osasuna",
    "Rayo Vallecano": "Rayo_Vallecano",
    "Real Betis": "Real_Betis",
    "Betis": "Real_Betis",
    "Real Madrid": "Real_Madrid",
    "Real Sociedad": "Real_Sociedad",
    "Sociedad": "Real_Sociedad",
    "Sevilla": "Sevilla",
    "Sevilla FC": "Sevilla",
    "Valencia": "Valencia",
    "Villarreal": "Villarreal",
}

    team_slug = UNDERSTAT_TEAM_MAP.get(team_name, team_name.replace(" ", "_"))
    url = f"https://understat.com/api/team/{team_slug}/{season}"

    try:
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        r.raise_for_status()
        data = r.json()

        matches = data.get("matches", [])
        if not matches:
            raise ValueError("No matches")

        # Moyenne des 5 derniers matchs
        recent = matches[-5:]
        xgf = xga = 0.0
        for m in recent:
            if m.get("h_title") == team_name or team_slug in m.get("h_title", "").replace(" ", "_"):
                xgf += float(m["xG"]["h"])
                xga += float(m["xG"]["a"])
            else:
                xgf += float(m["xG"]["a"])
                xga += float(m["xG"]["h"])

        n = len(recent)
        return {
            "xg_for": round(xgf / n, 2),
            "xg_against": round(xga / n, 2),
            "n": n,
            "source": "UnderstatAPI"
        }

    except Exception as e:
        print(f"[⚠️] Understat API fallback {team_name}: {e}")
        fb = fallback_func(team_name) if fallback_func else None
        if isinstance(fb, dict):
            return {
                "xg_for": fb.get("xg_for", 1.25),
                "xg_against": fb.get("xg_against", fb.get("xga", 1.15)),
                "n": fb.get("n", 1),
                "source": fb.get("source", "fallback"),
            }
        return _safe_return("error")



# ----------------------------------------------------
# 6) H2H — BTTS %, Moy. Buts, Score pondéré
# ----------------------------------------------------
H2H_CACHE = {}  # 🧠 cache mémoire H2H

def get_btts_h2h(home_id: int, away_id: int, last: int = 10):
    """
    Calcule les statistiques H2H sur les 'last' dernières confrontations :
      - % BTTS (les deux équipes marquent)
      - Moyennes de buts marqués et encaissés
      - Score H2H pondéré (BTTS %, buts pour/contre)
    Utilise un cache mémoire pour éviter les appels répétés.
    """
    key = (home_id, away_id, last)
    if key in H2H_CACHE:
        return H2H_CACHE[key]  # ⚡ cache hit, aucun appel API

    try:
        params = {"h2h": f"{home_id}-{away_id}", "last": last}
        data = _api_get("/fixtures/headtohead", params)
        _sleep()

        if not data:
            result = {
                "n": 0,
                "btts_pct": 0.0,
                "gf_home": 0.0,
                "ga_home": 0.0,
                "gf_away": 0.0,
                "ga_away": 0.0,
                "score_h2h": 0.0
            }
            H2H_CACHE[key] = result
            return result

        both = 0
        gf_home = ga_home = gf_away = ga_away = 0.0

        for f in data:
            gh = f["goals"]["home"]
            ga = f["goals"]["away"]
            home_team = f["teams"]["home"]["id"]
            away_team = f["teams"]["away"]["id"]

            if gh > 0 and ga > 0:
                both += 1

            if home_team == home_id:
                gf_home += gh
                ga_home += ga
            else:
                gf_away += ga
                ga_away += gh

        n_h2h = len(data)
        btts_pct = round(100.0 * both / n_h2h, 1) if n_h2h else 0.0
        gf_home = gf_home / n_h2h if n_h2h else 0.0
        ga_home = ga_home / n_h2h if n_h2h else 0.0
        gf_away = gf_away / n_h2h if n_h2h else 0.0
        ga_away = ga_away / n_h2h if n_h2h else 0.0

        if n_h2h >= 3:
            score_h2h = (btts_pct / 100.0) * 0.6 + (gf_home + gf_away) * 0.2 + (ga_home + ga_away) * 0.2
        else:
            score_h2h = (gf_home + gf_away + ga_home + ga_away) / 4.0 if n_h2h else 0.0

        result = {
            "n": n_h2h,
            "btts_pct": btts_pct,
            "gf_home": round(gf_home, 2),
            "ga_home": round(ga_home, 2),
            "gf_away": round(gf_away, 2),
            "ga_away": round(ga_away, 2),
            "score_h2h": round(score_h2h, 2)
        }
        H2H_CACHE[key] = result
        return result

    except Exception:
        result = {
            "n": 0,
            "btts_pct": 0.0,
            "gf_home": 0.0,
            "ga_home": 0.0,
            "gf_away": 0.0,
            "ga_away": 0.0,
            "score_h2h": 0.0
        }
        H2H_CACHE[key] = result
        return result



# ----------------------------------------------------
# 7) STANDINGS — force tableau simplifiée
# ----------------------------------------------------
def get_table_strength(league_id: int, season: int, team_id: int):
    """
    Force simple: points_equipe / points_max (du leader).
    """
    try:
        params = {"league": league_id, "season": season}
        data = _api_get("/standings", params)
        _sleep()
        if not data:
            return 0.5
        # structure: response[0]["league"]["standings"][0] = liste
        league = data[0]["league"]
        table = league["standings"][0]
        pts_leader = max(row["points"] for row in table) or 1
        my_pts = 0
        for row in table:
            if row["team"]["id"] == team_id:
                my_pts = row["points"]
                break
        return max(0.0, min(1.0, my_pts / pts_leader))
    except Exception:
        return 0.5

# ----------------------------------------------------
# 8) SOT — tirs cadrés moyens dernier N (option léger)
# ----------------------------------------------------
def get_shots_on_target_avgs(team_id: int, league_id: int, season: int, last: int = 5):
    """
    Approche légère: moyenne 'shots on target' pour et contre sur N derniers matchs.
    (Utilise /fixtures/statistics par match — peut être plus lent si N grand)
    """
    try:
        # 1) Récupère les derniers matchs IDs
        params = {"team": team_id, "league": league_id, "season": season, "last": last}
        fixtures = _api_get("/fixtures", params)
        _sleep()
        if not fixtures:
            return {"for": 0.0, "against": 0.0, "n": 0}

        total_for = total_against = 0.0
        n = 0
        for f in fixtures:
            fid = f["fixture"]["id"]
            st = _api_get("/fixtures/statistics", {"fixture": fid})
            _sleep()
            if not st:
                continue
            # st = [ { "team": {...}, "statistics": [ {"type":"Shots on Goal","value":X}, ... ] }, {...} ]
            if len(st) != 2:
                continue
            # équipe A
            a = st[0]; b = st[1]
            if a["team"]["id"] == team_id:
                me, opp = a, b
            else:
                me, opp = b, a
            def _sog(block):
                for it in block.get("statistics", []):
                    if it.get("type") == "Shots on Goal":
                        return _safe_float(it.get("value"), 0)
                return 0.0
            total_for += _sog(me)
            total_against += _sog(opp)
            n += 1
        if n == 0:
            return {"for": 0.0, "against": 0.0, "n": 0}
        return {"for": round(total_for / n, 2), "against": round(total_against / n, 2), "n": n}
    except Exception:
        return {"for": 0.0, "against": 0.0, "n": 0}

# ----------------------------------------------------
# 9) Jours de repos (congestion)
# ----------------------------------------------------
def get_days_since_last_match(team_id: int, league_id: int, season: int):
    """
    Renvoie le nombre de jours depuis le dernier match de l'équipe
    (dans la même compétition).
    """
    try:
        params = {"team": team_id, "league": league_id, "season": season, "last": 1}
        data = _api_get("/fixtures", params)
        _sleep()
        if not data:
            return None
        dt = data[0]["fixture"]["date"]
        last_dt = datetime.fromisoformat(dt.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        return (now - last_dt).days
    except Exception:
        return None

# ----------------------------------------------------
# 10) Voyage / fuseau (simple placeholder)
# ----------------------------------------------------
def get_travel_penalty(home_country: str, away_country: str):
    """
    Malus simple si pays différents (intercontinental).
    """
    try:
        if not home_country or not away_country:
            return 0.0
        if home_country == away_country:
            return 0.0
        # pénalité légère si continents différents
        # (à spécialiser si tu as une table de continents)
        return -0.03
    except Exception:
        return 0.0

# ----------------------------------------------------
# 11) Arbitre — contexte simple (placeholder propre)
# ----------------------------------------------------
def get_referee_context(fixture_referee: str):
    """
    L'API-Football ne fournit pas de stats d'arbitre exhaustives (penalties/cartons)
    via un endpoint public standard. On retourne un placeholder exploitable.
    """
    if not fixture_referee:
        return {"name": None, "pen_rate": None, "card_rate": None}
    return {"name": fixture_referee, "pen_rate": None, "card_rate": None}

# ----------------------------------------------------
# 12) Probabilités implicites (1X2 / Over / BTTS)
# ----------------------------------------------------
def implied_probs_1x2(fx: dict):
    """
    Transforme les cotes 1X2 en probabilités renormalisées (0..1).
    """
    try:
        oh = _safe_float(fx.get("odds_home"), 0.0)
        od = _safe_float(fx.get("odds_draw"), 0.0)
        oa = _safe_float(fx.get("odds_away"), 0.0)
        inv = [1/x for x in (oh, od, oa) if x and x > 0]
        s = sum(inv)
        if s == 0:
            return (1/3, 1/3, 1/3)
        p = [x/s for x in inv]
        # réordonne (home, draw, away)
        return (p[0] if len(p) > 0 else 1/3,
                p[1] if len(p) > 1 else 1/3,
                p[2] if len(p) > 2 else 1/3)
    except Exception:
        return (1/3, 1/3, 1/3)

def implied_prob_from_over(odd_over):
    try:
        o = _safe_float(odd_over, 0.0)
        return round(1/o, 3) if o > 1 else 0.5
    except Exception:
        return 0.5

def implied_prob_from_btts(odd_yes):
    try:
        o = _safe_float(odd_yes, 0.0)
        return round(1/o, 3) if o > 1 else 0.5
    except Exception:
        return 0.5

