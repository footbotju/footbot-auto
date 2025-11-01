# ================================
# analyse_globale.py — FootBot Global Analyzer (v6 robust)
# ================================

import os, re, glob, pandas as pd, numpy as np
from bs4 import BeautifulSoup
from io import StringIO
import json

BASE_DIR = os.path.dirname(__file__)
RAPPORTS_DIR = os.path.join(BASE_DIR, "rapports_quotidiens")
OUT_HTML = os.path.join(BASE_DIR, "analyse_globale_footbot.html")

def extract_float(txt):
    try:
        return float(str(txt).replace(",", ".").replace("%", "").strip())
    except Exception:
        return None

def pick_numeric_col(df, candidates):
    """
    Choose the first column in `candidates` that actually contains numeric-like values.
    Returns column name or None.
    """
    for c in candidates:
        if c in df.columns:
            vals = pd.to_numeric(df[c].astype(str).str.replace("%","").str.replace(",","."), errors="coerce")
            # consider it numeric if at least 30% are numbers
            if vals.notna().mean() >= 0.3:
                return c
    return None

# ----------------------------------------------------------
# 1) Read all reports
# ----------------------------------------------------------
html_files = sorted(glob.glob(os.path.join(RAPPORTS_DIR, "FootBot — Profil Volume — *.html")))
if not html_files:
    print("⚠️ Aucun rapport trouvé dans 'rapports_quotidiens'.")
    raise SystemExit()

print(f"📊 {len(html_files)} rapports trouvés → analyse en cours...")

all_rows = []
for path in html_files:
    with open(path, encoding="utf-8") as f:
        html = f.read()

    soup = BeautifulSoup(html, "html.parser")
    txt = soup.get_text(" ")

    # taux global (optional)
    m = re.search(r"Taux global\s*[:=]\s*([\d,.]+)%", txt)
    taux_global = extract_float(m.group(1)) if m else None

    # main table (by id or class)
    main_table = soup.find("table", {"id": "signalsTable"}) or soup.find("table", {"class": "signals"})
    if not main_table:
        continue

    try:
        df = pd.read_html(StringIO(str(main_table)))[0]

        # ---- Standardize headers
        rename = {}
        for c in df.columns:
            lc = str(c).strip().lower()
            if "type" in lc:
                rename[c] = "Type"
            elif "ligue" in lc or "league" in lc:
                rename[c] = "Ligue"
            elif "prob" in lc:           # "Probabilité"
                rename[c] = "Probabilite"
            elif lc == "ic":
                # In your HTML, the "IC" column is LABEL text ("IC"), not a number.
                # We'll rename it to "IC_label" to avoid confusion.
                rename[c] = "IC_label"
            elif "résultat" in lc or "result" in lc:
                rename[c] = "Resultat"

        df = df.rename(columns=rename)

        # ---- Build a real numeric "IC" column from whichever is numeric:
        # Prefer Probabilite; otherwise fallback to a truly numeric "IC" if present
        proba_col = pick_numeric_col(df, ["Probabilite", "IC", "Proba", "Confidence", "Score"])
        if proba_col is None:
            # no numeric signal in this table → skip it
            continue

        df["IC"] = pd.to_numeric(df[proba_col].astype(str).str.replace("%","").str.replace(",","."), errors="coerce")

        # Keep essentials
        df["source_file"] = os.path.basename(path)
        df["taux_global"] = taux_global
        all_rows.append(df)
    except Exception:
        continue

if not all_rows:
    print("❌ Aucun tableau exploitable détecté.")
    raise SystemExit()

df = pd.concat(all_rows, ignore_index=True)

# ----------------------------------------------------------
# 2) Cleaning
# ----------------------------------------------------------
# ensure Type exists
if "Type" not in df.columns:
    print("❌ Colonne 'Type' manquante après lecture — arrêt.")
    raise SystemExit()

# keep only rows that have a type and a numeric IC
df = df[df["Type"].notna()]
df = df[pd.to_numeric(df["IC"], errors="coerce").notna()]

if df.empty:
    # still render a minimal HTML so you can see something
    with open(OUT_HTML, "w", encoding="utf-8") as f:
        f.write("<html><body><h1>Aucune donnée exploitable trouvée</h1></body></html>")
    print(f"✅ Rapport HTML généré → {OUT_HTML}")
    raise SystemExit()

