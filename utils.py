import math, os, json, hashlib
from datetime import datetime, timedelta
from scipy.stats import poisson
from config import CACHE_TTL_DAYS

# --- maths ---
def logistic(x):
    return 1.0 / (1.0 + math.exp(-x))

def normalize_implied_probs(c_home, c_draw, c_away):
    try:
        pH, pD, pA = 1.0/float(c_home), 1.0/float(c_draw), 1.0/float(c_away)
    except Exception:
        return 0.5, 0.2, 0.3
    s = pH + pD + pA
    return pH/s, pD/s, pA/s

def poisson_over(lambda_total, line):
    return 1 - poisson.cdf(math.floor(line), lambda_total)

# --- cache fichiers ---
CACHE_DIR = os.path.join(os.getcwd(), "cache")
os.makedirs(CACHE_DIR, exist_ok=True)

def _cache_path(key: str):
    h = hashlib.sha1(key.encode()).hexdigest()
    return os.path.join(CACHE_DIR, f"{h}.json")

def cache_get(key: str):
    path = _cache_path(key)
    if not os.path.exists(path):
        return None
    mtime = datetime.fromtimestamp(os.stat(path).st_mtime)
    if datetime.now() - mtime > timedelta(days=CACHE_TTL_DAYS):
        return None
    with open(path, "r", encoding="utf8") as f:
        return json.load(f)

def cache_set(key: str, data):
    path = _cache_path(key)
    with open(path, "w", encoding="utf8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
