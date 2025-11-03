# api_football_odds.py
from datetime import datetime
import os, requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from time import sleep

API_KEY = os.getenv("API_FOOTBALL_KEY")
API_BASE = "https://v3.football.api-sports.io"
HEADERS  = {"x-apisports-key": API_KEY, "Accept": "application/json"}

# --- marchés demandés
BET_FILTER = "1,2,5,8"   # 1=Match Winner, 2=Home/Away team to score, 5=Over/Under, 8=BTTS
BET365_ID  = 8           # bookmaker Bet365 (quand dispo)

# ---------- Utils ----------
def _check_key():
    if not API_KEY:
        raise RuntimeError("API_FOOTBALL_KEY manquant dans .env")

def _get(path, params, timeout=12):
    """GET avec petit backoff."""
    url = f"{API_BASE}{path if path.startswith('/') else '/' + path}"
    backoff = 0.5
    for attempt in range(3):
        try:
            r = requests.get(url, headers=HEADERS, params=params, timeout=timeout)
            r.raise_for_status()
            return r.json()
        except Exception:
            if attempt == 2:
                raise
            sleep(backoff)
            backoff *= 2

def _pick_bookmaker(bookmakers):
    """Priorise Bet365, sinon 1er bookmaker dispo."""
    if not bookmakers:
        return None
    for b in bookmakers:
        try:
            if int(b.get("id", 0)) == BET365_ID:
                return b
        except Exception:
            pass
    return bookmakers[0]

def _parse_bets(bm_bets):
    """Extrait les marchés utiles depuis la structure bookmaker['bets']."""
    out = {}
    for bet in bm_bets or []:
        name = (bet.get("name") or "").strip().lower()
        vals = bet.get("values") or []

        # 1) Match Winner
        if "match winner" in name:
            for v in vals:
                val = (v.get("value") or "").strip().lower()
                odd = v.get("odd")
                try:
                    o = float(odd)
                except Exception:
                    continue
                if "home" in val:
                    out["odds_home"] = round(o, 2)
                elif "draw" in val:
                    out["odds_draw"] = round(o, 2)
                elif "away" in val:
                    out["odds_away"] = round(o, 2)

        # 2) Goals Over/Under (On retient Over 1.5)
        elif "goals over/under" in name:
            for v in vals:
                if (v.get("value") or "").strip().lower() == "over 1.5":
                    try:
                        out["odds_over_1_5"] = round(float(v.get("odd")), 2)
                    except Exception:
                        pass

        # 3) Both Teams To Score (BTTS)
        elif "both teams to score" in name:
            for v in vals:
                val = (v.get("value") or "").strip().lower()
                if val == "yes":
                    try:
                        out["odds_btts_yes"] = round(float(v.get("odd")), 2)
                    except Exception:
                        pass

        # 4) Team Score a Goal (Home/Away YES)
        elif "team score a goal" in name:
            for v in vals:
                val = (v.get("value") or "").strip().lower()
                try:
                    o = float(v.get("odd"))
                except Exception:
                    continue
                # ex. "Home - Yes" / "Away - Yes"
                if "home" in val and "yes" in val:
                    out["odds_team_home"] = round(o, 2)
                elif "away" in val and "yes" in val:
                    out["odds_team_away"] = round(o, 2)

    return out

# ---------- Fallback intelligent ----------
def _get_fixtures_ids_for_date(date_str):
    """Récupère les IDs de fixtures pour la date donnée (UTC or local décalé peu importe ici)."""
    j = _get("/fixtures", {"date": date_str})
    resp = j.get("response", []) if isinstance(j, dict) else []
    ids = []
    for it in resp:
        try:
            fid = it.get("fixture", {}).get("id")
            if fid:
                ids.append(int(fid))
        except Exception:
            pass
    return ids

def _fetch_odds_for_fixture(fid: int):
    """Récupère les cotes pour 1 fixture. Bet365 prioritaire, sinon 1er bookmaker."""
    j = _get("/odds", {"fixture": fid, "bet": BET_FILTER})
    resp = j.get("response", []) if isinstance(j, dict) else []
    if not resp:
        return fid, {}
    # structure: response[0] → {fixture:{id}, bookmakers:[{id,name,bets:[...]}]}
    item = resp[0]
    bm = _pick_bookmaker(item.get("bookmakers"))
    if not bm:
        return fid, {}
    return fid, _parse_bets(bm.get("bets"))

# ---------- API publique ----------
def fetch_odds_for_date(date_str: str):
    """
    1) Essaye /odds?date=YYYY-MM-DD&bet=1,2,5,8
    2) Si 0 → fallback:
       - récupère fixture IDs via /fixtures?date=...
       - lance /odds?fixture=<id> (en //) et parse
    Retourne: { fixture_id:int -> {odds_*:float, ...} }
    """
    _check_key()

    # --- Tentative 1: par date
    params = {"date": date_str, "bet": BET_FILTER}
    print(f"1/ Appel /odds par date → {params}")
    j = _get("/odds", params)
    if not isinstance(j, dict):
        j = {}
    total = int(j.get("results", 0) or 0)
    resp = j.get("response", []) or []
    odds_map = {}

    if total > 0 and resp:
        print(f"→ OK: {total} lignes")
        for item in resp:
            fid = item.get("fixture", {}).get("id")
            if not fid:
                continue
            bm = _pick_bookmaker(item.get("bookmakers"))
            if not bm:
                continue
            parsed = _parse_bets(bm.get("bets"))
            if parsed:
                odds_map[int(fid)] = parsed
        return odds_map

    print("→ 0 résultat. Activation du fallback intelligent (par fixture).")

    # --- Fallback: récupérer les fixtures du jour
    fids = _get_fixtures_ids_for_date(date_str)
    if not fids:
        print("⚠️ Aucun fixture id trouvé pour cette date — retour cotes vides.")
        return {}

    # --- Interroger /odds fixture par fixture en // (rapide et robuste)
    odds_map = {}
    with ThreadPoolExecutor(max_workers=12) as ex:
        futures = [ex.submit(_fetch_odds_for_fixture, fid) for fid in fids]
        for fut in as_completed(futures):
            try:
                fid, parsed = fut.result()
                if parsed:
                    odds_map[int(fid)] = parsed
            except Exception:
                pass

    print(f"→ Fallback terminé: cotes trouvées pour {len(odds_map)}/{len(fids)} fixtures")
    return odds_map


def merge_odds(fixtures, odds_map):
    """
    Injecte les cotes dans tes fixtures.
    """
    updated = 0
    for fx in fixtures:
        fid = (
            fx.get("fixture_id") or
            fx.get("id") or
            (fx.get("fixture") or {}).get("id")
        )
        if not fid:
            continue
        odds = odds_map.get(int(fid))
        if not odds:
            continue
        fx.update(odds)
        updated += 1
    print(f"✅ merge_odds : {updated}/{len(fixtures)} fixtures enrichies avec cotes")
    return fixtures