# ----------------------------------------------------------
# 3) Aggregations
# ----------------------------------------------------------
# Period (best effort from file names)
import re as _re
from datetime import datetime

# Extraire toutes les dates trouvées dans les noms de fichiers
dates_trouvees = []
for f in html_files:
    m = _re.search(r"(\d{4}-\d{2}-\d{2})", f)
    if m:
        try:
            d = datetime.strptime(m.group(1), "%Y-%m-%d")
            dates_trouvees.append(d)
        except Exception:
            pass

if dates_trouvees:
    d_min = min(dates_trouvees)
    d_max = max(dates_trouvees)
    periode = f"Du {d_min.strftime('%Y-%m-%d')} au {d_max.strftime('%Y-%m-%d')}"
else:
    periode = f"Jusqu’au {datetime.now().strftime('%Y-%m-%d')} (période inconnue)"

# Summary by type: use IC as the success proxy (mean of numeric ICs)
# --- Résumé par type : taux de réussite réel et IC moyen gagnant ---

def parse_score(score):
    """Extrait buts domicile / extérieur à partir du texte de score ('2–1', '1-0', etc.)"""
    if isinstance(score, str):
        parts = re.split(r"[–\-:]", score)
        if len(parts) == 2:
            try:
                return int(parts[0].strip()), int(parts[1].strip())
            except ValueError:
                return None, None
    return None, None


def is_won(row):
    """Retourne True si le pari est gagnant selon le type et le score final."""
    sh, sa = parse_score(row.get("Resultat"))
    if sh is None:
        return None  # match non joué ou score vide

    t = str(row.get("Type") or "").lower().strip()
    sugg = str(row.get("Suggestion") or "").lower()

    # Résultat
    if "résultat" in t or "result" in t:
        if sh > sa and ("domicile" in sugg or "home" in sugg):
            return True
        if sa > sh and ("extérieur" in sugg or "away" in sugg):
            return True
        if sh == sa and ("nul" in sugg or "draw" in sugg):
            return True
        return False

    # Over 1.5
    if "over" in t and "1.5" in t:
        return (sh + sa) > 1.5

    # BTTS
    if "btts" in t or "deux" in t or "both" in t:
        return (sh > 0 and sa > 0)

    # Équipe marque
    if "équipe marque" in t or "equipe marque" in t:
        home_team = str(row.get("Match")).split("–")[0].strip().lower()
        away_team = str(row.get("Match")).split("–")[-1].strip().lower()
        if home_team in sugg and sh > 0:
            return True
        if away_team in sugg and sa > 0:
            return True
        return False

    return None


# Conversion IC en float propre
df["IC_val"] = pd.to_numeric(df["IC"].astype(str).str.replace("%", "").str.replace(",", "."), errors="coerce")

# Ajout du statut gagné/perdu
df["won"] = df.apply(is_won, axis=1)

# --- Agrégation par Type ---
rows = []
for t, g in df.groupby("Type"):
    total = g["won"].notna().sum()
    wins = g["won"].eq(True).sum()
    taux = round((wins / total * 100), 1) if total > 0 else np.nan
    ic_mean = round(g.loc[g["won"] == True, "IC_val"].mean(), 1)
    rows.append({
        "Type": t,
        "Matchs": total,
        "Taux_moy": taux,
        "IC_moy": ic_mean
    })

summary = pd.DataFrame(rows)

# --- Agrégation par Ligue (même logique) ---
if "Ligue" in df.columns:
    league_rows = []
    for (t, lig), g in df.groupby(["Type", "Ligue"]):
        total = g["won"].notna().sum()
        wins = g["won"].eq(True).sum()
        taux = round((wins / total * 100), 1) if total > 0 else np.nan
        ic_mean = round(g.loc[g["won"] == True, "IC_val"].mean(), 1)
        league_rows.append({
            "Type": t,
            "Ligue": lig,
            "Matchs": total,
            "Taux_moy": taux,
            "IC_moy": ic_mean
        })
    by_league = pd.DataFrame(league_rows)
else:
    by_league = pd.DataFrame()

