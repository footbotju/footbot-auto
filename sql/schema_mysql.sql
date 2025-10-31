CREATE DATABASE IF NOT EXISTS FootballStats CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE FootballStats;

CREATE TABLE IF NOT EXISTS fixtures (
  fixture_id VARCHAR(32) PRIMARY KEY,
  league_name VARCHAR(255),
  country VARCHAR(255),
  home_team VARCHAR(255),
  away_team VARCHAR(255),
  date_match DATETIME,
  cote_home FLOAT,
  cote_draw FLOAT,
  cote_away FLOAT,
  xg_home FLOAT,
  xg_away FLOAT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS signals (
  fixture_id VARCHAR(32) PRIMARY KEY,
  p_home_win FLOAT,
  p_draw FLOAT,
  p_away_win FLOAT,
  score_final_home FLOAT,
  EV_home FLOAT,
  IC VARCHAR(32),
  signal VARCHAR(8),
  p_over_1_5 FLOAT,
  suggest_over_1_5 VARCHAR(32),
  p_over_2_5 FLOAT,
  suggest_over_2_5 VARCHAR(32),
  p_BTTS FLOAT,
  suggest_BTTS VARCHAR(32),
  corroboration_votes INT,
  notes VARCHAR(255),
  run_ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
