from django.urls import path
from base.views import feed, match_details

app_name = 'base'

urlpatterns = [
    path("", feed, name="feed"),
    path("last_matches/<int:match_id>", match_details, name="last_matches"),
]