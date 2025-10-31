# =====================================================
# understat_ext.py — module d’intégration Understat (v2025 corrigé)
# =====================================================
import os, json, time, requests
from bs4 import BeautifulSoup
from team_name_map import map_understat_name

CACHE_FILE = os.path.join(os.path.dirname(__file__), "cache_understat.json")
BASE_URL = "https://understat.com/team"

# -----------------------
# Cache local
# -----------------------
if os.path.exists(CACHE_FILE):
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            CACHE = json.load(f)
    except Exception:
        CACHE = {}
else:
    CACHE = {}

def _save_cache():
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(CACHE, f, indent=2, ensure_ascii=False)
    except Exception:
        pass

# -----------------------
# Lecture xG d’une équipe
# -----------------------
def get_team_splits(team_name, season):
    """
    Retourne un dict contenant les xG moyens Home/Away/Overall pour une équipe Understat.
    Si indisponible, renvoie un fallback neutre (pas d’erreur).
    """
    if not team_name:
        return _fallback(team_name)

    # mapping nom
    team_name = map_understat_name(team_name)
    key = f"{team_name}_{season}"

    # --- Vérifie le cache ---
    if key in CACHE:
        try:
            globals()["STATS"]["n_understat"] = globals().get("STATS", {}).get("n_understat", 0) + 1
        except Exception:
            pass
        return CACHE[key]

    # --- Requête Understat ---
    url = f"{BASE_URL}/{team_name.replace(' ', '%20')}/{season}"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        r = requests.get(url, headers=headers, timeout=10)
        time.sleep(0.2)

        if r.status_code == 404:
            print(f"[ℹ️] Understat: no data for {team_name} – using fallback.")
            data = _fallback(team_name)
            CACHE[key] = data
            _save_cache()
            try:
                globals()["STATS"]["n_understat"] = globals().get("STATS", {}).get("n_understat", 0) + 1
            except Exception:
                pass
            return data

        r.raise_for_status()

    except Exception as e:
        print(f"[⚠️] Understat error {team_name}: {e}")
        data = _fallback(team_name)
        CACHE[key] = data
        _save_cache()
        try:
            globals()["STATS"]["n_understat"] = globals().get("STATS", {}).get("n_understat", 0) + 1
        except Exception:
            pass
        return data

    # --- Extraction ---
    try:
        soup = BeautifulSoup(r.text, "html.parser")
        scripts = soup.find_all("script")
        target = [s for s in scripts if "matchesData" in s.text]
        if not target:
            raise ValueError("matchesData introuvable.")

        js = target[0].string
        js = js[js.index("matchesData") + 13 : js.index("];") + 1]
        matches = json.loads(js)
        if not matches:
            raise ValueError("Aucun match Understat.")

        home_games = [m for m in matches if m["h"]["title"] == team_name]
        away_games = [m for m in matches if m["a"]["title"] == team_name]
        all_games = matches

        def avg(v):
            return sum(v) / len(v) if v else 0

        xg_home = avg([float(m["xG"]["h"]) for m in home_games if m["xG"]["h"]])
        xga_home = avg([float(m["xG"]["a"]) for m in home_games if m["xG"]["a"]])
        xg_away = avg([float(m["xG"]["a"]) for m in away_games if m["xG"]["a"]])
        xga_away = avg([float(m["xG"]["h"]) for m in away_games if m["xG"]["h"]])
        xg_overall = avg([float(m["xG"]["h"]) + float(m["xG"]["a"]) for m in all_games]) / 2
        xga_overall = xg_overall  # symétrique en moyenne

        data = {
            "xg_home": xg_home,
            "xga_home": xga_home,
            "xg_away": xg_away,
            "xga_away": xga_away,
            "xg_overall": xg_overall,
            "xga_overall": xga_overall,
        }

        CACHE[key] = data
        _save_cache()

        try:
            globals()["STATS"]["n_understat"] = globals().get("STATS", {}).get("n_understat", 0) + 1
        except Exception:
            pass

        print(f"[✅ Understat] {team_name} ({season}) → {data}")
        return data

    except Exception as e:
        print(f"[⚠️] Understat parse error {team_name}: {e}")
        data = _fallback(team_name)
        CACHE[key] = data
        _save_cache()
        try:
            globals()["STATS"]["n_understat"] = globals().get("STATS", {}).get("n_understat", 0) + 1
        except Exception:
            pass
        return data

# -----------------------
# Fallback neutre (valeurs moyennes)
# -----------------------
def _fallback(team_name):
    return {
        "xg_home": 1.3,
        "xga_home": 1.2,
        "xg_away": 1.1,
        "xga_away": 1.3,
        "xg_overall": 1.2,
        "xga_overall": 1.2,
    }
