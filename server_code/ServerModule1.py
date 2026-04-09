import anvil.server
from anvil.tables import app_tables

import requests
from bs4 import BeautifulSoup
import pandas as pd
import json
import logging
import unicodedata


logging.basicConfig(level=logging.INFO)


PICKS = {
  "James": ["Tommy Fleetwood", "Brooks Koepka", "Rasmus Højgaard", "Brian Harman", "Andrew Novak", "Jose Maria Olazabal"],
  "Abs": ["Patrick Reed", "Justin Thomas", "Cameron Smith", "Ryan Fox", "Michael Kim", "Vijay Singh"],
  "Joe": ["Cameron Young", "Jake Knapp", "J.J. Spaun", "Kristoffer Reitan", "Haotong Li", "Danny Willett"],
  "Lew": ["Matt Fitzpatrick", "Akshay Bhatia", "Gary Woodland", "Sam Stevens", "Charl Schwartzel", "Davis Riley"],
  "Jack H": ["Collin Morikawa", "Russell Henley", "Sungjae Im", "Aaron Rai", "Sami Valimaki", "Zach Johnson"],
  "Mark": ["Min Woo Lee", "Viktor Hovland", "Ben Griffin", "Wyndham Clark", "Rasmus Neergaard-Petersen", "Brian Campbell"],
  "Tom D": ["Ludvig Åberg", "Nicolai Højgaard", "Tyrrell Hatton", "Keegan Bradley", "Matt McCarty", "Brandon Holtz"],
  "Jack D": ["Jon Rahm", "Shane Lowry", "Daniel Berger", "Dustin Johnson", "John Keefer", "Fifa Laopakdee"],
  "Aidan": ["Hideki Matsuyama", "Adam Scott", "Sam Burns", "Max Homa", "Nick Taylor", "Mason Howell"],
  "Cam": ["Rory McIlroy", "Maverick McNealy", "Harris English", "Alex Noren", "Bubba Watson", "Mateo Pulcini"],
  "Tom B": ["Xander Schauffele", "Patrick Cantlay", "Corey Conners", "Harry Hall", "Nicolas Echavarria", "Jackson Herrington"],
  "Aaron": ["Justin Rose", "Chris Gotterup", "Sepp Straka", "Casey Jarvis", "Carlos Ortiz", "Angel Cabrera"],
  "Sean": ["Scottie Scheffler", "Jordan Spieth", "Kurt Kitayama", "Sergio Garcia", "Michael Brennan", "Ethan Fang"],
  "Max": ["Bryson DeChambeau", "Jason Day", "Jacob Bridgeman", "Aldrich Potgieter", "Max Greyserman", "Fred Couples"],
  "Alex": ["Robert MacIntyre", "Si Woo Kim", "Marco Penge", "Ryan Gerard", "Tom McKibbin", "Naoyuki Kataoka"],
}


NAME_ALIASES = {
  "jj spaun": "jj spaun",
  "ludvig aberg": "ludvig aberg",
  "nicolai hojgaard": "nicolai hojgaard",
  "rasmus hojgaard": "rasmus hojgaard",
  "rasmus neergaard petersen": "rasmus neergaard petersen",
  "jose maria olazabal": "jose maria olazabal",
  "angel cabrera": "angel cabrera",
}


def normalize_name(name):
  if not name:
    return ""

  name = unicodedata.normalize("NFKD", str(name))
  name = "".join(ch for ch in name if not unicodedata.combining(ch))
  name = name.lower()
  name = name.replace(".", "")
  name = name.replace("-", " ")
  name = name.replace("'", "")
  name = " ".join(name.split())
  return name


def canonical_name(name):
  n = normalize_name(name)
  return NAME_ALIASES.get(n, n)


def safe_int(value):
  try:
    return int(str(value).strip())
  except Exception:
    return None


def parse_player_score(row):
  raw = str(row.get("current_score_raw", "")).strip().upper()

  if raw in {"E", "-", ""}:
    return 0.0

  try:
    return float(raw)
  except Exception:
    pass

  if raw in {"CUT", "MC"}:
    r1 = safe_int(row.get("round_1"))
    r2 = safe_int(row.get("round_2"))

    if r1 is not None and r2 is not None:
      return float((r1 - 72) + (r2 - 72))

    return 997.0

  if raw in {"WD", "DQ"}:
    return 998.0

  return 999.0


