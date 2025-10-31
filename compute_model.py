import math
from utils import logistic, normalize_implied_probs, poisson_over

# Poids & seuils
W_FORM, W_XG, W_H2H, W_DEF, W_BOOK = 0.35, 0.25, 0.15, 0.15, 0.10
K = 1.5
MAX_REF_XGA = 3.0
MIN_MATCHES = 5
MIN_H2H = 4

def analyze_fixture(fx: dict):
    missing = 0
    xg_home = fx.get("xg_home"); xg_away = fx.get("xg_away")
    if xg_home is None or xg_away is None:
        xg_home, xg_away = 1.25, 1.05; missing += 1

    cH = fx.get("cote_home", 1.80)
    cD = fx.get("cote_draw", 3.40)
    cA = fx.get("cote_away", 4.20)
    pH_book, pD_book, pA_book = normalize_implied_probs(cH, cD, cA)

    # Forme locale / H2H (déjà fournis par fetch_data)
    N_matches = fx.get("N_form", 0)
    P_form = fx.get("P_form", 0.65)
    if N_matches < MIN_MATCHES: P_form *= 0.5

    H2H_count = fx.get("H2H_count", 0)
    P_H2H = fx.get("P_H2H", 0.60)
    if H2H_count < MIN_H2H: P_H2H *= 0.5

    # Défense (proxy)
    P_def = max(0.0, 1.0 - (xg_away / MAX_REF_XGA))

    # Blessures (à brancher si lineups) : 1.00 par défaut
    F_injury = fx.get("F_injury", 1.00)
    if F_injury <= 0.85:
        return {
            "fixture_id": fx["fixture_id"],
            "IC": "NoSignal",
            "signal": "BLOCKED",
            "notes": f"N={N_matches},H2H={H2H_count},injury={F_injury}"
        }

    # P_xG & P_book
    P_xG = logistic(K * (xg_home - xg_away))
    P_book = pH_book

    # Score pondéré + caveat domicile
    score_raw = (W_FORM*P_form + W_XG*P_xG + W_H2H*P_H2H + W_DEF*P_def + W_BOOK*P_book)
    if F_injury > 1.00: score_raw *= 1.05
    score_final = min(1.0, max(0.0, score_raw * 1.05))

    # Votes corroboration
    votes = (1 if P_xG >= 0.60 else 0) + (1 if P_form >= 0.60 else 0) + (1 if P_H2H >= 0.60 else 0)

    # EV & IC
    P_model = score_final
    EV_home = P_model * (cH - 1) - (1 - P_model)

    IC, signal = "NoSignal", "NO"
    if (score_final >= 0.70 and P_model >= 0.70 and EV_home >= 0.04 and cH >= 1.70
        and votes == 3 and F_injury > 0.90 and N_matches >= MIN_MATCHES):
        IC, signal = "Très conservateur", "YES"
    elif (score_final >= 0.65 and P_model >= 0.65 and EV_home >= 0.02 and cH >= 1.60
          and votes >= 2 and F_injury > 0.85 and N_matches >= MIN_MATCHES):
        IC, signal = "Conservateur", "YES"

    if missing >= 2:
        IC, signal = "NoSignal", "LOWDATA"

    # Over/BTTS
    lam_total = xg_home + xg_away
    p_over_1_5 = poisson_over(lam_total, 1.5)
    p_over_2_5 = poisson_over(lam_total, 2.5)
    p_BTTS = 1 - math.exp(-xg_home) - math.exp(-xg_away) + math.exp(-(xg_home + xg_away))

    suggest_over_1_5 = "Très conservateur (YES)" if p_over_1_5 >= 0.80 else ("Conservateur (YES)" if p_over_1_5 >= 0.70 else "NO")
    suggest_over_2_5 = "Très conservateur (YES)" if p_over_2_5 >= 0.80 else ("Conservateur (YES)" if p_over_2_5 >= 0.70 else "NO")
    suggest_BTTS = "YES" if p_BTTS >= 0.70 else "NO"

    return {
        "fixture_id": fx["fixture_id"],
        "p_home_win": round(P_model,3),
        "p_draw": round(pD_book,3),
        "p_away_win": round(pA_book,3),
        "score_final_home": round(score_final,3),
        "EV_home": round(EV_home,3),
        "IC": IC,
        "signal": signal,
        "p_over_1_5": round(p_over_1_5,3),
        "suggest_over_1_5": suggest_over_1_5,
        "p_over_2_5": round(p_over_2_5,3),
        "suggest_over_2_5": suggest_over_2_5,
        "p_BTTS": round(p_BTTS,3),
        "suggest_BTTS": suggest_BTTS,
        "corroboration_votes": votes,
        "notes": f"N={N_matches},H2H={H2H_count},injury={F_injury}"
    }
