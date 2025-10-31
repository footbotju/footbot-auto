

# ================================
# FootBot PRO v2025.10 — main.py
# ================================
import os, sys, json, math, time
from datetime import datetime
today = datetime.now().strftime("%Y-%m-%d")

from concurrent.futures import ThreadPoolExecutor
from dotenv import load_dotenv

# --- Initialisation du chemin de base et des variables .env
BASE_DIR = os.path.dirname(__file__)
load_dotenv(dotenv_path=os.path.join(BASE_DIR, ".env"))

print(f"🧩 .env chargé depuis: {os.path.join(BASE_DIR, '.env')}")


# --- Modules internes
from leagues_list import MAJOR_LEAGUES
from api_football_ext import (
    get_fixtures_by_date,
    enrich_with_odds_and_markets,
    get_recent_form,
    add_injuries_influents,
    implied_probs_1x2,
    implied_prob_from_over,
    implied_prob_from_btts,
    get_btts_h2h,
    get_table_strength,
    get_shots_on_target_avgs,
    get_days_since_last_match,
    get_travel_penalty,
    get_referee_context,
    get_team_expected,
    get_understat_xg_v2,
)

from understat_ext import get_team_splits

from concurrent.futures import ThreadPoolExecutor, as_completed

# ======================
# OPTIMISATION FootBot PRO
# ======================
DEBUG = False  # passer à True pour revoir les prints
POOL = ThreadPoolExecutor(max_workers=20)

# --- Calibration IC (dérivée du dernier analyse_globale) ---
CALIB = {
    "btts":      {"k": 1.10},   # +10% (IC trop prudent)
    "over 1.5":  {"k": 0.86},   # -14% (IC trop optimiste)
    "résultat":  {"k": 1.00},   # inchangé
    "équipe marque": {"k": 0.985},  # -1.5% léger
}

def _apply_calib(prob: float, bet_type: str) -> float:
    """Multiplie la proba par le facteur de calibration du type, puis la borne."""
    k = CALIB.get(bet_type.lower(), {}).get("k", 1.0)
    return max(0.01, min(0.99, float(prob) * k))

import json

def _load_latest_calibration():
    """Charge les coefficients IC recalculés automatiquement."""
    path = os.path.join(BASE_DIR, "calibration_auto.json")
    if not os.path.exists(path):
        return CALIB
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        for k, v in data.items():
            if k in CALIB:
                CALIB[k]["k"] = float(v)
        print("✅ Calibration IC mise à jour depuis analyse_globale.")
    except Exception as e:
        print(f"⚠️ Erreur chargement calibration_auto.json : {e}")

_load_latest_calibration()

# -----------------------
# Initialisation
# -----------------------
print("🚀 FootBot PRO v2025.10 — Profil Volume (IC+Understat+Contexte)\n")

# ---------- Sélection robuste de la date d'exécution ----------
from datetime import datetime

def _parse_date_or_none(s: str):
    s = (s or "").strip()
    if not s:
        return None
    try:
        # accepte "YYYY-MM-DD" ou "DD/MM/YYYY"
        if "-" in s:
            datetime.strptime(s, "%Y-%m-%d")
            return s
        if "/" in s:
            d = datetime.strptime(s, "%d/%m/%Y")
            return d.strftime("%Y-%m-%d")
    except Exception:
        return None
    return None

def get_run_date():
    # 1️⃣ Argument CLI : py main.py 2025-10-23
    if len(sys.argv) >= 2:
        d = _parse_date_or_none(sys.argv[1])
        if d:
            print(f"📅 Date via CLI : {d}")
            return d

    # 2️⃣ Variable d’environnement
    d = _parse_date_or_none(os.environ.get("FOOTBOT_DATE", ""))
    if d:
        print(f"📅 Date via .env/FOOTBOT_DATE : {d}")
        return d

    # 3️⃣ Tentative input (sans bloquer PowerShell)
    try:
        s = input("📅 Entrez une date (YYYY-MM-DD) ou Entrée pour aujourd’hui : ").strip()
        d = _parse_date_or_none(s)
        if d:
            print(f"📅 Date saisie : {d}")
            return d
    except Exception:
        pass

    # 4️⃣ Fallback sûr : aujourd’hui
    today = datetime.now().strftime("%Y-%m-%d")
    print(f"📅 Date auto : {today}")
    return today

TODAY = get_run_date()



# -----------------------
# Exclusions & ligues valides
# -----------------------
EXCLUDED = set([
  
    # 🌍 Féminines
    "Damallsvenskan", "FA WSL", "Women Super League", "Division 1 Féminine",
    "Primera Division Women", "Bundesliga Women", "Serie A Women",
    "NWSL", "Liga MX Femenil", "Brasileirao Feminino", "UEFA Nations League - Women", "women"

    # 🌍 Amérique latine
    "Liga MX", 

    # 👶 Réserves / jeunes
    "U19", "U20", "U21", "U23", "Youth League", "MLS Next Pro",
    "Premier League 2", "Primavera", "Reserves", "B teams",

    # 🏆 Coupes nationales / Super Cups
    "Cup", "Super Cup", "Trophy", "Community Shield", "Taça", "coupe",
    "Copa del Rey", "Coupe de France", "Copa do Brasil", "copa"
    "Copa Argentina", "US Open Cup", "Emperor’s Cup", "supercopa", "EFL Cup", "FA Cup", "DFB Pokal",

    # 🌐 Internationales non-club
    "Friendly", "Friendlies", "International Champions Cup",
    "Club Friendlies", "National Team", "Uefa Youth", "CONMEBOL U20",
    "Euro U21", "Euro U19", "World Cup Women", "World Cup U20",
    "World Cup U17", "Olympics", "Asian Cup", "African Cup of Nations",
    "Concacaf Nations League", "CAF Champions League",

    # 🇺🇸 compétitions inférieures
    "USL Championship", "USL League One", "USL League Two", "NISA", "Ligue 2", "Championship",

    # 🇲🇽 divisions inférieures
    "Liga de Expansión MX",

    # 🇧🇷 divisions inférieures
    "Serie B", "Serie C", "Serie D",

    # 🇦🇷 divisions inférieures
    "Primera Nacional", "Primera B Metropolitana",

    # 🇪🇸 divisions inférieures
    "Segunda Federación", "Primera Federación", "Tercera División",

    # 🇮🇹 divisions inférieures
    "Serie C", "Serie D",

    # 🇫🇷 divisions inférieures
    "National 1", "National 2", "National 3",

    # 🇩🇪 divisions inférieures
    "3. Liga", "Regionalliga",

    # 🇬🇧 divisions inférieures
    "League One", "League Two", "National League", "FA Trophy", "EFL Trophy",

    # 🌏 Ligues asiatiques à exclure
    "AFC Champions League",
    "AGCFF Gulf Champions League",
])