def get_raw_leaderboard():
  url = "https://www.pgatour.com/leaderboard"

  r = requests.get(
    url,
    timeout=20,
    headers={"User-Agent": "Mozilla/5.0"}
  )
  r.raise_for_status()

  soup = BeautifulSoup(r.content, "html.parser")

  # Find the JSON-LD script tag (no longer has a specific id)
  script_tag = None
  for tag in soup.find_all("script", {"type": "application/ld+json"}):
    if tag.string and "csvw:columns" in tag.string:
      script_tag = tag
      break

  if not script_tag or not script_tag.string:
    raise ValueError("Could not find leaderboard JSON")

  leader_json = json.loads(script_tag.string)
  columns = leader_json["mainEntity"]["csvw:tableSchema"]["csvw:columns"]

  col_names = [col.get("csvw:name", "") for col in columns]
  data = []
  for col in columns:
    data.append([item["csvw:value"] for item in col["csvw:cells"]])

  leaderboard = pd.DataFrame(data).transpose()
  leaderboard.columns = col_names

  # Map to consistent column names
  col_map = {
    "POS": "position",
    "PLAYER": "name",
    "TOT": "current_score_raw",
    "THRU": "hole",
    "R1": "round_1",
    "R2": "round_2",
    "R3": "round_3",
    "R4": "round_4",
  }
  leaderboard.rename(columns=col_map, inplace=True)

  for needed in ["position", "name", "current_score_raw", "round_1", "round_2"]:
    if needed not in leaderboard.columns:
      leaderboard[needed] = "-"

  leaderboard["canonical_name"] = leaderboard["name"].apply(canonical_name)
  leaderboard["current_score"] = leaderboard.apply(parse_player_score, axis=1)

  return leaderboard


def score_one_person(leaderboard, person, picks):
  player_rows = []
  total = 0.0

  for i, player in enumerate(picks, start=1):
    key = canonical_name(player)
    match = leaderboard[leaderboard["canonical_name"] == key]

    # Fallback: match on last name + first initial (handles "J. Keefer" vs "John Keefer")
    if match.empty and " " in key:
      last_name = key.split()[-1]
      first_initial = key[0]
      match = leaderboard[
        (leaderboard["canonical_name"].str.endswith(last_name)) &
        (leaderboard["canonical_name"].str.startswith(first_initial))
      ]

    if match.empty:
      actual_name = player
      score = 999.0
      found = False
    else:
      row = match.iloc[0]
      actual_name = row["name"]
      score = row["current_score"]
      found = True

    total += score
    player_rows.append({
      "slot": i,
      "pick_name": player,
      "matched_name": actual_name,
      "score": score,
      "found": found,
    })

  avg_score = total / 6.0

  out = {
    "person": person,
    "avg_score": avg_score,
  }

  for p in player_rows:
    i = p["slot"]
    out[f"player_{i}"] = p["pick_name"]
    out[f"matched_player_{i}"] = p["matched_name"]
    out[f"score_{i}"] = p["score"]
    out[f"found_{i}"] = p["found"]

  return out


def build_person_leaderboard():
  try:
    leaderboard = get_raw_leaderboard()
  except Exception as e:
    logging.warning("Could not fetch leaderboard: %s. Showing picks without scores.", e)
    leaderboard = pd.DataFrame(columns=["canonical_name", "name", "current_score"])

  rows = []

  for person, picks in PICKS.items():
    rows.append(score_one_person(leaderboard, person, picks))

  df = pd.DataFrame(rows).sort_values("avg_score").reset_index(drop=True)
  return df


@anvil.server.callable
def refresh_person_leaderboard():
  df = build_person_leaderboard()

  app_tables.person_leaderboard.delete_all_rows()

  for record in df.to_dict(orient="records"):
    app_tables.person_leaderboard.add_row(**record)

  logging.info("Loaded %s rows into person_leaderboard", len(df))
  return df.to_dict(orient="records")


@anvil.server.callable
def get_person_leaderboard():
  rows = app_tables.person_leaderboard.search()

  data = []
  for row in rows:
    data.append({
      "person": row["person"],
      "avg_score": row["avg_score"],
      "player_1": row["player_1"],
      "matched_player_1": row["matched_player_1"],
      "score_1": row["score_1"],
      "found_1": row["found_1"],
      "player_2": row["player_2"],
      "matched_player_2": row["matched_player_2"],
            "score_2": row["score_2"],
            "found_2": row["found_2"],
            "player_3": row["player_3"],
            "matched_player_3": row["matched_player_3"],
            "score_3": row["score_3"],
            "found_3": row["found_3"],
            "player_4": row["player_4"],
            "matched_player_4": row["matched_player_4"],
            "score_4": row["score_4"],
            "found_4": row["found_4"],
            "player_5": row["player_5"],
            "matched_player_5": row["matched_player_5"],
            "score_5": row["score_5"],
            "found_5": row["found_5"],
            "player_6": row["player_6"],
            "matched_player_6": row["matched_player_6"],
            "score_6": row["score_6"],
            "found_6": row["found_6"],
        })

    return sorted(data, key=lambda x: x["avg_score"])