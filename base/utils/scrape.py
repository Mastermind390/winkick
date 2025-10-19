from bs4 import BeautifulSoup
import requests
import time
import re, json
from google import genai
import os
from dotenv import load_dotenv
from ollama import chat
from ollama import ChatResponse
from ollama import Client

load_dotenv()

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/128.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}

client = Client()

def get_today_matches():

    soup = BeautifulSoup()

    tags = soup.find_all()

    url = 'https://www.livescore.bz/en/'

    page = requests.get(url, headers=headers).text

    soup = BeautifulSoup(page, 'html.parser')

    match_tags = soup.find_all('a', class_=['m meven', 'm modd'])

    matches = []

    for tag in match_tags:
        match_detail = {}
        element = tag
        match_id = element.get('mid')
        home_team = element.find('t1').get_text(strip=True)
        away_team = element.find('t2').get_text(strip=True)
        start_time = element.get('start-time')
        
        match_detail['match_id'] = match_id
        match_detail['team'] = {
            'home' : home_team,
            'away' : away_team,
        }
        match_detail['start-time'] = start_time
        matches.append(match_detail)
    return matches


def get_league_name(match_id):
    get_league_name_url = f'https://www.livescore.bz/en/football/event/{match_id}/'

    response = requests.get(get_league_name_url, headers=headers)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, 'html.parser')

    league_name = soup.find('div', class_='detayHeader aic').text

    return league_name



def get_team_last_matches(match_id, class_name):

    league_name = get_league_name(match_id)

    home_previous_match_url = f"https://www.livescore.bz/last_matches_2018.cache?id={match_id}&filter=overall&team=all&lang=en"
    
    home_previous_response = requests.get(home_previous_match_url, headers=headers)
    home_previous_response.raise_for_status()

    soup = BeautifulSoup(home_previous_response.text, 'html.parser')
    find_element = soup.find('div', class_ = f'{class_name}')
    home_team_name = find_element.find('th', class_ = 'lm_h1').find_all('span')[0].text
    home_team_previous_matches = find_element.find_all('tr', class_=['sm_m sm_sncL', 'sm_m sm_sncW', 'sm_m sm_sncD'])

    if not home_team_previous_matches:
        print("⚠️ No match details found.")
        return []

    list_of_match = []

    all_match_data = {}

    for row in home_team_previous_matches:
        cols = row.find_all('td')
        if len(cols) < 5:
            continue  # Skip malformed rows

        match_data = {
            'date': cols[0].text.strip(),
            'home': cols[1].text.strip(),
            'score': cols[2].text.strip(),
            'away': cols[3].text.strip(),
            'half_score': cols[4].text.strip(),
        }

        list_of_match.append({
            'match_id': match_id,
            'previous_match': match_data
        })
    all_match_data['match_id'] = match_id
    all_match_data['home_team_name'] = home_team_name
    all_match_data['league_name'] = league_name
    all_match_data['matches'] = list_of_match
    return all_match_data

home_team_last_matches = get_team_last_matches(2306790,'lm_home')
away_team_last_matches = get_team_last_matches(2306790,'lm_away')

# print('=============== home team matches ===================')
# print(home_team_last_matches)
# print('=============== away team matches ===================')
# print(away_team_last_matches)

def get_head_to_head(match_id):

    h2h_url = f'https://www.livescore.bz/h2h_2018.cache?id={match_id}&filter=overall&team=all&lang=en'
    h2h_response = requests.get(h2h_url, headers=headers)
    h2h_response.raise_for_status()

    h2h_soup = BeautifulSoup(h2h_response.text, 'html.parser')
    head_to_head_rows = h2h_soup.find_all('tr', class_ = 'sm_m')

    list_of_h2h = []
    for row in head_to_head_rows:
        cols = row.find_all('td')
        if len(cols) < 5:
            continue  # Skip malformed rows

        match_data = {
            'date': cols[0].text.strip(),
            'home': cols[1].text.strip(),
            'score': cols[2].text.strip(),
            'away': cols[3].text.strip(),
            'half_score': cols[4].text.strip(),
        }

        list_of_h2h.append({
            'match_id': match_id,
            'head_to_head': match_data
        })

    return list_of_h2h


