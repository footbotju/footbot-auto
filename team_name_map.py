# =====================================================
# TEAM_NAME_MAP — Correspondance API-Football → Understat (v2025)
# =====================================================
# - Couvre intégralement les grands championnats européens supportés par Understat :
#   Premier League, La Liga, Serie A, Bundesliga, Ligue 1, Eredivisie, Primeira Liga
# - Inclut de nombreuses variantes (accents, abréviations, surnoms courants).
# - Fallback intelligent : si une équipe n’est pas dans le mapping, on renvoie le nom d’origine.
# - Pour les ligues non supportées par Understat (Belgique, Suisse, Suède, Danemark, Croatie,
#   Tchéquie, Autriche, MLS, Brésil, Argentine, Mexique, etc.), aucune correspondance n’est requise
#   car le robot utilisera les xG proxy internes (forme/tirs cadrés).
#
# Utilisation:
#   from team_name_map import map_understat_name
#   u_name = map_understat_name(api_football_team_name)
# =====================================================
import unicodedata

from typing import Dict

def _strip_accents(s: str) -> str:
    return ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn')

def _canon(s: str) -> str:
    s = s.strip()
    s = s.replace("’", "'")
    s = s.replace("`", "'")
    s = s.replace("´", "'")
    s = s.replace("“", '"').replace("”", '"')
    s = s.replace("&amp;", "&").replace("&", "and")
    s = s.replace(".", "").replace(",", "").replace(";", "").replace(":", "")
    s = s.replace("-", " ").replace("_", " ")
    s = s.replace("  ", " ").replace("  ", " ").lower()
    s = _strip_accents(s)
    return s

# -----------------------------------------------------
# Mapping principal API-Football → Understat
# -----------------------------------------------------
TEAM_NAME_MAP: Dict[str, str] = {
    # ==========================
    # 🇬🇧 Premier League (20)
    # ==========================
    "Arsenal": "Arsenal",
    "Aston Villa": "Aston Villa",
    "Bournemouth": "Bournemouth",
    "Brentford": "Brentford",
    "Brighton": "Brighton",
    "Burnley": "Burnley",
    "Chelsea": "Chelsea",
    "Crystal Palace": "Crystal Palace",
    "Everton": "Everton",
    "Fulham": "Fulham",
    "Ipswich": "Ipswich",
    "Ipswich Town": "Ipswich",
    "Leicester": "Leicester",
    "Leicester City": "Leicester",
    "Liverpool": "Liverpool",
    "Manchester City": "Manchester City",
    "Man City": "Manchester City",
    "Manchester United": "Manchester United",
    "Man Utd": "Manchester United",
    "Newcastle United": "Newcastle United",
    "Newcastle": "Newcastle United",
    "Nottingham Forest": "Nottingham Forest",
    "Southampton": "Southampton",
    "Tottenham": "Tottenham",
    "Tottenham Hotspur": "Tottenham",
    "West Ham": "West Ham",
    "West Ham United": "West Ham",
    "Wolverhampton": "Wolverhampton",
    "Wolves": "Wolverhampton",

    # ==========================
    # 🇪🇸 La Liga (20)
    # ==========================
    "Alaves": "Alaves",
    "Athletic Club": "Athletic Club",
    "Ath Bilbao": "Athletic Club",
    "Atletico Madrid": "Atletico Madrid",
    "Atlético Madrid": "Atletico Madrid",
    "Barcelona": "Barcelona",
    "Celta Vigo": "Celta Vigo",
    "Getafe": "Getafe",
    "Girona": "Girona",
    "Las Palmas": "Las Palmas",
    "Leganes": "Leganes",
    "Mallorca": "Mallorca",
    "Osasuna": "Osasuna",
    "Rayo Vallecano": "Rayo Vallecano",
    "Real Betis": "Real Betis",
    "Real Madrid": "Real Madrid",
    "Real Sociedad": "Real Sociedad",
    "Sevilla": "Sevilla",
    "Valencia": "Valencia",
    "Villarreal": "Villarreal",
    "Valladolid": "Valladolid",
    "Espanyol": "Espanyol",
    "Granada": "Granada",

    # ==========================
    # 🇮🇹 Serie A (20)
    # ==========================
    "AC Milan": "AC Milan",
    "Atalanta": "Atalanta",
    "Bologna": "Bologna",
    "Cagliari": "Cagliari",
    "Como": "Como",
    "Empoli": "Empoli",
    "Fiorentina": "Fiorentina",
    "Genoa": "Genoa",
    "Inter": "Inter",
    "Internazionale": "Inter",
    "Juventus": "Juventus",
    "Lazio": "Lazio",
    "Lecce": "Lecce",
    "Monza": "Monza",
    "Napoli": "Napoli",
    "Parma": "Parma",
    "Roma": "Roma",
    "AS Roma": "Roma",
    "Salernitana": "Salernitana",
    "Torino": "Torino",
    "Udinese": "Udinese",
    "Verona": "Verona",
    "Venezia": "Venezia",
    "Frosinone": "Frosinone",
    "Sassuolo": "Sassuolo",

    # ==========================
    # 🇩🇪 Bundesliga (18)
    # ==========================
    "Augsburg": "Augsburg",
    "Bayer Leverkusen": "Bayer Leverkusen",
    "Bayern Munich": "Bayern Munich",
    "Bochum": "Bochum",
    "Borussia Dortmund": "Borussia Dortmund",
    "Borussia M'gladbach": "Borussia M.Gladbach",
    "Borussia Monchengladbach": "Borussia M.Gladbach",
    "Eintracht Frankfurt": "Eintracht Frankfurt",
    "FC Heidenheim": "FC Heidenheim",
    "Hoffenheim": "Hoffenheim",
    "Mainz": "Mainz 05",
    "Mainz 05": "Mainz 05",
    "RB Leipzig": "RB Leipzig",
    "SC Freiburg": "SC Freiburg",
    "Union Berlin": "Union Berlin",
    "VfB Stuttgart": "VfB Stuttgart",
    "VfL Wolfsburg": "VfL Wolfsburg",
    "Werder Bremen": "Werder Bremen",
    "Köln": "Köln",
    "Cologne": "Köln",
    "Darmstadt": "Darmstadt",

    # ==========================
    # 🇫🇷 Ligue 1 (18 depuis 2023-24)
    # ==========================
    "Paris SG": "Paris Saint Germain",
    "Paris Saint-Germain": "Paris Saint Germain",
    "PSG": "Paris Saint Germain",
    "Marseille": "Marseille",
    "Olympique Marseille": "Marseille",
    "Lyon": "Lyon",
    "Olympique Lyonnais": "Lyon",
    "Monaco": "Monaco",
    "AS Monaco": "Monaco",
    "Lille": "Lille",
    "LOSC Lille": "Lille",
    "Nice": "Nice",
    "Rennes": "Rennes",
    "Stade Rennais": "Rennes",
    "Reims": "Reims",
    "Stade de Reims": "Reims",
    "Nantes": "Nantes",
    "Toulouse": "Toulouse",
    "Montpellier": "Montpellier",
    "Strasbourg": "Strasbourg",
    "Metz": "Metz",
    "Brest": "Brest",
    "Lens": "Lens",
    "RC Lens": "Lens",
    "Le Havre": "Havre AC",
    "Havre AC": "Havre AC",
    "Clermont": "Clermont Foot",
    "Clermont Foot": "Clermont Foot",
    "Lorient": "Lorient",
    "Angers": "Angers",
    "Auxerre": "Auxerre",
    "Ajaccio": "Ajaccio",
    "Dijon": "Dijon",

    # ==========================
    # 🇳🇱 Eredivisie (18)
    # ==========================
    "Ajax": "Ajax",
    "AZ": "AZ Alkmaar",
    "AZ Alkmaar": "AZ Alkmaar",
    "Feyenoord": "Feyenoord",
    "PSV": "PSV",
    "Twente": "Twente",
    "Utrecht": "Utrecht",
    "Vitesse": "Vitesse",
    "Groningen": "Groningen",
    "Heerenveen": "Heerenveen",
    "Heracles": "Heracles",
    "Go Ahead Eagles": "Go Ahead Eagles",
    "Fortuna Sittard": "Fortuna Sittard",
    "NEC": "NEC Nijmegen",
    "NEC Nijmegen": "NEC Nijmegen",
    "Sparta Rotterdam": "Sparta Rotterdam",
    "RKC Waalwijk": "RKC Waalwijk",
    "Volendam": "Volendam",
    "PEC Zwolle": "PEC Zwolle",
    "Zwolle": "PEC Zwolle",
    "Willem II": "Willem II",
    "Cambuur": "Cambuur",

    # ==========================
    # 🇵🇹 Primeira Liga (18)
    # ==========================
    "Benfica": "Benfica",
    "FC Porto": "Porto",
    "Porto": "Porto",
    "Sporting CP": "Sporting CP",
    "Sporting": "Sporting CP",
    "Braga": "Braga",
    "Boavista": "Boavista",
    "Casa Pia": "Casa Pia",
    "Chaves": "Chaves",
    "Estoril": "Estoril",
    "Famalicao": "Famalicao",
    "Famalicão": "Famalicao",
    "Gil Vicente": "Gil Vicente",
    "Moreirense": "Moreirense",
    "Portimonense": "Portimonense",
    "Rio Ave": "Rio Ave",
    "Vizela": "Vizela",
    "Farense": "Farense",
    "Arouca": "Arouca",
    "Estrela": "Estrela",
    "Santa Clara": "Santa Clara",
}

