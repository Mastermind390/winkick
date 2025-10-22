from django.urls import path
from base.views import feed, match_details,h2h,standings, ai_insight

app_name = 'base'

urlpatterns = [
    path("", feed, name="feed"),
    path("last_matches/<str:match_id>", match_details, name="last_matches"),
    path("h2h/<str:match_id>", h2h, name="h2h"),
    path("standings/<str:match_id>", standings, name="standings"),
    path("ai_insight/<str:match_id>", ai_insight, name="ai_insight"),
]