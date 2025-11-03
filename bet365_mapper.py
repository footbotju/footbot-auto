# ============================================
# bet365_mapper_v4.py — Bet365 PREMATCH only
#   - Source unique: GET /odds?sportId=10&verbosity=3
#   - Exclut live/inplay ET terminés → PREMATCH uniquement
#   - Matching robuste: noms normalisés + heure (±120 min) pour la même date
#   - Injecte: odds_home, odds_draw, odds_away, odds_over_1_5, odds_btts_yes
# ============================================

import os, re, json, time, unicodedata
from datetime import datetime, timezone, timedelta
import requests
from dotenv import load_dotenv

# ---------- ENV ----------
BASE_DIR = os.path.dirname(__file__)
load_dotenv(dotenv_path=os.path.join(BASE_DIR, ".env"))

API_HOST = os.getenv("BET365_API_HOST", "bet36528.p.rapidapi.com")
API_KEY  = os.getenv("BET365_API_KEY", "")
BASE_URL = f"https://{API_HOST}"

HEADERS = {
    "x-rapidapi-key": API_KEY,
    "x-rapidapi-host": API_HOST,
    "accept": "application/json",
}

SPORT_ID_SOCCER = "10"  # confirmé sur ton plan

# ---------- CACHES ----------
CACHE_RAW_ODDS = os.path.join(BASE_DIR, "cache_bet365_odds_raw.json")   # dataset brut /odds
CACHE_IDX_DAY  = os.path.join(BASE_DIR, "cache_bet365_index_by_day.json")  # index par date

_RAW_MEM = None          # dataset brut en mémoire
_INDEX_BY_DAY_MEM = {}   # date -> index {(home,away): [items]}


# ---------- UTILS ----------
def _load_json(path, default):
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return default

def _save_json(path, data):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=str)
    except Exception:
        pass