# -----------------------
# Ligues valides = celles de leagues_list.py
# -----------------------

def is_relevant_league(country, league_name):
    if not league_name:
        return False

    lname = league_name.lower()  # ✅ définition manquante

    # ✅ Exception : garder uniquement les qualifications Coupe du Monde Europe
    if "qualification" in lname and "world cup" in lname:
        if "europe" in lname:
            return True       # 👍 garder Europe uniquement
        else:
            return False      # ❌ ignorer Afrique, Asie, AmSud, etc.

    # Ignorer ligues explicitement exclues
    if any(x.lower() in lname for x in EXCLUDED):
        return False

    # Vérifie si la ligue (pays, nom) est dans MAJOR_LEAGUES
    for item in MAJOR_LEAGUES:
        if isinstance(item, tuple):
            ctry, lig = item
            if country == ctry and league_name == lig:
                return True
        elif isinstance(item, str) and item.lower() in lname:
            return True

    return False


# -----------------------
# Mapping noms Understat
# -----------------------
from team_name_map import TEAM_NAME_MAP
def map_understat_name(name): return TEAM_NAME_MAP.get(name, name)

# -----------------------
# Utilitaires
# -----------------------
def zscore(x, mu, sigma): return 0.0 if sigma<=1e-9 else (x-mu)/sigma
def sigmoid(x): import math; return 1/(1+math.exp(-x))
def normalize3(a,b,c): s=a+b+c; return (a/s,b/s,c/s) if s>0 else (1/3,1/3,1/3)

ROWS, SUMMARY_ROWS = [], []

STATS = {
    "n_matches": 0,
    "n_understat": 0,
    "n_api": 0,
    "exec_time": 0.0
}

# ===========================================================
# 🎯 MODULE — Analyse spéciale compétitions européennes (EuropeMix)
# ===========================================================

EUROPEAN_COMPETITIONS = [
    "UEFA Champions League",
    "UEFA Europa League",
    "UEFA Europa Conference League"
]

LEAGUE_TIERS = {
    "elite": ["England", "Spain", "Germany", "Italy", "France"],
    "semi_elite": ["Netherlands", "Portugal", "Belgium", "Turkey", "Austria"],
    "minor": [
        "Switzerland", "Greece", "Scotland", "Denmark", "Norway",
        "Czech Republic", "Poland", "Croatia", "Serbia", "Romania",
        "Israel", "Hungary", "Bulgaria", "Finland", "Slovakia",
        "Slovenia", "Cyprus", "Azerbaijan"
    ]
}

LEAGUE_STRENGTH = {
    "Spain": 1.00, "England": 1.00, "Germany": 0.97,
    "Italy": 0.95, "France": 0.90, "Netherlands": 0.88,
    "Portugal": 0.86, "Belgium": 0.84, "Turkey": 0.83,
    "Austria": 0.82, "Croatia": 0.78, "Scotland": 0.78,
    "Denmark": 0.77, "Greece": 0.76, "Israel": 0.75
}


def is_european_competition(league_name: str) -> bool:
    """Détecte si le match appartient à une compétition européenne."""
    if not league_name:
        return False
    return any(name.lower() in league_name.lower() for name in EUROPEAN_COMPETITIONS)


def league_strength_factor(country):
    """Coefficient de force moyenne du championnat (impacte xG offensif)."""
    return LEAGUE_STRENGTH.get(country, 0.85)


def enrich_with_european_context(fx):
    """
    Combine la forme domestique et européenne, pondérée selon la force du championnat.
    Intègre H2H si dispo et ajuste les xG selon le niveau de la ligue.
    """
    home_id, away_id = fx["home_id"], fx["away_id"]
    season = fx["season"]
    league_name = fx.get("league_name", "")
    country = fx.get("country", "")

    if not is_european_competition(league_name):
        return fx  # Pas un match européen → on ne touche à rien

    # 1️⃣ Déterminer la catégorie du championnat
    def _get_tier(country):
        if country in LEAGUE_TIERS["elite"]:
            return "elite"
        if country in LEAGUE_TIERS["semi_elite"]:
            return "semi_elite"
        return "minor"

    tier = _get_tier(country)
    WEIGHTS = {
        "elite": (0.65, 0.35),
        "semi_elite": (0.50, 0.50),
        "minor": (0.35, 0.65)
    }
    w_dom, w_eur = WEIGHTS[tier]

    # 2️⃣ Récupérer la forme championnat
    league_id_dom = fx["league_id"]
    home_dom = get_recent_form(home_id, league_id_dom, season)
    away_dom = get_recent_form(away_id, league_id_dom, season)

    # 3️⃣ Récupérer la forme européenne (même saison)
    try:
        home_eur = get_recent_form(home_id, fx["league_id"], season)
        away_eur = get_recent_form(away_id, fx["league_id"], season)
    except Exception:
        home_eur = away_eur = {}

    # 4️⃣ Fusion pondérée  (championnat / Europe)
    def _merge(a, b):
        return round(w_dom * (a or 0) + w_eur * (b or 0), 2)

    fx["home_form"]["xg_for"] = _merge(home_dom.get("xg_for"), home_eur.get("xg_for"))
    fx["away_form"]["xg_for"] = _merge(away_dom.get("xg_for"), away_eur.get("xg_for"))
    fx["home_form"]["xg_against"] = _merge(home_dom.get("xg_against"), home_eur.get("xg_against"))
    fx["away_form"]["xg_against"] = _merge(away_dom.get("xg_against"), away_eur.get("xg_against"))

    # 5️⃣ H2H (complémentaire, jamais exclusif)
    try:
        h2h = get_btts_h2h(home_id, away_id)
        fx["h2h_score"] = h2h.get("score_h2h", 0.0)
        fx["btts_pct_h2h"] = h2h.get("btts_pct", 0.0)
    except Exception:
        fx["h2h_score"] = 0
        fx["btts_pct_h2h"] = 0

    # 6️⃣ Pondération de la force du championnat (impacte xG offensifs)
    coef_home = league_strength_factor(country)
    coef_away = league_strength_factor(country)
    fx["home_form"]["xg_for"] = round(fx["home_form"]["xg_for"] * coef_home, 2)
    fx["away_form"]["xg_for"] = round(fx["away_form"]["xg_for"] * coef_away, 2)

    # 7️⃣ Ajustement de l’Indice Confiance (IC)
    adj_factor = {"elite": 1.00, "semi_elite": 0.95, "minor": 0.90}[tier]
    fx["_ic_adj"] = adj_factor

    # 8️⃣ Stocker le contexte pour affichage et logs
    fx["_context"] = f"EuropeMix_{tier}"
    print(f"[EUROPEMix] {fx['home_team']} vs {fx['away_team']} | Tier={tier} | w_dom={w_dom} w_eur={w_eur} | IC_adj={adj_factor}")

    return fx