# -----------------------------------------------------
# Alias supplémentaires (formes abrégées fréquentes)
# -----------------------------------------------------
ALIASES = {
    # PL / UK
    "man utd": "Manchester United",
    "manchester utd": "Manchester United",
    "man united": "Manchester United",
    "man u": "Manchester United",
    "man city": "Manchester City",
    "spurs": "Tottenham",
    "wolves": "Wolverhampton",
    "west ham utd": "West Ham",
    "west ham united": "West Ham",
    # La Liga
    "atletico": "Atletico Madrid",
    "ath bilbao": "Athletic Club",
    # Ligue 1
    "psg": "Paris Saint Germain",
    "stade rennais": "Rennes",
    "stade de reims": "Reims",
    "rc lens": "Lens",
    # Bundesliga
    "monchengladbach": "Borussia M.Gladbach",
    "mgladbach": "Borussia M.Gladbach",
    "koln": "Köln",
    "fc koln": "Köln",
    # Eredivisie
    "nec": "NEC Nijmegen",
}

# Pré-calcul canonique pour accélérer les recherches
import unicodedata as _ud
_CANON_KEYS = { _canon(k): v for k,v in (list(TEAM_NAME_MAP.items()) + list(ALIASES.items())) }

def map_understat_name(name: str) -> str:
    """
    Retourne le nom Understat correspondant à `name` (API-Football),
    sinon renvoie `name` si aucune correspondance n'est trouvée.
    """
    if not name:
        return name
    # 1) match direct
    if name in TEAM_NAME_MAP:
        return TEAM_NAME_MAP[name]
    # 2) match canonique
    c = _canon(name)
    if c in _CANON_KEYS:
        alias = _CANON_KEYS[c]
        return TEAM_NAME_MAP.get(alias, alias)
    # 3) fallback (identité)
    return name
