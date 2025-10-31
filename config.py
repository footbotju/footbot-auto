import os
from dotenv import load_dotenv
load_dotenv()

API_FOOTBALL_KEY = os.getenv("API_FOOTBALL_KEY")
FOOTBALL_DATA_KEY = os.getenv("FOOTBALL_DATA_KEY")

USE_API_FOOTBALL = os.getenv("USE_API_FOOTBALL","false").lower() == "true"
MAX_AF_FIXTURES = int(os.getenv("MAX_AF_FIXTURES","20"))

USE_SQL = os.getenv("USE_SQL","true").lower() == "true"
DB_URL = os.getenv("DB_URL")

CACHE_TTL_DAYS = int(os.getenv("CACHE_TTL_DAYS","1"))
