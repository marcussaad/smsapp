from rest_framework import serializers
from .models import User


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model  = User
        fields = ["id", "name", "phone_number", "created_at"]
        read_only_fields = ["id", "created_at"]

    def validate_phone_number(self, value):
        # Normalize: strip spaces/dashes, ensure E.164-ish format
        normalized = "".join(c for c in value if c.isdigit() or c == "+")
        if len(normalized) < 10:
            raise serializers.ValidationError("Invalid phone number.")
        return normalized