# ---------------------------------------------------------
# Cœur modèle : calcule IC + signaux pour un fixture donné
# ---------------------------------------------------------
# ===================== PATCH BTTS + xG + HTML =====================
# (1) Remplacement de compute_signals_for_profile : BTTS recalibré + pondération H2H
def compute_signals_for_profile(fx, P):
    sigs = []
    btts_h2h = 0.0

    # --- Ajustement spécial compétitions européennes (IC)
    ic_adj = fx.get("_ic_adj", 1.0)

    # --- Probabilités implicites (marché)
    p_home_odds, _, p_away_odds = implied_probs_1x2(fx)
    p_over15_odds = implied_prob_from_over(fx.get("odds_over_1_5") or 0)
    p_btts_odds = implied_prob_from_btts(fx.get("odds_btts_yes") or 0)

    # --- Forme récente (5–10) + xG proxies
    hf, af = fx.get("home_form", {}), fx.get("away_form", {})
    n_h, n_a = hf.get("n", 1), af.get("n", 1)

    # ✅ Moyennes corrigées : pas de double division
    def _per_match(val, n):
        try:
            v = float(val)
        except Exception:
            return 0.0
        if v <= 3.0:
            return v  # déjà une moyenne (API-Football)
        return v / max(n or 1, 1)

    gf_home = _per_match(hf.get("goals_for", hf.get("gf", 0)), n_h)
    ga_home = _per_match(hf.get("goals_against", hf.get("ga", 0)), n_h)
    gf_away = _per_match(af.get("goals_for", af.get("gf", 0)), n_a)
    ga_away = _per_match(af.get("goals_against", af.get("ga", 0)), n_a)

    xg_home = fx.get("xg_home") or max(0.2, float(hf.get("xg_for", 1.2)))
    xg_away = fx.get("xg_away") or max(0.2, float(af.get("xg_for", 1.1)))

    hw = hf.get("wins", 0) / (n_h or 1)
    aw = af.get("wins", 0) / (n_a or 1)

    # --- 1X2 (fusion simple marché + forme)
    ph_raw = 0.35 * p_home_odds + 0.65 * hw
    pa_raw = 0.35 * p_away_odds + 0.65 * aw
    s = (ph_raw + pa_raw) or 1.0
    ph, pa = ph_raw / s, pa_raw / s
    chosen_side = "home" if ph >= pa else "away"
    p_res = max(ph, pa)

    # --- H2H (unique appel)
    h2h_data = {}
    try:
        h2h_data = get_btts_h2h(fx["home_id"], fx["away_id"]) or {}
        btts_h2h = float(h2h_data.get("score_h2h", 0.0) or 0.0)
        home_win_pct = float(h2h_data.get("home_win_pct", 0.0) or 0.0)
        away_win_pct = float(h2h_data.get("away_win_pct", 0.0) or 0.0)
    except Exception:
        btts_h2h = 0.0
        home_win_pct = away_win_pct = 0.0

    # --- Bonus H2H Résultat
    if chosen_side == "home":
        if home_win_pct >= 0.8:   p_res = min(0.97, p_res + 0.05)
        elif home_win_pct >= 0.7: p_res = min(0.97, p_res + 0.04)
        elif home_win_pct >= 0.6: p_res = min(0.97, p_res + 0.02)
    else:
        if away_win_pct >= 0.8:   p_res = min(0.97, p_res + 0.05)
        elif away_win_pct >= 0.7: p_res = min(0.97, p_res + 0.04)
        elif away_win_pct >= 0.6: p_res = min(0.97, p_res + 0.02)

    # ---------- Application du facteur IC EuropeMix AVANT fusion des probabilités ----------
    p_res = _apply_calib(p_res, "Résultat")

    if ic_adj != 1.0:
        p_res *= ic_adj
        if p_over15_odds:
            p_over15_odds *= ic_adj
        if p_btts_odds:
            p_btts_odds *= ic_adj

    




    # --- Sous-fonction locale pour ajouter un signal ---
    def _add_signal(subtype, suggestion, p_model, odd):
        """
        Ajoute un signal dans la liste sigs avec sa proba, son IC et sa couleur.
        """
        try:
            odd = float(odd) if odd and float(odd) > 1.0 else 2.0
        except Exception:
            odd = 2.0

        res = "pending"
        color = "#bdc3c7"
        result_text = fx.get("result_display", "—")

        sigs.append([
            subtype,                     # Type (Résultat / Over / BTTS / Équipe marque)
            suggestion,                  # Texte du signal
            "IC",                        # Placeholder pour la colonne IC
            round(100 * p_model, 1),     # Probabilité %
            "Fusion",                    # Source
            res,                         # Statut (pending, correct, wrong)
            color,                       # Couleur
            result_text                  # Score si dispo
        ])

