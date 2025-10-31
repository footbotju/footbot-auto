# ==========================
#  Module : euro_profile_ext.py
#  Version : 1.0 — Oct 2025
#  Analyse spécifique compétitions européennes
# ==========================

import statistics
from api_football_ext import get_recent_form, get_btts_h2h

# ----------------------------
# Détection compétition européenne
# ----------------------------
def is_competition_europeenne(league_name: str) -> bool:
    if not league_name:
        return False
    name = league_name.lower()
    return any(x in name for x in [
        "champions league", "uefa europa", "conference league"
    ])

# ----------------------------
# Niveau de ligue (indice UEFA simplifié)
# ----------------------------
def get_league_strength(country: str) -> float:
    if not country:
        return 0.7
    levels = {
        "england": 1.0, "spain": 1.0, "germany": 1.0, "italy": 1.0,
        "france": 0.9, "portugal": 0.9, "netherlands": 0.9,
        "belgium": 0.85, "switzerland": 0.85, "turkey": 0.85,
        "scotland": 0.8, "austria": 0.8, "norway": 0.75, "czech": 0.75,
        "israel": 0.7, "hungary": 0.7, "cyprus": 0.7,
    }
    return levels.get(country.lower(), 0.7)

# ----------------------------
# Expérience européenne du club (0.5 → 1.0)
# ----------------------------
def get_euro_experience(team_name: str) -> float:
    if not team_name:
        return 0.6
    known = {
        "real madrid": 1.0, "bayern": 0.96, "manchester city": 0.94, "barcelona": 0.92,
        "liverpool": 0.9, "inter": 0.88, "porto": 0.87, "benfica": 0.86,
        "milan": 0.86, "psg": 0.84, "juventus": 0.84, "sevilla": 0.82,
        "roma": 0.8, "sporting": 0.78, "leverkusen": 0.78,
        "feyenoord": 0.76, "lazio": 0.76, "marseille": 0.74,
        "atalanta": 0.7, "braga": 0.7, "rangers": 0.7,
    }
    for k, v in known.items():
        if k in team_name.lower():
            return v
    return 0.6

def analyser_europe(fx, get_fixtures_by_team):
    league = fx.get("league_name", "").lower()
    round_name = fx.get("round", "").lower()
    team_home, team_away = fx["home_team"], fx["away_team"]
    season = fx.get("season")

    # Phase du tournoi
    if any(k in round_name for k in ["group", "poule"]):
        w_form, w_uefa, w_h2h = 0.5, 0.3, 0.2
    elif any(k in round_name for k in ["1/8", "quarter", "quart", "semi", "demi"]):
        w_form, w_uefa, w_h2h = 0.3, 0.5, 0.2
    elif "final" in round_name:
        w_form, w_uefa, w_h2h = 0.4, 0.6, 0.0
    else:
        w_form, w_uefa, w_h2h = 0.4, 0.4, 0.2

    # Historique UEFA (dernier 12 mois)
    recent_home = get_fixtures_by_team(fx["home_id"], season, europe_only=True)
    recent_away = get_fixtures_by_team(fx["away_id"], season, europe_only=True)

    # Facteur expérience
    exp_home = min(1.1, 1 + len(recent_home) / 30)
    exp_away = min(1.1, 1 + len(recent_away) / 30)

    # Moyenne de buts récents (Europe)
    avg_goals_home = sum(m['goals_for'] for m in recent_home[-5:]) / max(1, len(recent_home[-5:]))
    avg_goals_away = sum(m['goals_for'] for m in recent_away[-5:]) / max(1, len(recent_away[-5:]))

    # Probabilités finales ajustées
    p_home = round(0.5 * exp_home * w_uefa + w_form * fx['home_form']['wins'], 3)
    p_away = round(0.5 * exp_away * w_uefa + w_form * fx['away_form']['wins'], 3)
    p_over15 = round((avg_goals_home + avg_goals_away) / 3.2, 3)
    p_btts = round(0.5 * (p_over15 + 0.5 * (avg_goals_home > 0.8) + (avg_goals_away > 0.8)), 3)

    return {
        "p_home": p_home,
        "p_away": p_away,
        "p_over15": p_over15,
        "p_btts": p_btts
    }