def _norm(s: str) -> str:
    if not s:
        return ""
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = s.lower()
    s = re.sub(r"[\.\-_/]", " ", s)
    # nettoyages fréquents
    s = re.sub(r"\b(fc|cf|sc|ac|afc|cfc|ud|cd|bk|u\d+|deportivo|sporting|athletic|club)\b", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s

def _to_utc(v):
    if v is None:
        return None
    if isinstance(v, (int, float)):
        try:
            return datetime.fromtimestamp(float(v), tz=timezone.utc)
        except Exception:
            return None
    if isinstance(v, str):
        try:
            return datetime.fromisoformat(v.replace("Z", "+00:00")).astimezone(timezone.utc)
        except Exception:
            return None
    return None

def _minutes_diff(a, b):
    if not a or not b:
        return 9e9
    return abs((a - b).total_seconds()) / 60.0

def _date_str_from_iso(dt_iso: str) -> str:
    return (dt_iso or "").split("T")[0] if dt_iso else ""


# ---------- APPEL /odds (PREMATCH seulement) ----------
def _get(url, params, timeout=20):
    try:
        r = requests.get(url, headers=HEADERS, params=params, timeout=timeout)
        if r.status_code == 429:
            time.sleep(1.2)
            r = requests.get(url, headers=HEADERS, params=params, timeout=timeout)
        if r.ok:
            try:
                return r.status_code, r.json()
            except Exception:
                return r.status_code, None
        return r.status_code, None
    except Exception:
        return 0, None

def _is_prematch_like(item: dict) -> bool:
    """
    Garde uniquement le pré-match (ni live/inplay, ni terminé).
    Tolérant aux structures/flags variables de l’API.
    """
    status = (item.get("status") or item.get("phase") or "").lower()
    status_id = str(item.get("statusId") or "").lower()

    # Exclusions explicites
    blacklist_tokens = ("live", "inplay", "in-play", "running", "playing", "ended", "finished", "complete")
    if any(t in status for t in blacklist_tokens):
        return False
    if status_id in {"2", "3", "4"}:  # valeurs fréquentes pour live/terminé sur certaines variantes
        return False

    # Inclusions connues
    if status in {"pre", "prematch", "scheduled"}:
        return True

    # Heuristique sur l'heure: si on a un horaire à venir (ou tout juste passé), on considère pré-match
    dt = _to_utc(item.get("startTime") or item.get("trueStartTime"))
    if not dt:
        # Pas d’info → on ne bloque pas
        return True

    now_utc = datetime.now(timezone.utc)
    # Pré-match si le coup d'envoi est dans le futur ou a eu lieu il y a < 15 min
    return dt >= (now_utc - timedelta(minutes=15))


def load_all_bet365_odds_prematch(force_refresh=False):
    """
    Charge 1 fois les cotes Bet365 (PREMATCH uniquement) via /odds?sportId=10&verbosity=3
    - Retourne une liste de dicts {fixtureId, homeName, awayName, startTime, markets}
    - Met en cache brut pour limiter les appels
    """
    global _RAW_MEM

    if _RAW_MEM is not None and not force_refresh:
        return _RAW_MEM

    # cache disque
    if not force_refresh:
        cached = _load_json(CACHE_RAW_ODDS, None)
        if cached:
            _RAW_MEM = cached
            return _RAW_MEM

    url = f"{BASE_URL}/odds"
    params = {"sportId": SPORT_ID_SOCCER, "verbosity": "3"}
    code, data = _get(url, params=params)

    results = []
    if code == 200 and data:
        arr = data.get("results") or data
        for it in arr:
            # extraction du binaire d'équipes (multiples formats possibles)
            home = it.get("homeTeam") or it.get("participant1Name") or (it.get("teams") or {}).get("home")
            away = it.get("awayTeam") or it.get("participant2Name") or (it.get("teams") or {}).get("away")
            if not (home and away):
                continue

            # horodatage
            when = it.get("startTime") or it.get("trueStartTime") or it.get("time") or it.get("kickoff")
            dt_utc = _to_utc(when)

            # statut: on exclut live/terminés → PREMATCH seulement
            if not _is_prematch_like(it):
                continue

            fid = it.get("fixtureId") or it.get("id") or it.get("fixture_id")
            markets = it.get("markets") or it.get("odds") or []

            results.append({
                "fixture_id": str(fid) if fid else None,
                "home": str(home),
                "away": str(away),
                "dt_utc": dt_utc.isoformat() if dt_utc else None,
                "markets": markets
            })

    # garde-fou: écrire quand même en cache (même si vide) pour éviter le spam API
    _RAW_MEM = results
    _save_json(CACHE_RAW_ODDS, results)
    print(f"[Bet365 /odds PREMATCH] {len(results)} match(s) chargés depuis Bet365")
    return results


# ---------- INDEXATION PAR DATE ----------
def _build_index_by_day():
    """
    Construit un index par date: date_str -> {(norm_home, norm_away): [items]}
    """
    raw = load_all_bet365_odds_prematch()
    index = {}

    for it in raw:
        home = _norm(it["home"])
        away = _norm(it["away"])
        date_str = _date_str_from_iso(it["dt_utc"])
        if not date_str:
            continue
        index.setdefault(date_str, {})
        index[date_str].setdefault((home, away), []).append(it)

    _INDEX_BY_DAY_MEM.clear()
    _INDEX_BY_DAY_MEM.update(index)
    # cache disque
    _save_json(CACHE_IDX_DAY, index)
    return index

def _get_index_for_day(date_str: str):
    if date_str in _INDEX_BY_DAY_MEM:
        return _INDEX_BY_DAY_MEM[date_str]
    disk = _load_json(CACHE_IDX_DAY, {})
    if date_str in disk:
        _INDEX_BY_DAY_MEM[date_str] = disk[date_str]
        return disk[date_str]
    # (re)construction complète si manquant
    _build_index_by_day()
    return _INDEX_BY_DAY_MEM.get(date_str, {})


# ---------- EXTRACTION DES COTES D'UN ITEM ----------
def _to_float(x):
    try:
        return float(x)
    except Exception:
        return None

def _extract_common_odds(markets):
    """
    Normalise les marchés principaux: 1X2, Over 1.5, BTTS Yes.
    """
    out = {}
    for m in markets or []:
        name = (m.get("name") or "").lower()
        values = m.get("odds") or m.get("values") or []

        # 1X2
        if "match winner" in name or "full time result" in name or "1x2" in name:
            for v in values:
                val = (v.get("name") or v.get("value") or "").lower()
                odd = _to_float(v.get("odds") or v.get("odd"))
                if not odd:
                    continue
                if "home" in val:
                    out["odds_home"] = round(odd, 2)
                elif "draw" in val:
                    out["odds_draw"] = round(odd, 2)
                elif "away" in val:
                    out["odds_away"] = round(odd, 2)

        # Over 1.5 (on repère explicitement 1.5)
        if ("over 1.5" in name) or ("over/under" in name and "1.5" in name):
            if values:
                odd = _to_float(values[0].get("odds") or values[0].get("odd"))
                if odd:
                    out["odds_over_1_5"] = round(odd, 2)

        # BTTS Yes
        if "both teams to score" in name:
            for v in values:
                val = (v.get("name") or v.get("value") or "").lower()
                if val == "yes":
                    odd = _to_float(v.get("odds") or v.get("odd"))
                    if odd:
                        out["odds_btts_yes"] = round(odd, 2)

    return out


# ---------- API PUBLIQUE → À UTILISER DANS FootBot ----------
def inject_bet365_odds_for_fixture(fx: dict) -> dict:
    """
    Injection PREMATCH Bet365 pour un fixture API-Football (modifie fx en place si trouvé).
    - date_utc de fx sert de clé de jour
    - matching (home, away, heure) avec tolérance ± 120 minutes
    - si marché(s) trouvé(s) → injection dans fx
    """
    try:
        date_str = _date_str_from_iso(fx.get("date_utc"))
        if not date_str:
            return fx

        idx = _get_index_for_day(date_str)
        if not idx:
            # (re)construit si non disponible
            _build_index_by_day()
            idx = _get_index_for_day(date_str)

        home = _norm(fx.get("home_team"))
        away = _norm(fx.get("away_team"))
        dt_api = _to_utc(fx.get("date_utc"))

        # candidats mêmes noms, sinon inversé
        candidates = idx.get((home, away), []) or idx.get((away, home), [])
        if not candidates:
            print(f"[Bet365 MAP] Aucun PREMATCH pour {fx.get('home_team')} vs {fx.get('away_team')} ({date_str})")
            return fx

        # meilleur match horaire
        best, best_diff = None, 9e9
        for it in candidates:
            dt_b = _to_utc(it.get("dt_utc"))
            diff = _minutes_diff(dt_api, dt_b)
            if diff < best_diff:
                best, best_diff = it, diff

        if not best or best_diff > 120:  # tolérance ± 2h
            print(f"[Bet365 MAP] Candidat écart horaire >120 min pour {fx.get('home_team')} vs {fx.get('away_team')}")
            return fx

        odds = _extract_common_odds(best.get("markets") or [])
        if odds:
            fx.update(odds)
            print(f"[Bet365 OK] {fx.get('home_team')} vs {fx.get('away_team')} → {odds}")
        else:
            print(f"[Bet365 ODDS] Marchés insuffisants pour {fx.get('home_team')} vs {fx.get('away_team')}")

        return fx

    except Exception as e:
        print(f"[Bet365 inject] erreur: {e}")
        return fx