# ---------- Over 1.5 révisé : forme prioritaire + ajustements contextuels ----------
    odd_over = fx.get("odds_over_1_5")
    p_over15_odds = implied_prob_from_over(odd_over)
    lam = max(0.15, xg_home) + max(0.15, xg_away)

    # Modèle Poisson basé sur les xG cumulés
    try:
        p_over15_poisson = 1.0 - math.exp(-lam) * (1.0 + lam)
    except Exception:
        p_over15_poisson = 0.65

    # Moyennes récentes de buts marqués et encaissés
    gf_avg = (gf_home + gf_away) / 2
    ga_avg = (ga_home + ga_away) / 2

    # 🔸 Fusion pondérée : la forme compte plus que le marché
    if p_over15_odds is not None:
        p_over15 = (
            0.20 * p_over15_odds +       # Marché → 20 %
            0.40 * p_over15_poisson +    # Modèle xG → 40 %
            0.40 * ((gf_avg + ga_avg) / 2.2)  # Forme (buts marqués/encaissés) → 40 %
        )
    else:
        p_over15 = 0.60 * p_over15_poisson + 0.40 * ((gf_avg + ga_avg) / 2.2)

    # 🔸 Ajustements contextuels : renforce la logique de forme récente
    # Bonus si les deux équipes marquent souvent
    if gf_home > 1.4 and gf_away > 1.4:
        p_over15 += 0.04
    # Pénalité si défenses très solides
    if ga_home < 0.7 and ga_away < 0.7:
        p_over15 -= 0.03

    # 🔸 Ajustement selon la projection xG totale (match ouvert ou fermé)
    if (xg_home + xg_away) > 2.3:
        p_over15 += 0.03
    elif (xg_home + xg_away) < 1.8:
        p_over15 -= 0.04

    # Clamp pour garder la proba dans des bornes réalistes
    p_over15 = max(0.05, min(0.98, p_over15))

    # 🔸 Application du filtre de sélectivité avant ajout du signal
    p_over15 = _apply_calib(p_over15, "Over 1.5")

    if p_over15 >= P["O15_C"] and (xg_home + xg_away) > 2:
        _add_signal("Over 1.5", f"Over 1.5 buts (cote {fx.get('odds_over_1_5')})", p_over15, fx.get("odds_over_1_5"))



    # ---------- BTTS robuste (pondérations + garde-fous défensifs) ----------
    home_attack_vs_away_def = (gf_home + ga_away) / 2.0
    away_attack_vs_home_def = (gf_away + ga_home) / 2.0
    xg_dual_intensity = min(1.0, 0.5 * (xg_home / 1.7) + 0.5 * (xg_away / 1.7))

    w_odds, w_buts, w_xg, w_h2h = 0.30, 0.25, 0.20, 0.25
    if not btts_h2h:
        w_buts += 0.05; w_xg += 0.05; w_h2h = 0.05
    else:
        w_h2h = 0.20
        w_buts = 0.30
        w_xg = 0.15 

    def clamp01(v, lo=0.30, hi=0.95):
        return max(lo, min(hi, float(v)))

    comp_buts = clamp01((home_attack_vs_away_def + away_attack_vs_home_def) / 2.0)
    comp_xg   = clamp01(xg_dual_intensity)

    p_btts_raw = (
        w_odds * (p_btts_odds or 0.60) +
        w_buts * comp_buts +
        w_xg   * comp_xg +
        w_h2h  * (btts_h2h or 0.0)
    )

    # 🛡️ Garde-fous défensifs
    def defense_cap(ga_h, ga_a):
         if ga_h < 0.70 and ga_a < 0.70:
             return 0.55   # défenses d'acier
         if ga_h < 0.80 and ga_a < 0.80:
             return 0.65
         if ga_h < 0.90 or ga_a < 0.90:
             return 0.75
         return 0.90


    cap = defense_cap(ga_home, ga_away)
    if (xg_home >= 1.35 and xg_away >= 1.35) and (ga_home >= 0.75 or ga_away >= 0.75):
        cap = max(cap, 0.75)

    symmetry_bonus = 0.0
    if abs(xg_home - xg_away) <= 0.25 and (xg_home + xg_away) / 2 >= 1.35:
          symmetry_bonus = 0.01


    p_btts = min(cap, clamp01(p_btts_raw + symmetry_bonus, lo=0.35, hi=0.97))

    # ⚠️ pénalité si match déséquilibré (asymétrie forte)
    if abs(xg_home - xg_away) > 0.6:
        p_btts = max(0.35, p_btts - 0.10)

    # ✅ Conditions d’affichage BTTS révisées
    ok_def = (ga_home >= 1.00 and ga_away >= 1.00)
    ok_att = (gf_home >= 1.00 and gf_away >= 1.00)
    ok_xg  = (xg_home >= 1.10 and xg_away >= 1.10)


    # 🚫 Anti-faux positifs : si les deux défenses encaissent très peu
    if (ga_home < 0.9 and ga_away < 0.9):
      return sigs  # trop solides défensivement, on ne propose pas BTTS

    p_btts = _apply_calib(p_btts, "BTTS")

    if p_btts >= P["BTTS_C"] and ok_def and ok_att and ok_xg:
     _add_signal(
         "BTTS",
            f"Les deux équipes marquent (cote {fx.get('odds_btts_yes')})",
         p_btts,
          fx.get("odds_btts_yes")
    )


    # ---------- Équipe marque ----------
    try:
        home_condition = (gf_home >= 0.9 and ga_away >= 0.9 and xg_home >= 1.0)
        away_condition = (gf_away >= 0.9 and ga_home >= 0.9 and xg_away >= 1.0)

        if home_condition:
            p_team_home = min(0.95, (
                0.55*(xg_home/1.6) +
                0.20*gf_home +
                0.15*(btts_h2h or 0.0) +
                0.10*(1 - (1/(1+ga_away)))
            ))
            p_team_home = _apply_calib(p_team_home, "Équipe marque")
            if p_team_home >= P["TEAM_C"]:
                _add_signal("Équipe marque", f"{fx['home_team']} marque", p_team_home, fx.get("cote_home"))

        if away_condition:
            p_team_away = min(0.95, (
                0.55*(xg_away/1.6) +
                0.20*gf_away +
                0.15*(btts_h2h or 0.0) +
                0.10*(1 - (1/(1+ga_home)))
            ))
            p_team_away = _apply_calib(p_team_away, "Équipe marque")
            if p_team_away >= P["TEAM_C"]:
                _add_signal("Équipe marque", f"{fx['away_team']} marque", p_team_away, fx.get("cote_away"))
    except Exception as e:
        if DEBUG:
            print(f"[DEBUG] Erreur calcul équipe marque: {e}")

    # ---------- Application finale IC EuropeMix ----------
    if ic_adj != 1.0:
        p_res *= ic_adj
        p_over15 *= ic_adj
        p_btts *= ic_adj

    # ---------- Ajout des signaux principaux ----------
    if p_res >= (P["RES_C"] + 0.05):
        odd = fx.get("cote_home") if chosen_side == "home" else fx.get("cote_away")
        label = "Victoire Domicile" if chosen_side == "home" else "Victoire Extérieure"
        _add_signal("Résultat", f"{label} (cote {odd})", p_res, odd)

    fx["_xg_home_display"] = round(xg_home, 2)
    fx["_xg_away_display"] = round(xg_away, 2)

        # --- Attribution du résultat réel (pour le calcul des ratios) ---
    sh, sa = fx.get("score_home"), fx.get("score_away")

    def _eval_result(subtype, suggestion):
        """Détermine si le prono est correct, faux ou en attente."""
        if sh is None or sa is None:
            return "pending", "#bdc3c7"

        # --- Résultat 1X2
        if subtype == "Résultat":
            if chosen_side == "home" and sh > sa:
                return "correct", "#2ecc71"
            if chosen_side == "away" and sa > sh:
                return "correct", "#2ecc71"
            return "wrong", "#e74c3c"

        # --- Over 1.5
        if subtype == "Over 1.5":
            return ("correct", "#2ecc71") if (sh + sa) > 1.5 else ("wrong", "#e74c3c")

        # --- BTTS
        if subtype == "BTTS":
            return ("correct", "#2ecc71") if (sh > 0 and sa > 0) else ("wrong", "#e74c3c")

        # --- Équipe marque
        if subtype == "Équipe marque":
            if fx['home_team'] in suggestion and sh > 0:
                return "correct", "#2ecc71"
            if fx['away_team'] in suggestion and sa > 0:
                return "correct", "#2ecc71"
            return "wrong", "#e74c3c"

        return "pending", "#bdc3c7"

    # --- Mise à jour des signaux avec résultat réel ---
    for i, sig in enumerate(sigs):
        typ, sug, ic, probpct, src, _, _, _ = sig
        res, color = _eval_result(typ, sug)
        result_text = f"{sh}-{sa}" if (sh is not None and sa is not None) else "—"
        sigs[i] = [typ, sug, ic, probpct, src, res, color, result_text]

    return sigs