def get_team_standings(match_id):
    url = f'https://www.livescore.bz/standings_2020.cache?lang=en&id={match_id}&filter='

    response = requests.get(url, headers=headers)
    response.raise_for_status()
    html = response.text
    
    return html


def extract_stdata(html_content):
    """
    Extract the stdata JavaScript variable from HTML content.
    
    Args:
        html_content (str): The HTML content containing the stdata variable
    
    Returns:
        dict: The parsed stdata as a Python dictionary
    """
    # Method 1: Using regex to find the stdata variable assignment
    pattern = r'var stdata\s*=\s*(\{.*?\});?\s*function'
    match = re.search(pattern, html_content, re.DOTALL)
    
    if match:
        json_str = match.group(1)
        # Parse the JSON string to a Python dictionary
        stdata = json.loads(json_str)
        return stdata
    else:
        raise ValueError("Could not find stdata variable in the HTML content")



def extract_stdata_alternative(html_content):
    """
    Alternative method: More robust extraction handling edge cases.
    """
    # Find the start of the stdata declaration
    start_marker = 'var stdata='
    start_idx = html_content.find(start_marker)
    
    if start_idx == -1:
        raise ValueError("Could not find stdata variable")
    
    # Move to the start of the JSON object
    start_idx += len(start_marker)
    
    # Find the matching closing brace
    brace_count = 0
    in_string = False
    escape_next = False
    json_start = None
    
    for i in range(start_idx, len(html_content)):
        char = html_content[i]
        
        if escape_next:
            escape_next = False
            continue
            
        if char == '\\':
            escape_next = True
            continue
            
        if char == '"' and not escape_next:
            in_string = not in_string
            
        if not in_string:
            if char == '{':
                if json_start is None:
                    json_start = i
                brace_count += 1
            elif char == '}':
                brace_count -= 1
                if brace_count == 0:
                    # Found the end of the JSON object
                    json_str = html_content[json_start:i+1]
                    print(json_str)
                    return json.loads(json_str)
    
    raise ValueError("Could not parse stdata JSON")


def clean_league_table(raw_text):
    """
    Clean and safely parse a messy stdata JSON string into a Python dictionary.
    Handles cases with escaped chars, trailing quotes, and partial endings.
    """
    if not raw_text or not isinstance(raw_text, str):
        return {}

    # 1️⃣ Remove any wrapping single or double quotes
    raw_text = raw_text.strip().strip("'").strip('"')

    # 2️⃣ Remove escaped newlines and backslashes
    cleaned = raw_text.replace("\\n", "").replace("\\", "")

    # 3️⃣ Extract only the valid JSON portion (first '{' to last '}')
    match = re.search(r'\{.*\}', cleaned, re.DOTALL)
    if not match:
        # print("❌ Could not find valid JSON object in text")
        return {}
    json_part = match.group(0)

    # 4️⃣ Try parsing
    try:
        parsed = json.loads(json_part)
        return parsed
    except json.JSONDecodeError as e:
        return {}


def get_league_table(html):
    
    try:
        # Use the first method (simpler, works for most cases)
        stdata = extract_stdata(html)

        # Pretty print the extracted data
        return json.dumps(stdata, indent=2).strip().rstrip("'}").lstrip("'")
        
    except Exception as e:
        # print(f"Error: {e}")
        return "{}"


