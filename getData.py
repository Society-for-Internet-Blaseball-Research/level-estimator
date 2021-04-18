from blaseball_mike import chronicler, models
from datetime import timedelta
import json


# These aren't needed, but I took the time to find them, so I'm leaving them here
S14_START = "2021-03-15T15:00:01.003898Z"
S15_START = "2021-04-05T15:00:08.011462Z"
S16_START = "2021-04-12T15:00:01.002578Z"

# Controls which current chronicler time map phases are valid game days
# They don't look right currently because phases got hecked in season 12
normal_phases = ["season", "postseason", "pre_election", "bossfight"]

# Controls which season to start data collection from, 0-indexed
START_SEASON = 14

# Raw data storage, indexed by season then day
data = {}

# Fetch chroniclers time map and fill out the data dict with start-times and placeholders
time_map = chronicler.v1.time_map()
for time in time_map:
    if(time["season"] >= START_SEASON and time["type"] in normal_phases):
        if(time["season"] not in data):
            data[time["season"]] = {}
        data[time["season"]][time["day"]] = {"start": time["startTime"], "data": None}

# Iterate over season then day
for season, season_data in data.items():
    # Use blaseball mike to grab the standings ID for that season
    standings_id = models.Season.load(int(season) + 1).standings.id
    for day, day_data in season_data.items():
        # sometimes we get duplicate days, only take the first one, maybe this is an error
        if(day_data["data"] is None):
            print("data empty for season/day, fetching...", season, day)

            # Add 5 minutes to the start of day to make sure eDensity has updated
            adjusted_date = day_data["start"] + timedelta(minutes=5)

            # Convert to string for chron fetch and json storage
            day_data["start"] = day_data["start"].strftime('%Y-%m-%dT%H:%M:%S.%fZ')

            # Fetch team data, standings, and idols for that day.
            raw_team_data = chronicler.v2.get_entities("team", at=adjusted_date)
            standings = chronicler.v2.get_entities("standings", id_=standings_id, at=adjusted_date)
            idols = list(chronicler.v2.get_entities("idols", at=adjusted_date))[0]["data"]
            standings = list(standings)[0]["data"]

            # A hack to only get current teams
            teams = [team["data"] for team in raw_team_data if team["data"].get("stadium")]

            # Now we reduce the data to only the fields we need for each day.
            reduced_data = {}
            for team in teams:
                reduced_data[team["id"]] = {"eDensity": team["eDensity"], "level": team["level"],
                                            "wins": standings["wins"][team["id"]],
                                            "runs": standings["runs"][team["id"]],
                                            "sc": idols["data"]["strictlyConfidential"]}
            day_data["data"] = reduced_data

# Dump the raw data for future hopes of not having to fetch each time
with open('data.json', 'w') as outfile:
    json.dump(data, outfile)

# Fetch teams one last time for iteration purposes
raw_team_data = chronicler.v2.get_entities("team")
teams = [team["data"] for team in raw_team_data if team["data"].get("stadium")]

# Calculation data storage, indexed by team rather than season/day
calc_data = {}

# Set some initial values. Not really accurate to set this like this for all teams, but
#     initial values fade away quickly enough
# s: season
# d: day
# lv: level
# ed: eDensity
# ip: imposition
# ev: eVelociy
# np: noodlePosition
# nv: noodleVelocity
# sc: strictlyConfidential
for team in teams:
    calc_data[team["id"]] = [{"s": 0, "d": 0, "lv": 0, "ed": 0, "ip": -0.2850013115, "ev": -0.004151105971, "np": -0.1346, "nv": 0.3, "sc": 8}]

# Reserved for future hopes and dreams of calculating level transition values.
# transitions = [0, 0, 0, 0, 0, 0, 0, 0, 0]

# Iterate over season then day then team
for season, season_data in data.items():
    for day, day_data in season_data.items():
        for team in teams:
            # do the agreed upon imPosition calculations
            prev = calc_data[team["id"]][-1]
            ed = day_data["data"][team["id"]]["eDensity"]
            lv = day_data["data"][team["id"]]["level"]
            sc = day_data["data"][team["id"]]["sc"]
            nv = 0.55 * (prev["nv"] - prev["np"] + (sc - 8) / 10)
            np = prev["np"] + nv
            ev = 0.55 * (prev["ev"] - prev["ip"] - 0.0005 * ed - 0.0388 * sc + 0.9992)
            ip = prev["ip"] + ev
            data_point = {"s": season, "d": day, "ed": ed, "lv": lv, "sc": sc, "ev": ev, "ip": ip, "np": np, "nv": nv}
            calc_data[team["id"]].append(data_point)

# Strip all intermediate data and just output label, imposition, and level.
output_data = {}
for team in teams:
    team_data = calc_data[team["id"]][1:]
    output_data[team["id"]] = {"label": [str(int(p["s"])+1) + "-" + str(int(p["d"])+1) for p in team_data],
                               "ip": [p["ip"] + p["np"] for p in team_data],
                               "level": [p["lv"] for p in team_data]}


with open('output.json', 'w') as outfile:
    json.dump(output_data, outfile)
