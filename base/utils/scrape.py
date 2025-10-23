import asyncio
import aiohttp
from bs4 import BeautifulSoup
import json
import re
from dotenv import load_dotenv
from ollama import Client
from ollama import chat, ChatResponse
from base.models import MatchData
from django.utils import timezone
import datetime
from google import genai


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
client = genai.Client()



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
            "start_time": start_time,
        })

    # print(f"✅ Found {len(matches)} matches today.")
    return matches


async def get_start_time(session, match_id):
    matches = await get_today_matches(session)

    match_start_time = None

    for match in matches:
        id = match['match_id']
        if id == match_id:
            start_time = int(match['start_time'])
            time_str = datetime.datetime.fromtimestamp(start_time).strftime("%Y-%m-%d %H:%M").split(' ')[1]
            match_start_time = time_str
            break
    return match_start_time

    


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
    start_time, league_name, home_matches, away_matches, h2h, table = await asyncio.gather(
        get_start_time(session, match_id),
        get_league_name(session, match_id),
        get_team_last_matches(session, match_id, "lm_home"),
        get_team_last_matches(session, match_id, "lm_away"),
        get_head_to_head(session, match_id),
        get_league_table(session, match_id),
    )

    return {
        "match_id": match_id,
        'start_time' : start_time,
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


def save_match_to_db():
    matches = cleaned_match_data()
    db_matches = MatchData.objects.all()

    db_matches.delete()

    for match in matches:
        id = match['match_id']
        # start_time = match[]
        MatchData.objects.create(
            match_id=match['match_id'],
            data=match,
            created_at=datetime.datetime.now()
        )
    print('data loaded successfully')










# def batch_process(data, batch_size):
#     for i in range(0, len(data), batch_size):
#         yield data[i:i + batch_size]


# def generate_predictions(batch_size=5):
#     matches = get_clean_todays_matches_data()
#     print(f"Total matches found: {len(matches)}")

#     final_match_data = []

#     if not matches:
#         print("No match data available")
#         return final_match_data

#     # Process matches in batches
#     for batch_num, match_batch in enumerate(batch_process(matches, batch_size), start=1):
#         print(f"\nProcessing batch {batch_num} ({len(match_batch)} matches)")

#         for match in match_batch:
#             content = f"""
#             You are a football match prediction assistant.
#             Use this {match} data to predict the likely outcome of the match.

#             Your prediction should be one of the following formats:

#             Home win
#             Away win
#             Home win or draw
#             Away win or draw
#             Over or under X goals

#             Score your prediction out of 100 

#             Share insights explaining the reasoning.

#             Your insights should talk about the following topics in detail:
#             - Both teams’ recent matches
#             - Both teams’ recent forms
#             - Both teams’ head-to-head matches

#             Rules:
#             Go straight to the prediction — do NOT start with phrases like “Based on the data” or similar introductions.
#             Respond in plain text only (no Markdown, no bullet formatting).
#             Keep the entire response concise and structured like this:

#             Prediction: [your prediction]
#             Confidence Score: [score]/100
#             Insights:
#             """

#             # ChatResponse = chat(model='qwen3:1.7b', messages=[
#             #     {'role': 'user', 'content': content}
#             # ])
#             messages = [
#             {
#                 'role': 'user',
#                 'content': content,
#             },
#             ]
#             response = client.chat('gpt-oss:120b-cloud', messages=messages)
#             match['ai_insight'] = response['message']['content']
#             final_match_data.append(match)
#             print(match)
#             print(f"✅ Processed match: {match.get('id', 'unknown')}")

#     print(f"\nAll batches completed. Total predictions generated: {len(final_match_data)}")
#     return final_match_data

def generate_prediction(match):
    content = f"""
    You are a football match prediction assistant.
    Use this {match} data to predict the likely outcome of the match.

    Your prediction must be in one of these formats:

    Home win

    Away win

    Home win or draw

    Away win or draw

    Over or under X goals

    Assign a confidence score out of 100.

    Then provide clear, insightful reasoning behind the prediction.

    Tone & Style Guidelines:

    Write in a balanced tone — part sports journalist, part data analyst.

    Keep the writing natural, engaging, and factual.

    Avoid robotic phrasing and generic introductions like “Based on the data.”

    Write in plain text only (no markdown, no bullet points).

    Use short clear section headings in uppercase.

    The response should feel like a match preview written by an expert analyst.

    Response Structure Example:

    Prediction: Away win or draw
    Confidence Score: 75/100

    INSIGHTS:
    RECENT MATCHES: Watford’s form has been inconsistent, mixing solid wins with disappointing defeats. West Brom, meanwhile, look sharper, recording victories over Preston and Norwich City while holding Leicester to a draw. The visitors appear more composed and confident in recent weeks.

    RECENT FORM: Watford’s tendency to alternate between wins and losses shows a team still searching for rhythm. West Brom have displayed greater stability, balancing attack and defense effectively, which often makes the difference in tight fixtures.

    HEAD-TO-HEAD: Encounters between these sides have historically been close, but West Brom have edged the recent meetings, winning two of the last three. That momentum gives them a psychological advantage heading into this clash.

    SUMMARY: Watford’s home support could play a role, but West Brom’s current consistency and recent dominance suggest they are more likely to avoid defeat. An away win or draw looks the sensible prediction.

    
    """

    response = client.models.generate_content(
    model="gemini-2.5-flash-lite", contents=content
    )
    # response: ChatResponse = chat(model='llama3.2:1b', messages=[
    #     {'role': 'user', 'content': content}
    # ])
    # messages = [
    # {
    #     'role': 'user',
    #     'content': content,
    # },
    # ]
    # response = client.chat('gpt-oss:120b-cloud', messages=messages)
    # ai_insight = response['message']['content']
    ai_insight = response.text
    return ai_insight