# Sécurisation
summary["Taux_moy"] = pd.to_numeric(summary["Taux_moy"], errors="coerce").round(1)
summary["IC_moy"] = pd.to_numeric(summary["IC_moy"], errors="coerce").round(1)
if not by_league.empty:
    by_league["Taux_moy"] = pd.to_numeric(by_league["Taux_moy"], errors="coerce").round(1)
    by_league["IC_moy"] = pd.to_numeric(by_league["IC_moy"], errors="coerce").round(1)





# Best threshold per type
def best_threshold(subdf):
    """
    Détermine le meilleur seuil d'IC pour un type donné :
      - Cherche un bon équilibre entre taux de réussite et volume
      - Volume minimal : 15 % du total
    """
    best_thr, best_rate, best_vol = None, 0, 0
    total = len(subdf)
    global_rate = subdf["won"].eq(True).mean() * 100 if "won" in subdf else np.nan

    for thr in np.arange(60, 96, 1):  # pas de 1 % pour plus de précision
        filt = subdf[subdf["IC"] >= thr]
        if len(filt) < 0.15 * total:  # au moins 15 % du volume
            continue

        # taux de réussite réel (basé sur les matchs gagnés)
        wins = filt["won"].eq(True).sum()
        rate = (wins / len(filt) * 100) if len(filt) > 0 else 0

        # on privilégie la stabilité : gain de réussite min. 0.5 % au-dessus du global
        if rate >= global_rate + 0.5 and rate > best_rate:
            best_rate, best_thr, best_vol = rate, thr, len(filt)

    # Si rien trouvé, on prend la meilleure réussite globale (fallback)
    if best_thr is None and total > 0:
        best_thr = 70
        best_rate = global_rate
        best_vol = total

    return pd.Series({
        "Type": subdf["Type"].iloc[0],
        "Seuil_optimal": round(best_thr, 1),
        "Taux_au_seuil": round(best_rate, 1),
        "Volume_seuil": int(best_vol)
    })


thr_df = df.groupby("Type", group_keys=False).apply(best_threshold).reset_index(drop=True)
summary = pd.merge(summary, thr_df, on="Type", how="left")

# ----------------------------------------------------------
# Sauvegarde automatique des seuils optimaux pour réutilisation
# ----------------------------------------------------------
SEUILS_PATH = os.path.join(BASE_DIR, "seuils_optimaux.csv")
try:
    seuils = summary[["Type", "Seuil_optimal"]].dropna()
    seuils["Seuil_optimal"] = seuils["Seuil_optimal"].round(1)
    seuils.to_csv(SEUILS_PATH, index=False, encoding="utf-8-sig")
    print(f"💾 Seuils optimaux enregistrés → {SEUILS_PATH}")
except Exception as e:
    print(f"⚠️ Impossible d’enregistrer les seuils optimaux : {e}")


# Numeric formatting
summary["Taux_moy"] = pd.to_numeric(summary["Taux_moy"], errors="coerce").round(1)
summary["IC_moy"] = pd.to_numeric(summary["IC_moy"], errors="coerce").round(1)

# --- Par Ligue : vrai taux de réussite + IC moyen gagnant ---
if "Ligue" in df.columns:
    league_rows = []
    for (t, lig), g in df.groupby(["Type", "Ligue"]):
        total = g["won"].notna().sum()
        wins = g["won"].eq(True).sum()
        taux = round((wins / total * 100), 1) if total > 0 else np.nan
        ic_mean = round(g.loc[g["won"] == True, "IC_val"].mean(), 1)
        league_rows.append({
            "Type": t,
            "Ligue": lig,
            "Matchs": total,
            "Taux_moy": taux,
            "IC_moy": ic_mean
        })
    by_league = pd.DataFrame(league_rows)
else:
    by_league = pd.DataFrame()



# ----------------------------------------------------------
# 3 bis) Distribution des taux de réussite par fourchette d'IC
# ----------------------------------------------------------

def ic_range(v):
    """Retourne la fourchette d'IC (60–70, 70–80, etc.)"""
    try:
        val = float(v)
        if val < 60: return "<60"
        elif val < 70: return "60–70"
        elif val < 80: return "70–80"
        elif val < 90: return "80–90"
        elif val <= 100: return "90–100"
    except:
        return None

