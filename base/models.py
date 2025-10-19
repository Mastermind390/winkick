from django.db import models

class MatchData(models.Model):
    match_id = models.CharField(max_length=20, unique=True)
    data = models.JSONField()  # stores the full JSON object you showed
    created_at = models.DateTimeField(auto_now_add=True)  # timestamp when data was saved

    class Meta:
        indexes = [
            models.Index(fields=['match_id']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f"{self.match_id}"