def parse_league_table(match_id):
    """
    Fetches league table HTML, extracts the JSON-like text,
    fixes missing closing brackets, and returns a Python dict.
    """
    html = get_team_standings(match_id)
    league_table_str = get_league_table(html).strip()

    # Count braces to check balance
    open_braces = league_table_str.count('{')
    close_braces = league_table_str.count('}')

    # Add missing closing braces if needed
    if close_braces < open_braces:
        league_table_str += '}' * (open_braces - close_braces)

    try:
        league_table = json.loads(league_table_str)
        return league_table
    except json.JSONDecodeError as e:
        print(f"❌ JSON Decode Error: {e}")
        print("⚠️ Partial content (last 200 chars):")
        print(league_table_str[-200:])
        return None


def get_clean_todays_matches_data():
    all_matches = get_today_matches()
    print('======== getting head to head ==========')
    matches_data = []
    count = 0

    while count < len(all_matches):
        time.sleep(3)
        for match in all_matches:
            count += 1
            match_id = match['id']
            league_name = get_league_name(match_id)
            home_team_last_matches = get_team_last_matches(match_id,'lm_home')
            away_team_last_matches = get_team_last_matches(match_id,'lm_away')
            both_team_head_to_head = get_head_to_head(match_id)
            # html = get_team_standings(match_id)
            league_table = parse_league_table(match_id)

            if not league_table:
                # print('skipping... No league data')
                continue
            
            tables = league_table.get("overall", {}).get("tables", [])

            if not tables:
                # print(f"Skipping match {match_id} — no 'tables' data found")
                continue

            data_rows = tables[0].get("data", [])
            if not data_rows:
                # print(f"Skipping match {match_id} — table found but no data rows")
                continue

            # print(f"✅ Match {match_id} — league table found with {len(data_rows)} teams")

            matches_data.append({
            'league_name' : league_name,
            'id': match_id,
            'home_team_last_matches': home_team_last_matches,
            'away_team_last_matches': away_team_last_matches,
            'team_head_to_head': both_team_head_to_head,
            'team_standings': league_table["overall"]["tables"][0]["data"]
            })
            print(f'========== {match_id} finshed getting head-to-head =============')
            # print(count)
            # print(league_name)
    print('========== finshed getting head-to-head =============')
    return matches_data


def batch_process(data, batch_size):
    for i in range(0, len(data), batch_size):
        yield data[i:i + batch_size]


def generate_predictions(batch_size=5):
    matches = get_clean_todays_matches_data()
    print(f"Total matches found: {len(matches)}")

    final_match_data = []

    if not matches:
        print("No match data available")
        return final_match_data

    # Process matches in batches
    for batch_num, match_batch in enumerate(batch_process(matches, batch_size), start=1):
        print(f"\nProcessing batch {batch_num} ({len(match_batch)} matches)")

        for match in match_batch:
            content = f"""
            You are a football match prediction assistant.
            Use this {match} data to predict the likely outcome of the match.

            Your prediction should be one of the following formats:

            Home win
            Away win
            Home win or draw
            Away win or draw
            Over or under X goals

            Score your prediction out of 100 

            Share insights explaining the reasoning.

            Your insights should talk about the following topics in detail:
            - Both teams’ recent matches
            - Both teams’ recent forms
            - Both teams’ head-to-head matches

            Rules:
            Go straight to the prediction — do NOT start with phrases like “Based on the data” or similar introductions.
            Respond in plain text only (no Markdown, no bullet formatting).
            Keep the entire response concise and structured like this:

            Prediction: [your prediction]
            Confidence Score: [score]/100
            Insights:
            """

            # ChatResponse = chat(model='qwen3:1.7b', messages=[
            #     {'role': 'user', 'content': content}
            # ])
            messages = [
            {
                'role': 'user',
                'content': content,
            },
            ]
            response = client.chat('gpt-oss:120b-cloud', messages=messages)
            match['ai_insight'] = response['message']['content']
            final_match_data.append(match)
            print(match)
            print(f"✅ Processed match: {match.get('id', 'unknown')}")

    print(f"\nAll batches completed. Total predictions generated: {len(final_match_data)}")
    return final_match_data

# generate_predictions(batch_size=5)