df["IC_bucket"] = df["IC_val"].apply(ic_range)

dist_rows = []
for t, g in df[df["won"].notna()].groupby("Type"):
    total = len(g)
    taux_global = round(g["won"].eq(True).mean() * 100, 1)
    for bucket, sub in g.groupby("IC_bucket"):
        if bucket is None:
            continue
        wins = sub["won"].eq(True).sum()
        nb = len(sub)
        rate = round(wins / nb * 100, 1) if nb > 0 else np.nan
        dist_rows.append({
            "Type": t,
            "Fourchette IC": bucket,
            "Matchs": nb,
            "Taux_reussite": rate,
            "Part_du_total (%)": round(nb / total * 100, 1)
        })

dist_df = pd.DataFrame(dist_rows)

# ----------------------------------------------------------
# Zone la plus rentable par type (pondérée volume + réussite)
# ----------------------------------------------------------
rentable_rows = []

for t, g in dist_df.groupby("Type"):
    if g.empty:
        continue
    g = g[g["Taux_reussite"].notna()]
    # on ne garde que les zones significatives
    g = g[(g["Matchs"] >= 25) | (g["Part_du_total (%)"] >= 10)]
    # on calcule un score composite (pondéré volume + réussite)
    g["score"] = (g["Taux_reussite"] * 0.7) + (g["Part_du_total (%)"] * 0.3)
    best = g.loc[g["score"].idxmax()]
    rentable_rows.append({
        "Type": t,
        "Zone": best["Fourchette IC"],
        "Volume (%)": best["Part_du_total (%)"],
        "Matchs": best["Matchs"],
        "Taux_reussite (%)": best["Taux_reussite"]
    })

rentable_df = pd.DataFrame(rentable_rows)


# ----------------------------------------------------------
# Analyse automatique des zones de calibration par Type (version robuste 2)
# ----------------------------------------------------------
notes_auto = []

for t, g in dist_df.groupby("Type"):
    if g.empty:
        continue

    total = g["Matchs"].sum()

    # 1️⃣ On garde uniquement les zones significatives
    g_valid = g[(g["Matchs"] >= 25) | (g["Part_du_total (%)"] >= 10)]

    if g_valid.empty:
        g_valid = g

    # 2️⃣ On cherche les zones à très haute réussite (≥ 90%)
    high_perf = g_valid[g_valid["Taux_reussite"] >= 90]

    # 3️⃣ Sinon fallback à ≥ 85%
    if high_perf.empty:
        high_perf = g_valid[g_valid["Taux_reussite"] >= 85]

    # 4️⃣ Si aucune zone > 85%, on prend la meilleure globale
    if not high_perf.empty:
        # parmi celles valides, on privilégie le plus de volume
        best_row = high_perf.loc[high_perf["Matchs"].idxmax()]
    else:
        best_row = g_valid.loc[g_valid["Taux_reussite"].idxmax()]

    bucket = best_row["Fourchette IC"]
    rate = best_row["Taux_reussite"]
    volume = int(best_row["Matchs"])
    part = best_row["Part_du_total (%)"]

    # Avertissement échantillon trop petit
    warn = ""
    if volume < 25:
        warn = " <i>(⚠️ échantillon faible)</i>"

    notes_auto.append(
        f"<div class='note'>📈 <b>{t}</b> → Zone la plus rentable : "
        f"<b>{bucket}%</b> ({part}% du volume, "
        f"{rate}% de réussite sur {volume} pronos).{warn}</div>"
    )

auto_summary_html = "<br>".join(notes_auto)



# --- Tableau des distributions par fourchette d'IC (HTML)
if not dist_df.empty:
    tab_dist = dist_df.rename(columns={
        "Fourchette IC": "IC (%)",
        "Taux_reussite": "Taux de réussite (%)",
        "Part_du_total (%)": "Part du total (%)"
    }).to_html(index=False, classes="dataframe table", border=0, justify="center")
else:
    tab_dist = "<p class='note'>Aucune distribution disponible.</p>"


# ----------------------------------------------------------
# Calibration automatique — met à jour les facteurs IC
# ----------------------------------------------------------
calib_path = os.path.join(BASE_DIR, "calibration_auto.json")

