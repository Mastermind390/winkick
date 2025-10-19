from django.shortcuts import render, redirect, get_object_or_404
from base.utils.scrape import get_today_matches, get_league_name, get_team_last_matches
from base.models import MatchData
import datetime
from django.http import HttpResponseServerError



# Create your views here.
def feed(request):
    current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M").split(' ')[1]
    print(current_time)
    try:
        # Try to get all matches from the database
        matches = MatchData.objects.all()

        if matches.exists():
            print("Loaded matches from database.")

            sorted_matches = sorted(
                matches,
                key=lambda x: x.data.get('start_time', '')
            )
            return render(request, "base/feed.html", context={'matches': sorted_matches, "current_time" : current_time})

        else:
            print("No matches in database. Fetching from the internet...")
            games = get_today_matches()

            new_matches = []
            for match in games:
                # Convert UNIX timestamp to readable time
                start_time = int(match.get('start-time', 0))
                time_str = datetime.datetime.fromtimestamp(start_time).strftime("%Y-%m-%d %H:%M")
                match['start_time'] = time_str.split(' ')[1]
                match.pop('start-time', None)
                # Save to database
                MatchData.objects.create(
                    match_id=match['match_id'],
                    data=match,
                    created_at=datetime.datetime.now()
                )
                new_matches.append(match)
            matches = sorted(matches, key=lambda x: x['start_time'], reverse=False)
            return render(request, "base/feed.html", context={'matches': new_matches, "current_time" : current_time})

    except Exception as err:
        print(f"Error fetching matches: {err}")
        return render(request, "base/feed.html", context={'matches': []})


def match_details(request, match_id):
    # Get the match safely (returns 404 if not found)
    game_details = get_object_or_404(MatchData, match_id=match_id)
    data = game_details.data or {}

    try:
        # Try loading last matches from saved data
        home_last_matches = data.get('home_last_matches')
        away_last_matches = data.get('away_last_matches')

        if not home_last_matches and away_last_matches:
            # If missing, fetch from external source
            home_last_matches = get_team_last_matches(match_id, 'lm_home')
            away_last_matches = get_team_last_matches(match_id, 'lm_away')
            # Update local cache
            data['home_last_matches'] = home_last_matches
            data['away_last_matches'] = away_last_matches
            game_details.data = data
            game_details.save(update_fields=['data'])

        # Render template with matches
        return render(request, 'base/last_matches.html', {
            'home_last_matches': home_last_matches,
            'away_last_matches' : away_last_matches
        })

    except Exception as err:
        print(f"Error fetching last matches: {err}")
        return HttpResponseServerError("An error occurred while loading match details.")
    
