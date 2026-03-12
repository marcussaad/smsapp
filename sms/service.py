"""
High-level SMS operations. Views and tasks call these functions,
never the Twilio client directly.
"""
from __future__ import annotations
from typing import TYPE_CHECKING

from .client import get_sms_client

if TYPE_CHECKING:
    from users.models import User
    from rooms.models import Room


def send_welcome(*, user: "User", room: "Room") -> None:
    client = get_sms_client()
    client.send(
        from_number=room.twilio_number,
        to=user.phone_number,
        body=(
            f"Welcome to {room.name}! 🎉\n"
            f"Reply to this number to send a message to the group. "
            f"You can be in up to 10 rooms — each has its own number."
        ),
    )


def broadcast_message(*, sender: "User", room: "Room", body: str) -> list[str]:
    """
    Send `body` to every room member except the sender.
    Returns list of Twilio message SIDs (useful for logging/auditing).
    """
    from rooms.models import Membership

    recipients = (
        Membership.objects
        .filter(room=room)
        .exclude(user=sender)
        .select_related("user")
    )

    client  = get_sms_client()
    sids    = []
    outbound = f"{sender.name}: {body}"

    for membership in recipients:
        sid = client.send(
            from_number=room.twilio_number,
            to=membership.user.phone_number,
            body=outbound,
        )
        sids.append(sid)

    return sids
