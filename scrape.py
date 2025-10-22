import asyncio
import aiohttp
from bs4 import BeautifulSoup
import json
import re
from dotenv import load_dotenv
from ollama import Client

load_dotenv()

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/128.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

client = Client()


# ======================================================
# HELPER: Fetch page text asynchronously
# ======================================================
async def fetch(session, url):
    async with session.get(url) as response:
        if response.status != 200:
            print(f"⚠️ Error fetching {url}: {response.status}")
            return None
        return await response.text()


# ======================================================
# GET TODAY'S MATCHES
# ======================================================
async def get_today_matches(session):
    url = "https://www.livescore.bz/en/"
    html = await fetch(session, url)
    if not html:
        return []

    soup = BeautifulSoup(html, "html.parser")
    match_tags = soup.find_all("a", class_=["m meven", "m modd"])

    matches = []
    for tag in match_tags:
        match_id = tag.get("mid")
        home_team = tag.find("t1").get_text(strip=True)
        away_team = tag.find("t2").get_text(strip=True)
        start_time = tag.get("start-time")

        matches.append({
            "match_id": match_id,
            "team": {"home": home_team, "away": away_team},
            "start-time": start_time,
        })

    print(f"✅ Found {len(matches)} matches today.")
    return matches


# ======================================================
# LEAGUE NAME
# ======================================================
async def get_league_name(session, match_id):
    url = f"https://www.livescore.bz/en/football/event/{match_id}/"
    html = await fetch(session, url)
    if not html:
        return "Unknown League"
    soup = BeautifulSoup(html, "html.parser")
    header = soup.find("div", class_="detayHeader aic")
    return header.text.strip() if header else "Unknown League"


# ======================================================
# TEAM LAST MATCHES
# ======================================================
async def get_team_last_matches(session, match_id, class_name):
    url = f"https://www.livescore.bz/last_matches_2018.cache?id={match_id}&filter=overall&team=all&lang=en"
    html = await fetch(session, url)
    if not html:
        return {}

    soup = BeautifulSoup(html, "html.parser")
    find_element = soup.find("div", class_=class_name)
    if not find_element:
        return {}

    home_team_name = find_element.find("th", class_="lm_h1").find_all("span")[0].text
    rows = find_element.find_all("tr", class_=["sm_m sm_sncL", "sm_m sm_sncW", "sm_m sm_sncD"])

    matches = []
    for row in rows:
        cols = row.find_all("td")
        if len(cols) < 5:
            continue
        matches.append({
            "date": cols[0].text.strip(),
            "home": cols[1].text.strip(),
            "score": cols[2].text.strip(),
            "away": cols[3].text.strip(),
            "half_score": cols[4].text.strip(),
        })

    return {
        "match_id": match_id,
        "team_name": home_team_name,
        "matches": matches,
    }


# ======================================================
# HEAD TO HEAD
# ======================================================
async def get_head_to_head(session, match_id):
    url = f"https://www.livescore.bz/h2h_2018.cache?id={match_id}&filter=overall&team=all&lang=en"
    html = await fetch(session, url)
    if not html:
        return []
    soup = BeautifulSoup(html, "html.parser")

    rows = soup.find_all("tr", class_="sm_m")
    h2h_matches = []
    for row in rows:
        cols = row.find_all("td")
        if len(cols) < 5:
            continue
        h2h_matches.append({
            "date": cols[0].text.strip(),
            "home": cols[1].text.strip(),
            "score": cols[2].text.strip(),
            "away": cols[3].text.strip(),
            "half_score": cols[4].text.strip(),
        })
    return h2h_matches


# ======================================================
# LEAGUE TABLE
# ======================================================
def extract_stdata(html):
    pattern = r"var stdata\s*=\s*(\{.*?\});?\s*function"
    match = re.search(pattern, html, re.DOTALL)
    if match:
        return json.loads(match.group(1))
    return {}


async def get_league_table(session, match_id):
    url = f"https://www.livescore.bz/standings_2020.cache?lang=en&id={match_id}&filter="
    html = await fetch(session, url)
    if not html:
        return {}
    try:
        return extract_stdata(html)
    except Exception:
        return {}


# ======================================================
# COMBINE ALL DATA PER MATCH
# ======================================================
async def process_match(session, match):
    match_id = match["match_id"]

    # Run all fetches concurrently for this match
    league_name, home_matches, away_matches, h2h, table = await asyncio.gather(
        get_league_name(session, match_id),
        get_team_last_matches(session, match_id, "lm_home"),
        get_team_last_matches(session, match_id, "lm_away"),
        get_head_to_head(session, match_id),
        get_league_table(session, match_id),
    )

    return {
        "match_id": match_id,
        "league_name": league_name,
        "home_team_last_matches": home_matches,
        "away_team_last_matches": away_matches,
        "team_head_to_head": h2h,
        "team_standings": table,
    }


# ======================================================
# MAIN FUNCTION
# ======================================================
async def get_clean_todays_matches_data():
    async with aiohttp.ClientSession(headers=HEADERS) as session:
        matches = await get_today_matches(session)
        if not matches:
            print("❌ No matches found.")
            return []

        print("⚙️ Fetching all match data concurrently...")
        tasks = [process_match(session, m) for m in matches]
        results = await asyncio.gather(*tasks)

        print(f"✅ Finished processing {len(results)} matches.")
        return results


def cleaned_match_data():
    matches = asyncio.run(get_clean_todays_matches_data())
    
    cleaned_match_data = []
    for match in matches:
        if not match['team_standings']['overall']['tables']:
            continue
        table = match['team_standings']['overall']['tables'][0]['data']
        match['team_standings'] = table
        cleaned_match_data.append(match)
    return cleaned_match_data