try:
    calib_rows = {}
    for _, row in summary.iterrows():
        t = row["Type"].lower()
        taux = row["Taux_moy"]
        ic = row["IC_moy"]
        if pd.notna(taux) and pd.notna(ic) and ic > 0:
            k = round(taux / ic, 3)
            calib_rows[t] = k

    # Enregistre les multiplicateurs dans un fichier léger
    with open(calib_path, "w", encoding="utf-8") as f:
        json.dump(calib_rows, f, indent=2, ensure_ascii=False)
    print(f"✅ Calibration mise à jour ({len(calib_rows)} types) → calibration_auto.json")
except Exception as e:
    print(f"⚠️ Erreur calibration automatique : {e}")


# ----------------------------------------------------------
# 4) HTML render
# ----------------------------------------------------------
mean_global = round(pd.to_numeric(df.get("taux_global"), errors="coerce").dropna().mean(), 1) if "taux_global" in df.columns else float("nan")
signaux_total = len(df)
taux_actuel = round(pd.to_numeric(summary["Taux_moy"], errors="coerce").dropna().mean(), 1) if not summary.empty else 0.0
taux_optimal = taux_actuel
if "Taux_au_seuil" in summary.columns:
    _tmp = pd.to_numeric(summary["Taux_au_seuil"], errors="coerce").dropna()
    if not _tmp.empty:
        taux_optimal = round(_tmp.mean(), 1)

# Note finale sécurisée
try:
    if not summary.empty and pd.to_numeric(summary["Taux_moy"], errors="coerce").notna().any():
        best_type = summary.loc[summary["Taux_moy"].idxmax(), "Type"]
        best_val = summary["Taux_moy"].max()
        note = f"<div class='note'>🔎 <b>Analyse pertinente :</b> Sur la période, le type <b>{best_type}</b> affiche le meilleur taux de réussite moyen (<b>{best_val:.1f}%</b>).</div>"
    else:
        note = "<div class='note'>ℹ️ Aucune donnée exploitable pour déterminer le meilleur type de pari.</div>"
except Exception as e:
    note = f"<div class='note'>⚠️ Erreur dans le calcul de la note finale — {e}</div>"

STYLE = """
<style>
body {font-family:'Segoe UI',system-ui,Arial,sans-serif;background:#f8fbff;color:#223; margin:0;padding:20px}
h1,h2 {color:#0e4c92;text-align:center;margin:8px 0}
.panel {background:#fff;border-radius:12px;box-shadow:0 6px 18px rgba(0,0,0,.06);padding:16px;max-width:1200px;margin:14px auto}
.kpi {display:flex;gap:12px;justify-content:center;flex-wrap:wrap;margin:8px 0 16px}
.kpi .card {background:#0e4c92;color:#fff;border-radius:12px;padding:10px 14px;min-width:180px;text-align:center}
.kpi .card .v {font-weight:700;font-size:1.15rem}
table {width:100%;border-collapse:collapse;background:#fff;border-radius:8px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,.05);margin-top:10px}
th,td {padding:8px 10px;text-align:center;border-bottom:1px solid #e8eef7}
th {background:#eaf1ff;color:#19407a;font-weight:600;cursor:pointer;position:sticky;top:0;z-index:2}
th.sortable:hover {background:#dce6ff;cursor:pointer}
th.sortable::after {content:' ⇅';font-size:0.8em;color:#888;}
tr:nth-child(even) {background:#f9fbff}
.filters {display:flex;gap:8px;flex-wrap:wrap;justify-content:center;margin:8px 0 12px}
button.filter {background:#0e4c92;color:#fff;border:none;padding:8px 12px;border-radius:8px;cursor:pointer}
button.filter.active {background:#2ecc71}
.small {font-size:.92em;color:#666;text-align:center;margin-top:6px}
.barbox {max-width:500px;margin:10px auto;background:#eef4ff;border-radius:10px;padding:10px}
.bar {height:24px;border-radius:8px;text-align:right;color:#fff;font-weight:700;padding-right:6px;margin:6px 0}
.bar.current {background:#3498db}
.bar.sim {background:#2ecc71}
.note {font-style:italic;color:#555;text-align:center}
</style>

<script>
document.addEventListener('DOMContentLoaded', function() {
  document.querySelectorAll('table').forEach(function(table) {
    table.querySelectorAll('th').forEach(function(header, index) {
      header.classList.add('sortable');
      header.addEventListener('click', function() {
        const tbody = table.tBodies[0];
        const rows = Array.from(tbody.querySelectorAll('tr'));
        const asc = !header.classList.contains('asc');
        table.querySelectorAll('th').forEach(th => th.classList.remove('asc','desc'));
        header.classList.toggle('asc', asc);
        header.classList.toggle('desc', !asc);
        rows.sort((a, b) => {
          const A = a.cells[index].innerText.replace('%','').trim();
          const B = b.cells[index].innerText.replace('%','').trim();
          const numA = parseFloat(A); const numB = parseFloat(B);
          if (!isNaN(numA) && !isNaN(numB))
            return asc ? numA - numB : numB - numA;
          return asc ? A.localeCompare(B) : B.localeCompare(A);
        });
        rows.forEach(row => tbody.appendChild(row));
      });
    });
  });
});
</script>
"""



