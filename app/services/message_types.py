"""Structured WhatsApp message types.

These are provider-agnostic message structures:
- TextMsg  → plain text
- ButtonMsg → up to 3 quick-reply options (native buttons via Twilio Content API)
- ListMsg   → scrollable menu with sections (native list via Twilio Content API)
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class TextMsg:
    """Plain text message."""

    body: str
    content_sid: str = ""
    content_variables: dict = field(default_factory=dict)


@dataclass
class Button:
    """A tappable quick-reply button."""

    id: str
    text: str


@dataclass
class ButtonMsg:
    """Message with up to 3 quick-reply options."""

    body: str
    buttons: list[Button]
    footer: str = ""
    content_sid: str = ""
    content_variables: dict = field(default_factory=dict)


@dataclass
class ListRow:
    """A single row in a list section."""

    id: str
    title: str
    description: str = ""


@dataclass
class ListSection:
    """A section grouping in a list message."""

    title: str
    rows: list[ListRow]


@dataclass
class ListMsg:
    """Message with a scrollable list menu."""

    body: str
    button_text: str
    sections: list[ListSection]
    title: str = ""
    footer: str = "Remindam Bot"
    content_sid: str = ""
    content_variables: dict = field(default_factory=dict)


Msg = TextMsg | ButtonMsg | ListMsg
