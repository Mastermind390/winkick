from django.shortcuts import render, redirect, get_object_or_404
from base.utils.scrape import generate_prediction
from base.models import MatchData
from django.utils import timezone
import datetime
from django.http import HttpResponseServerError
from django.contrib import messages
from zoneinfo import ZoneInfo
from datetime import timedelta



# Create your views here.
def feed(request):
    lagos_tz = ZoneInfo("Africa/Lagos")
    now = timezone.now().astimezone(lagos_tz)
    current_time = now.time()
    print(f"Current time: {current_time}")

    matches = MatchData.objects.all()

    def parse_start_time(match):
        """Safely parse and return today's datetime for the match start."""
        start_str = match.data.get('start_time')
        if not start_str:
            return datetime.datetime.max  # Put matches without time at the end
        try:
            start_dt = datetime.datetime.strptime(start_str, "%H:%M")
            # Combine today's date + start time in Lagos timezone
            start_dt_today = datetime.datetime.combine(now.date(), start_dt.time(), tzinfo=lagos_tz)
            return start_dt_today
        except Exception as e:
            print(f"Error parsing start_time for match {match.match_id}: {e}")
            return datetime.datetime.max

    # Sort matches by how close their start time is to "now"
    sorted_matches = sorted(
        matches,
        key=lambda m: (parse_start_time(m) - now).total_seconds() if parse_start_time(m) > now else float('inf')
    )

    # Optionally, bring matches starting within the next hour to the top
    sorted_matches = sorted(
        sorted_matches,
        key=lambda m: abs((parse_start_time(m) - now).total_seconds() - 3600)
    )

    # Debug output
    for match in sorted_matches:
        start_dt = parse_start_time(match)
        if start_dt != datetime.datetime.max:
            print(f"{match.match_id} -> starts at {start_dt.time()}")

    return render(request, "base/feed.html", {"matches": sorted_matches})



def match_details(request, match_id):
    game_details = MatchData.objects.get(match_id=match_id)

    data = game_details.data or {}

    try:
        home_last_matches = data.get('home_team_last_matches')
        away_last_matches = data.get('away_team_last_matches')
        start_time = data.get('start_time')
        league_name = data.get('league_name')
    except Exception as err:
        print(err)
        messages.error('failed to get match data')

    

    context = {
        'home' : home_last_matches['team_name'].strip(),
        'away' : away_last_matches['team_name'].strip(),
        'home_last_matches': home_last_matches['matches'],
        'away_last_matches': away_last_matches['matches'],
        'start_time': start_time,
        'league_name' : league_name,
        'match_id' : game_details.match_id
    }
    return render(request, 'base/last_matches.html', context)
    


def h2h(request, match_id):
    game_details = MatchData.objects.get(match_id=match_id)

    data = game_details.data or {}
    # print(data)

    try:
        home_last_matches = data.get('home_team_last_matches')
        away_last_matches = data.get('away_team_last_matches')
        head_to_head = data.get('team_head_to_head')
        start_time = data.get('start_time')
        league_name = data.get('league_name')
    except Exception as err:
        print(err)
        messages.error('failed to get match data')
    
    # print(home_last_matches)

    context = {
        'home' : home_last_matches['team_name'],
        'away' : away_last_matches['team_name'],
        'start_time': start_time,
        'league_name' : league_name,
        'match_id' : game_details.match_id,
        'head_to_head' : head_to_head
    }
    return render(request, 'base/head_to_head.html', context)


def standings(request, match_id):
    game_details = MatchData.objects.get(match_id=match_id)

    data = game_details.data or {}
    # print(data)

    try:
        home_last_matches = data.get('home_team_last_matches')
        away_last_matches = data.get('away_team_last_matches')
        standings = data.get('team_standings')
        start_time = data.get('start_time')
        league_name = data.get('league_name')
    except Exception as err:
        print(err)
        messages.error('failed to get match data')
    
    new_standings = []

    for s in standings:
        tmp = int(s['w']) + int(s['d']) + int(s['l'])
        s['tmp'] = tmp
        new_standings.append(s)

    # print(home_last_matches['team_name'].strip())
    context = {
        'home' : home_last_matches['team_name'].strip(),
        'away' : away_last_matches['team_name'].strip(),
        'start_time': start_time,
        'league_name' : league_name,
        'match_id' : game_details.match_id,
        'standings' : new_standings
    }

    return render(request, 'base/standings.html', context)


def ai_insight(request, match_id):
    game_details = MatchData.objects.get(match_id=match_id)

    data = game_details.data or {}
    # print(data)

    # test = generate_prediction(data)

    # print(test)

    try:
        home_last_matches = data.get('home_team_last_matches')
        away_last_matches = data.get('away_team_last_matches')
        start_time = data.get('start_time')
        league_name = data.get('league_name')
    except Exception as err:
        print(err)
        messages.error('failed to get match data')
    
    try:
        ai_insight = data.get('ai_insight')
        if ai_insight is None:
            print('AI insight not found in DB, fetching...')
            ai_insight = generate_prediction(data)
            data['ai_insight'] = ai_insight

            MatchData.objects.update_or_create(
                match_id=match_id,
                defaults={
                    'data': data,
                    'created_at': game_details.created_at
                }
            )
            print('AI insight saved to DB')
        else:
            print('Found ai_insight in DB, skipping Gemini API call.')

    except Exception as e:
        print(f"Error processing AI insight: {e}")

    print(ai_insight)
    
    context = {
        'home' : home_last_matches['team_name'].strip(),
        'away' : away_last_matches['team_name'].strip(),
        'start_time': start_time,
        'league_name' : league_name,
        'match_id' : game_details.match_id,
        'ai_insight' : ai_insight
    }
    return render(request, 'base/ai.html', context)