def df_to_html_table(df, rename_map, table_id):
    if df.empty:
        return "<p class='note'>Aucune donnée disponible.</p>"
    return df.rename(columns=rename_map).to_html(index=False, classes="dataframe table", border=0, justify="center", table_id=table_id)

tab_summary = df_to_html_table(
    summary,
    {
        "Taux_moy": "Taux de réussite (%)",
        "IC_moy": "IC moyen (%)",
        "Seuil_optimal": "Seuil optimal (%)",
        "Taux_au_seuil": "Taux au-dessus du seuil (%)",
        "Volume_seuil": "Volume au-dessus du seuil"
    },
    "tbl_summary"
)

if not by_league.empty:
    tab_league = df_to_html_table(
        by_league,
        {
            "Taux_moy": "Taux de réussite (%)",
            "IC_moy": "IC moyen (%)"
        },
        "tbl_per_league"
    )
else:
    tab_league = "<p class='note'>Aucune donnée par ligue disponible.</p>"

bar_html = f"""
<div class='barbox'>
  <div class='bar current' style='width:{taux_actuel}%'>{taux_actuel}%</div>
  <div class='bar sim' style='width:{taux_optimal}%'>{taux_optimal}%</div>
  <div class='small'>Bleu = taux actuel (tous signaux scorés) · Vert = si on filtre par seuil optimal de proba pour chaque type</div>
</div>
"""

html = f"""<!doctype html>
<html><head><meta charset="utf-8"><title>Analyse globale FootBot</title>{STYLE}</head>
<body>
  <div class="panel">
    <h1>Analyse globale FootBot</h1>
    <h2>{periode}</h2>
    <div class='kpi'>
      <div class='card'><div>Période</div><div class='v'>{periode}</div></div>
      <div class='card'><div>Taux global moyen (rapports)</div><div class='v'>{"" if pd.isna(mean_global) else str(mean_global)+'%'} </div></div>
      <div class='card'><div>Signaux évalués</div><div class='v'>{signaux_total:,}</div></div>
    </div>
  </div>

    <div class="panel">
    <h2>1) Résumé par type (comptes, réussite, IC moyen, seuil optimal)</h2>
    <div class="note">Le "Seuil optimal" est la probabilité minimale (IC) qui maximise la réussite, avec ≥ 10 signaux au-dessus du seuil.</div>
    {tab_summary}

    <div class="panel">
      <h2>Simulation — si on appliquait les seuils optimaux</h2>
      {bar_html}
    </div>

    <div class="panel">
      <h2>Répartition des réussites par fourchette d’IC</h2>
      {tab_dist}
      {auto_summary_html}
    </div>

    <div class="small">Astuce : clique sur les en-têtes pour trier (ex: "Taux de réussite (%)").</div>
  </div>


    <div class="small">Astuce: clique sur les en-têtes pour trier (ex: "Taux de réussite (%)").</div>
  </div>

  <div class="panel">
    <h2>2) Taux de réussite par Type × Ligue</h2>
    {tab_league}
  </div>

  
</body></html>"""

with open(OUT_HTML, "w", encoding="utf-8") as f:
    f.write(html)

print(f"✅ Rapport HTML généré → {OUT_HTML}")
