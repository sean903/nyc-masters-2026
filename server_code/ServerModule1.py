import anvil.server
import requests
from bs4 import BeautifulSoup
import pandas as pd
import json
import unicodedata


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

  if raw == "E":
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
    return 999.0

  if raw in {"WD", "DQ"}:
    return 999.0

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
  script_tag = soup.find("script", {"id": "leaderboard-seo-data"})

  if not script_tag or not script_tag.string:
    raise ValueError("Could not find leaderboard JSON")

  leader_json = json.loads(script_tag.string)
  columns = leader_json["mainEntity"]["csvw:tableSchema"]["csvw:columns"]

  data = []
  for i in range(8):
    data.append([item["csvw:value"] for item in columns[i]["csvw:cells"]])

  leaderboard = pd.DataFrame(data).transpose()
  leaderboard.columns = [
    "position",
    "name",
    "current_score_raw",
    "hole",
    "round_1",
    "round_2",
    "round_3",
    "round_4",
  ]

  leaderboard["canonical_name"] = leaderboard["name"].apply(canonical_name)
  leaderboard["current_score"] = leaderboard.apply(parse_player_score, axis=1)

  return leaderboard


def score_one_person(leaderboard, person, picks):
  total = 0.0
  out = {"person": person}

  for i, player in enumerate(picks, start=1):
    key = canonical_name(player)
    match = leaderboard[leaderboard["canonical_name"] == key]

    if match.empty:
      score = 999.0
    else:
      score = match.iloc[0]["current_score"]

    total += score
    out[f"player_{i}"] = player
    out[f"score_{i}"] = score

  out["avg_score"] = total / 6.0
  return out


@anvil.server.callable
def get_person_leaderboard():
  leaderboard = get_raw_leaderboard()
  rows = []

  for person, picks in PICKS.items():
    rows.append(score_one_person(leaderboard, person, picks))

  rows = sorted(rows, key=lambda x: x["avg_score"])
  return rows