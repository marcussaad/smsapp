from rest_framework import serializers
from .models import Room, Membership


class RoomSerializer(serializers.ModelSerializer):
    member_count = serializers.IntegerField(read_only=True)

    class Meta:
        model  = Room
        fields = ["id", "name", "twilio_number", "member_count", "created_at"]
        read_only_fields = ["id", "twilio_number", "member_count", "created_at"]


class MembershipSerializer(serializers.ModelSerializer):
    user_name    = serializers.CharField(source="user.name", read_only=True)
    phone_number = serializers.CharField(source="user.phone_number", read_only=True)

    class Meta:
        model  = Membership
        fields = ["id", "user_id", "user_name", "phone_number", "joined_at"]
        read_only_fields = fields