# ----------------------------------------------------------
# Lecture des seuils optimaux (issus de l’analyse globale)
# ----------------------------------------------------------
from bs4 import BeautifulSoup

def _load_optimal_thresholds_from_global():
    """
    Ouvre analyse_globale_footbot.html et récupère {Type -> Seuil_optimal}.
    Fallback sur None si absent.
    """
    try:
        base = os.path.dirname(__file__)
        path = os.path.join(base, "analyse_globale_footbot.html")
        if not os.path.exists(path):
            return {}
        with open(path, "r", encoding="utf-8") as f:
            html = f.read()
        soup = BeautifulSoup(html, "html.parser")
        table = soup.find("table", {"id": "tbl_summary"})
        if not table: 
            return {}
        # pandas to_html => 1ère ligne = headers <th>
        headers = [th.get_text(strip=True).lower() for th in table.find_all("th")]
        rows = []
        for tr in table.find_all("tr")[1:]:
            tds = [td.get_text(strip=True) for td in tr.find_all("td")]
            if len(tds) != len(headers): 
                continue
            rows.append(dict(zip(headers, tds)))

        out = {}
        for r in rows:
            typ = r.get("type", "")
            seuil = r.get("seuil optimal (%)") or r.get("seuil_optimal") or r.get("seuil optimal")
            if typ and seuil:
                try:
                    out[typ] = float(str(seuil).replace(",", ".").replace("%","").strip())
                except:
                    pass
        return out
    except Exception:
        return {}




