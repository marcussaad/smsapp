from django.db import models
from users.models import User


class Room(models.Model):
    name           = models.CharField(max_length=255)
    twilio_number  = models.CharField(max_length=20, unique=True, null=True, blank=True)
    created_at     = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    @property
    def member_count(self):
        return self.memberships.count()


class Membership(models.Model):
    user      = models.ForeignKey(User, on_delete=models.CASCADE, related_name="memberships")
    room      = models.ForeignKey(Room, on_delete=models.CASCADE, related_name="memberships")
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "room")
        ordering = ["-joined_at"]

    def __str__(self):
        return f"{self.user.name} in {self.room.name}"
