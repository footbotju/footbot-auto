# db.py — gestion MySQL avec SQLAlchemy
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
import os

# Charger les variables du fichier .env
load_dotenv()

DB_URL = os.getenv("DB_URL")

# Créer la connexion SQLAlchemy
try:
    engine = create_engine(DB_URL)
except Exception as e:
    print(f"❌ Erreur de connexion MySQL: {e}")
    engine = None


def test_connection():
    """Teste la connexion à la base."""
    if not engine:
        print("❌ Aucune connexion à la base.")
        return False
    try:
        with engine.connect() as conn:
            res = conn.execute(text("SELECT NOW()"))
            print("✅ Connexion MySQL OK:", res.scalar())
        return True
    except Exception as e:
        print("❌ Database connection error:", e)
        return False


def insert_fixture(fx):
    """Insère ou met à jour un match (fixture) dans la base MySQL."""
    if not engine:
        print("⚠️ Impossible d’insérer : pas de connexion SQL.")
        return
    sql = text("""
        INSERT INTO fixtures (
            fixture_id, league_name, country, home_team, away_team, date_match,
            cote_home, cote_draw, cote_away, xg_home, xg_away
        )
        VALUES (
            :fixture_id, :league_name, :country, :home_team, :away_team, :date_match,
            :cote_home, :cote_draw, :cote_away, :xg_home, :xg_away
        )
        ON DUPLICATE KEY UPDATE
            cote_home = VALUES(cote_home),
            cote_draw = VALUES(cote_draw),
            cote_away = VALUES(cote_away),
            xg_home = VALUES(xg_home),
            xg_away = VALUES(xg_away)
    """)
    try:
        with engine.begin() as conn:
            conn.execute(sql, fx)
        print(f"💾 Fixture insérée : {fx.get('fixture_id')} ({fx.get('home_team')} vs {fx.get('away_team')})")
    except Exception as e:
        print(f"⚠️ Erreur SQL sur fixture {fx.get('fixture_id')}: {e}")