# (2) Remplacement du bloc "Analyse & Stats" -> lignes + HTML avec xG_home/xG_away + style "papier"
def build_html(path_out, P, fixtures, today):
    """Construit le rapport HTML complet (style du 23/10, ratios + filtres + tri)."""

    stats = {"analysed": 0, "signals": 0, "correct": 0, "wrong": 0}
    types = {
        "Résultat": {"ok": 0, "ko": 0, "pending": 0},
        "Over 1.5": {"ok": 0, "ko": 0, "pending": 0},
        "BTTS": {"ok": 0, "ko": 0, "pending": 0},
        "Équipe marque": {"ok": 0, "ko": 0, "pending": 0}
    }

    rows_html = ""
    current_league = None

    for fx in fixtures:
        sigs = fx.get("_sigs", [])
        if not sigs:
            continue

        league = f"{fx.get('country','')} – {fx.get('league_name','')}"
        if league != current_league:
            rows_html += f"<tr class='section'><td colspan='13'>{league}</td></tr>"
            current_league = league

        stats["analysed"] += 1
        sh, sa = fx.get("score_home"), fx.get("score_away")
        result_display = f"{sh}–{sa}" if sh is not None and sa is not None else "—"

        for typ, sug, ic, probpct, src, res, color, result_text in sigs:
            stats["signals"] += 1
            if res == "correct":
                stats["correct"] += 1
                types[typ]["ok"] += 1
            elif res == "wrong":
                stats["wrong"] += 1
                types[typ]["ko"] += 1
            else:
                types[typ]["pending"] += 1

            # Couleur du texte selon le résultat
            if res == "correct":
                color = "color:#0da60d; font-weight:700;"
            elif res == "wrong":
                color = "color:#e00000; font-weight:700;"
            else:
                color = "color:#333;"
            row_bg = "background-color:#ffffff;"

            rows_html += (
                f"<tr style='{row_bg}'>"
                f"<td>{today}</td>"
                f"<td></td>"
                f"<td>{fx.get('league_name','')}</td>"
                f"<td>{fx.get('home_team','')} – {fx.get('away_team','')}</td>"
                f"<td>{fx.get('_xg_home_display',0):.2f}</td>"
                f"<td>{fx.get('home_form', {}).get('goals_against', 0):.2f}</td>"
                f"<td>{fx.get('_xg_away_display',0):.2f}</td>"
                f"<td>{fx.get('away_form', {}).get('goals_against', 0):.2f}</td>"
                f"<td>{typ}</td>"
                f"<td>{sug}</td>"
                f"<td>{ic}</td>"
                f"<td>{probpct}%</td>"
                f"<td>{src}</td>"
                f"<td style='{color}'>{result_display}</td>"
                f"</tr>"
            )

    # --- Calcul des ratios
    def ratio(ok, ko):
        total = ok + ko
        return f"{round(100 * ok / total, 1)}%" if total else "—"

    ratios = {
        "Résultat": ratio(types["Résultat"]["ok"], types["Résultat"]["ko"]),
        "Over 1.5": ratio(types["Over 1.5"]["ok"], types["Over 1.5"]["ko"]),
        "BTTS": ratio(types["BTTS"]["ok"], types["BTTS"]["ko"]),
        "Équipe marque": ratio(types["Équipe marque"]["ok"], types["Équipe marque"]["ko"]),
        "global": ratio(stats["correct"], stats["wrong"]),
    }

    counts = {
        t: f"{v['ok']}/{v['ok']+v['ko']+v['pending']}" for t, v in types.items()
    }

    # === Script JS (du 23/10, adapté avec doubles accolades)
    js_script = """
<script>
function sortTable(n) {{
  const table = document.getElementById("signalsTable");
  let switching = true;
  let dir = table.getAttribute("data-sort-dir") || "desc";
  let switchcount = 0;

  document.querySelectorAll("th").forEach(th => th.classList.remove("sorted"));
  if (table.rows[0] && table.rows[0].cells[n]) {{
    table.rows[0].cells[n].classList.add("sorted");
  }}

  while (switching) {{
    switching = false;
    const rows = table.rows;
    for (let i = 1; i < rows.length - 1; i++) {{
      let shouldSwitch = false;
      const x = rows[i].getElementsByTagName("TD")[n];
      const y = rows[i + 1].getElementsByTagName("TD")[n];
      if (!x || !y) continue;
      let xVal = parseFloat(x.textContent.replace('%','')) || x.textContent.toLowerCase();
      let yVal = parseFloat(y.textContent.replace('%','')) || y.textContent.toLowerCase();
      if (dir === "desc" ? xVal < yVal : xVal > yVal) {{
        shouldSwitch = true;
        break;
      }}
    }}
    if (shouldSwitch) {{
      rows[i].parentNode.insertBefore(rows[i + 1], rows[i]);
      switching = true;
      switchcount++;
    }} else {{
      if (switchcount === 0) {{
        dir = (dir === "desc") ? "asc" : "desc";
        table.setAttribute("data-sort-dir", dir);
        switching = true;
      }}
    }}
  }}
}}

function filterType(type) {{
  const table = document.getElementById("signalsTable");
  const rows = table.getElementsByTagName("tr");
  document.querySelectorAll(".card").forEach(btn => btn.classList.remove("active"));
  const activeBtn = Array.from(document.querySelectorAll(".card")).find(btn => btn.textContent.includes(type));
  if (activeBtn) activeBtn.classList.add("active");
  for (let i = 1; i < rows.length; i++) {{
    const cell = rows[i].getElementsByTagName("td")[8];
    if (!cell) continue;
    const val = cell.textContent.trim();
    if (val === type || type === "all") {{
      rows[i].style.display = "";
    }} else if (rows[i].classList.contains("section")) {{
      rows[i].style.display = "";
    }} else {{
      rows[i].style.display = "none";
    }}
  }}
}}
function showAll() {{ filterType("all"); }}
window.addEventListener("load", function() {{ sortTable(11); }});
</script>
"""

    # Seuils optimaux depuis l'analyse globale (si disponible)
    SEUILS_OPT = _load_optimal_thresholds_from_global()

    # === Encart de calibration automatique ===
    import json

    def _load_calibration_factors():
        """Lit calibration_auto.json et retourne un texte de synthèse."""
        try:
            path = os.path.join(BASE_DIR, "calibration_auto.json")
            if not os.path.exists(path):
                return "Calibration non trouvée."
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            txt_parts = []
            for k, v in data.items():
                delta = round((v - 1) * 100, 1)
                symb = "+" if delta > 0 else ""
                txt_parts.append(f"{k.upper()} {symb}{delta}%")
            return " · ".join(txt_parts)
        except Exception as e:
            return f"Erreur calibration : {e}"

    CALIB_INFO = _load_calibration_factors()

    calibration_html = f"""
<div class='note' style='margin-top:10px; text-align:center;'>
  <b>⚙️ Calibration active :</b> {CALIB_INFO}
</div>
"""

    def _fmt_opt(typ):
        if not SEUILS_OPT:
            return "—"
        for k, v in SEUILS_OPT.items():
            if k.lower() == typ.lower():
                return f"{v:.0f}%"
        return "—"

    seuils_html = f"""
<div class='note' style='margin-top:10px; text-align:center;'>
  <b>📊 Seuils optimaux (issus de l’analyse globale)</b><br>
  • <b>Résultat</b> → {_fmt_opt('Résultat')} &nbsp;|&nbsp;
  <b>Over 1.5</b> → {_fmt_opt('Over 1.5')} &nbsp;|&nbsp;
  <b>BTTS</b> → {_fmt_opt('BTTS')} &nbsp;|&nbsp;
  <b>Équipe marque</b> → {_fmt_opt('Équipe marque')}
</div>
"""

    # === HTML final (style du 23/10)
    html = f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<title>FootBot — Profil Volume — {today}</title>