# ----------------------------
# Forme européenne actuelle (même saison)
# ----------------------------
def get_forme_europe(team_id, season, get_fixtures_by_team):
    """
    Récupère les matchs européens de la saison en cours
    et renvoie un dict avec moyenne buts, xG et BTTS rate.
    """
    try:
        fixtures = get_fixtures_by_team(team_id)
        euro_games = [
            f for f in fixtures
            if f.get("league_name") and any(x in f["league_name"].lower() for x in ["champions", "europa", "conference"])
            and f.get("season") == season
        ]
        if not euro_games:
            return {"n": 0, "goals_for": 0, "goals_against": 0, "xg_for": 1.2, "btts_rate": 0.5}

        goals_for = [f.get("score_home") if f.get("home_id") == team_id else f.get("score_away") for f in euro_games if f.get("score_home") is not None]
        goals_against = [f.get("score_away") if f.get("home_id") == team_id else f.get("score_home") for f in euro_games if f.get("score_home") is not None]
        btts = [1 for f in euro_games if f.get("score_home") and f.get("score_away") and f["score_home"] > 0 and f["score_away"] > 0]

        return {
            "n": len(euro_games),
            "goals_for": sum(goals_for) / len(goals_for) if goals_for else 0,
            "goals_against": sum(goals_against) / len(goals_against) if goals_against else 0,
            "btts_rate": len(btts) / len(euro_games),
            "xg_for": 1.3 + 0.1 * (sum(goals_for) / len(goals_for) if goals_for else 1.2)
        }
    except Exception as e:
        print(f"[WARN] Erreur get_forme_europe: {e}")
        return {"n": 0, "goals_for": 0, "goals_against": 0, "xg_for": 1.2, "btts_rate": 0.5}

# ----------------------------
# Analyse globale d’un match européen
# ----------------------------
def analyser_europe(fx, get_fixtures_by_team):
    """
    Combine forme nationale, forme européenne, H2H, expérience, force ligue.
    Retourne un dict avec p_home, p_away, p_over15, p_btts.
    """
    home = fx.get("home_team", "")
    away = fx.get("away_team", "")
    season = fx.get("season")

    # Forme nationale existante
    hf = fx.get("home_form", {"xg_for": 1.3, "wins": 0.5})
    af = fx.get("away_form", {"xg_for": 1.2, "wins": 0.45})

    # Forme européenne actuelle
    euro_home = get_forme_europe(fx["home_id"], season, get_fixtures_by_team)
    euro_away = get_forme_europe(fx["away_id"], season, get_fixtures_by_team)

    # Expérience et force championnat
    exp_home = get_euro_experience(home)
    exp_away = get_euro_experience(away)
    str_home = get_league_strength(fx.get("country", ""))
    str_away = get_league_strength(fx.get("country", ""))

    # H2H
    btts_h2h = get_btts_h2h(fx["home_id"], fx["away_id"], fx["home_id"])

    # Pondérations (selon recherche empirique)
    W_FORM_DOM = 0.30
    W_FORM_EUR = 0.35
    W_H2H = 0.15
    W_EXP = 0.10
    W_LEAGUE = 0.10

    # Résultat global pondéré
    p_home = (
        W_FORM_DOM * hf.get("wins", 0.5)
        + W_FORM_EUR * (euro_home["goals_for"] / max(1, euro_home["n"]))
        + W_H2H * (1 - btts_h2h / 2)
        + W_EXP * exp_home
        + W_LEAGUE * str_home
    )

    p_away = (
        W_FORM_DOM * af.get("wins", 0.5)
        + W_FORM_EUR * (euro_away["goals_for"] / max(1, euro_away["n"]))
        + W_H2H * (1 - btts_h2h / 2)
        + W_EXP * exp_away
        + W_LEAGUE * str_away
    )

    # Over/BTTS : basé sur intensité offensive européenne
    p_over15 = 0.4 * (euro_home["xg_for"] + euro_away["xg_for"]) / 2 + 0.3 * euro_home["btts_rate"] + 0.3 * euro_away["btts_rate"]
    p_btts = (euro_home["btts_rate"] + euro_away["btts_rate"]) / 2

    # Clamp 0–1
    p_home = max(0, min(1, p_home))
    p_away = max(0, min(1, p_away))
    p_over15 = max(0, min(1, p_over15))
    p_btts = max(0, min(1, p_btts))

    return {
        "p_home": round(p_home, 3),
        "p_away": round(p_away, 3),
        "p_over15": round(p_over15, 3),
        "p_btts": round(p_btts, 3)
    }
