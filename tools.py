"""Mock backend tools invoked by the agent."""
from __future__ import annotations

from datetime import datetime
from typing import Dict


def mock_lead_capture(name: str, email: str, platform: str) -> Dict[str, str]:
    """Simulate writing a qualified lead into the CRM backend.

    In production this would POST to /api/leads; for the assignment we
    print a success line (as specified in the brief) and also return a
    structured payload so the agent can reference the confirmation.
    """
    print(f"Lead captured successfully: {name}, {email}, {platform}")
    return {
        "status": "success",
        "name": name,
        "email": email,
        "platform": platform,
        "captured_at": datetime.utcnow().isoformat() + "Z",
    }