<style>
:root {{
  --bg:#f4f7fa; --text:#2c3e50; --card:#fff; --muted:#6b7c93;
  --ok:#2ecc71; --ko:#e74c3c; --blue:#3498db;
}}
body {{
  font-family:Segoe UI,Arial,sans-serif;
  background:url('ai-stade.jpg') center/cover fixed no-repeat;
  color:var(--text);
  padding:24px;
  margin:0;
}}
.main-title {{
  text-align:center;
  font-size:1.9rem;
  font-weight:600;
  margin:10px 0 18px 0;
  color:#0e3b2c;
  text-shadow:0 1px 3px rgba(0,0,0,0.25);
}}
.panel {{
  background:rgba(255,255,255,0.92);
  border-radius:16px;
  box-shadow:0 6px 20px rgba(0,0,0,0.1);
  padding:18px 20px;
  margin:25px auto;
  max-width:1200px;
}}
.summary {{ text-align:center; margin-bottom:16px; }}
.summary p {{
  font-size:1rem; color:#1f2d27; background:rgba(255,255,255,0.95);
  display:inline-block; padding:8px 16px; border-radius:12px;
  box-shadow:0 2px 6px rgba(0,0,0,.05);
}}
.ratios {{
  display:flex; justify-content:center; flex-wrap:wrap; gap:10px; margin:10px 0 16px 0;
}}
.card {{
  flex:1; min-width:140px; max-width:190px; border-radius:12px; color:#fff; padding:10px 12px;
  font-size:0.9rem; text-align:center; border:none; cursor:pointer;
  transition:transform 0.15s ease, box-shadow 0.15s ease;
}}
.card:hover {{ transform:scale(1.05); box-shadow:0 4px 12px rgba(0,0,0,.15); }}
.card .val {{ font-weight:700; background:rgba(255,255,255,.15); padding:4px 6px; border-radius:8px; display:block; margin-top:6px; font-size:0.85rem; }}
.card.res {{ background:linear-gradient(135deg,#2980b9,#3498db); }}
.card.o15 {{ background:linear-gradient(135deg,#27ae60,#2ecc71); }}
.card.btts {{ background:linear-gradient(135deg,#8e44ad,#9b59b6); }}
.card.team {{ background:linear-gradient(135deg,#f39c12,#f1c40f); }}
table.signals {{
  width:100%;
  border-collapse:collapse;
  margin-top:20px;
  font-size:0.9rem;
  background:rgba(255,255,255,0.97);
  border-radius:10px;
  overflow:hidden;
  box-shadow:0 4px 12px rgba(0,0,0,0.05);
}}
table.signals thead th {{
  position:sticky;
  top:0;
  background:linear-gradient(135deg,#2980b9,#3498db);
  color:#fff;
  font-weight:600;
  z-index:10;
  cursor:pointer;
  text-align:center;
  padding:10px 6px;
  box-shadow:0 2px 4px rgba(0,0,0,0.1);
  user-select:none;
}}
th.sorted {{
  background:#1d6fa5 !important;
  box-shadow:inset 0 -3px 0 #fff;
}}
table.signals tbody td {{
  text-align:center;
  padding:8px 6px;
  border-bottom:1px solid #e0e0e0;
  background:rgba(255,255,255,0.97);
}}
.section td {{
  background:#eef5ff;
  font-weight:600;
  color:#1f3b5c;
  text-align:left;
  border-bottom:2px solid #c8daf5;
}}
</style>
</head>
<body>
<h1 class="main-title">⚽ Résumé FootBot : carte du {today} ⚽</h1>
<div class="panel">
  <div class="summary">
    <p>
      📊 <b>Matchs analysés :</b> {stats['analysed']} |
      💡 <b>Signaux :</b> {stats['signals']} |
      ✅ <b>{stats['correct']}</b> — ❌ <b>{stats['wrong']}</b> |
      🎯 <b>Taux global :</b> {ratios['global']}
    </p>
  </div>
  <div class="ratios">
    <button class="card res" onclick="filterType('Résultat')">
      ⚽ Résultat
      <div class="val">{ratios['Résultat']} ({counts['Résultat']})</div>
    </button>
    <button class="card o15" onclick="filterType('Over 1.5')">
      🔥 Over 1.5
      <div class="val">{ratios['Over 1.5']} ({counts['Over 1.5']})</div>
    </button>
    <button class="card btts" onclick="filterType('BTTS')">
      🤝 BTTS
      <div class="val">{ratios['BTTS']} ({counts['BTTS']})</div>
    </button>
    <button class="card team" onclick="filterType('Équipe marque')">
      🎯 Équipe marque
      <div class="val">{ratios['Équipe marque']} ({counts['Équipe marque']})</div>
    </button>
    <button class="card" style="background:linear-gradient(135deg,#7f8c8d,#95a5a6);" onclick="showAll()">
      🔄 Tout afficher
    </button>
  </div>
  {seuils_html}
  {calibration_html}
  <table class="signals" id="signalsTable">
    <thead>
      <tr>
        <th onclick="sortTable(0)">Date</th>
        <th onclick="sortTable(1)">Heure</th>
        <th onclick="sortTable(2)">Ligue</th>
        <th onclick="sortTable(3)">Match</th>
        <th onclick="sortTable(4)">xG Home</th>
        <th onclick="sortTable(5)">BE Home</th>
        <th onclick="sortTable(6)">xG Away</th>
        <th onclick="sortTable(7)">BE Away</th>
        <th onclick="sortTable(8)">Type</th>
        <th onclick="sortTable(9)">Suggestion</th>
        <th onclick="sortTable(10)">IC</th>
        <th onclick="sortTable(11)">Probabilité</th>
        <th onclick="sortTable(12)">Source</th>
        <th onclick="sortTable(13)">Résultat</th>
      </tr>
    </thead>
    <tbody>{rows_html}</tbody>
  </table>
</div>
{js_script}
</body>
</html>
"""

    with open(path_out, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"✅ Rapport HTML généré → {path_out}")

def main():
    global START_TIME
    START_TIME = time.time()

    print(f"📅 Date: {TODAY}")

    # 1️⃣ Chargement des matchs du jour
    print(f"\n🔎 Chargement des matchs du {TODAY} ...")
    fixtures = get_fixtures_by_date(TODAY)
    print(f"📦 {len(fixtures)} matchs récupérés pour la date {TODAY}")

    # 2️⃣ Filtrage des ligues pertinentes
    fixtures = [fx for fx in fixtures if is_relevant_league(fx.get("country"), fx.get("league_name"))]
    STATS["n_matches"] = len(fixtures)
    print(f"🏆 Ligues pertinentes : {STATS['n_matches']}")
    if not fixtures:
        print("⚠️ Aucun match pertinent trouvé.")
        return

    # 3️⃣ Mode test rapide
    FAST_MODE = False  # ⬅️ Passe à True pour tester rapidement
    if FAST_MODE:
        fixtures = fixtures[:15]
        print("⚡ Mode test rapide activé : 15 matchs seulement")


    # 3️⃣ Enrichissement des données
        # --- Normalisation ultra-robuste avant enrichissement ---
    def deep_flatten(obj):
        """Retourne une liste aplatie de tous les dictionnaires trouvés."""
        out = []
        if isinstance(obj, dict):
            out.append(obj)
        elif isinstance(obj, (list, tuple, set)):
            for el in obj:
                out.extend(deep_flatten(el))
        else:
            # Ignore tout ce qui n'est pas exploitable
            pass
        return out

    fixtures = deep_flatten(fixtures)
    fixtures = [fx for fx in fixtures if isinstance(fx, dict) and fx.get("home_team")]

    print(f"🧩 Fixtures aplaties (finales) : {len(fixtures)} objets de type dict")
    print(f"✅ Exemple type premier élément : {type(fixtures[0]) if fixtures else 'Aucun'}")


    # Vérifie la présence d’objets anormaux
    bad_items = [fx for fx in fixtures if not isinstance(fx, dict)]
    if bad_items:
        print(f"🚨 Attention : {len(bad_items)} objets non conformes détectés avant enrichissement")

    # Enrichissement des cotes & marchés (version liste → évite boucle et doublons)
    for fx in fixtures:
        enrich_with_odds_and_markets(fx)



        # 4️⃣ Fusion des xG Understat + API-Football
    for fx in fixtures:
        add_injuries_influents(fx)

        fx["home_form"] = get_recent_form(fx["home_id"], fx["league_id"], fx["season"], "home")
        fx["away_form"] = get_recent_form(fx["away_id"], fx["league_id"], fx["season"], "away")



        # Compétitions européennes
        if is_european_competition(fx.get("league_name", "")):
            fx = enrich_with_european_context(fx)

        # --- Fusion xG API-Football + Understat (parallélisé pour accélérer)
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(
                lambda args: get_team_expected(*args),
                [
                    (fx["home_id"], fx["league_id"], fx["season"]),
                    (fx["away_id"], fx["league_id"], fx["season"])
                ]
            ))
        api_home, api_away = results

        try:
            us_home = get_team_splits(fx["home_team"], fx["season"])
            us_away = get_team_splits(fx["away_team"], fx["season"])
        except Exception as e:
            print(f"[⚠️] Understat indisponible pour {fx['home_team']} ou {fx['away_team']}: {e}")
            us_home = us_away = {}

        def merge_xg(us_val, api_val):
            if us_val and api_val:
                return round(0.7 * us_val + 0.3 * api_val, 2)
            return round(us_val or api_val or 1.2, 2)

        fx["xg_home"] = merge_xg(us_home.get("xg_overall", 0), api_home.get("xg_for", 0))
        fx["xga_home"] = merge_xg(us_home.get("xga_overall", 0), api_home.get("xga", 0))
        fx["xg_away"] = merge_xg(us_away.get("xg_overall", 0), api_away.get("xg_for", 0))
        fx["xga_away"] = merge_xg(us_away.get("xga_overall", 0), api_away.get("xga", 0))

        print(f"[⚙️ Fusion xG] {fx['home_team']} {fx['xg_home']}/{fx['xga_home']}  vs  {fx['away_team']} {fx['xg_away']}/{fx['xga_away']}")

        # --- Comptage propre selon source principale
        if (
            (us_home and us_home.get("xg_overall", 0) > 0)
            or (us_away and us_away.get("xg_overall", 0) > 0)
        ):
            STATS["n_understat"] += 1
        else:
            STATS["n_api"] += 1



    # 5️⃣ Seuils IC
    P = {
    "RES_C": 0.70, "RES_TC": 0.85,
    "O15_C": 0.60, "O15_TC": 0.70,
    "BTTS_C": 0.70, "BTTS_TC": 0.85,
    "TEAM_C": 0.65, "TEAM_TC": 0.70
}


        # 6️⃣ Calcul des signaux (une seule fois, en parallèle) + stockage dans fx["_sigs"]
    def safe_compute(f):
        try:
            sigs = compute_signals_for_profile(f, P)
            f["_sigs"] = sigs
            return sigs
        except Exception as e:
            print(f"[❌ Signal] {f.get('home_team')} vs {f.get('away_team')} : {e}")
            f["_sigs"] = []
            return []

    print("⚙️ Calcul des signaux...")
    with ThreadPoolExecutor(max_workers=20) as ex:
        list(ex.map(safe_compute, fixtures))





            # 7️⃣ Génération du rapport HTML
    out_name = f"FootBot — Profil Volume — {TODAY}.html"
    out_path = os.path.join(BASE_DIR, out_name)

    # 6️⃣½ Rafraîchissement des scores finaux avant génération du HTML
    print("🔄 Mise à jour des scores finaux...")
    try:
        updated = 0
        live_data = get_fixtures_by_date(TODAY)
        live_map = {fx2["fixture_id"]: fx2 for fx2 in live_data if fx2.get("score_home") is not None}

        for fx in fixtures:
            fid = fx.get("fixture_id")
            if not fid:
                continue
            ref = live_map.get(fid)
            if ref and ref.get("score_home") is not None:
                fx["score_home"] = ref.get("score_home")
                fx["score_away"] = ref.get("score_away")
                updated += 1

        print(f"✅ Scores mis à jour pour {updated} matchs terminés.")
    except Exception as e:
        print(f"[⚠️] Erreur lors du rafraîchissement des scores : {e}")

    # ✅ Recalcule les signaux maintenant que les scores sont connus
    print("♻️ Recalcul des signaux avec scores finaux...")
    for fx in fixtures:
        fx["_sigs"] = compute_signals_for_profile(fx, P)

    # ✅ Génération du rapport HTML avec les taux corrects
    build_html(out_path, P, fixtures, TODAY)


    # 8️⃣ Résumé console
    print(f"✅ {len(fixtures)} matchs analysés | "
          f"{STATS['n_understat']} Understat | "
          f"{STATS['n_api']} API-Football | "
          f"{round(time.time() - START_TIME, 2)}s")
    print(f"📁 Rapport généré : {out_path}")


# ===================== TEST DE COHÉRENCE AVANT EXECUTION =====================
def preflight_check():
    """
    Vérifie que toutes les fonctions critiques existent avant d'appeler les APIs.
    Évite de gaspiller les quotas API si le script planterait plus tard.
    """
    import inspect

    required_funcs = [
        "compute_signals_for_profile",
        "build_html",
        "get_fixtures_by_date",
        "enrich_with_odds_and_markets",
        "get_recent_form",
        "get_btts_h2h"
    ]

    print("🧠 Vérification préliminaire FootBot...")

    missing = []
    for func in required_funcs:
        if func not in globals():
            missing.append(func)

    if missing:
        print(f"🚨 Fonctions manquantes : {', '.join(missing)}")
        print("❌ Arrêt avant les appels API.")
        sys.exit(1)

    # Vérifie les variables .env essentielles
    env_keys = ["API_FOOTBALL_KEY"]
    for k in env_keys:
        if not os.getenv(k):
            print(f"⚠️ Variable d'environnement manquante : {k}")
            print("➡️ Vérifie ton fichier .env avant de lancer FootBot.")
            sys.exit(1)

    # Test rapide sur un faux fixture (simulation sans API)
    try:
        fake_fixture = {
            "home_team": "Test FC",
            "away_team": "Bot United",
            "home_id": 1,
            "away_id": 2,
            "league_id": 999,
            "season": 2025,
            "odds_over_1_5": 1.80,
            "odds_btts_yes": 2.00,
            "odds_home": 2.10,
            "odds_away": 3.40,
            "home_form": {"n": 5, "wins": 3, "xg_for": 1.5, "xg_against": 1.0, "goals_for": 8, "goals_against": 5},
            "away_form": {"n": 5, "wins": 2, "xg_for": 1.3, "xg_against": 1.2, "goals_for": 6, "goals_against": 7},
        }

        compute_signals_for_profile(fake_fixture, {
            "RES_C": 0.70, "RES_TC": 0.80,
            "O15_C": 0.55, "O15_TC": 0.65,
            "BTTS_C": 0.60, "BTTS_TC": 0.70,
            "TEAM_C": 0.54, "TEAM_TC": 0.62
        })
        print("✅ Test de cohérence passé, le code est stable.")
    except Exception as e:
        print(f"❌ Erreur détectée avant requêtes API : {e}")
        print("➡️ Corrige cette erreur avant d'exécuter le script complet.")
        sys.exit(1)


# === POINT D’ENTRÉE ===
if __name__ == "__main__":
    preflight_check()   # 🔍 test rapide avant appels API
    main()


