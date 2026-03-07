"""Marker parsing for Asterisk Verbose/Log dialplan markers.

Ported from the Go implementation in pbx-test collector/parser.go.
"""

import re
from dataclasses import dataclass, field

# Matches structured Verbose markers.
# Format: "    -- MARKER_NAME: context key=value key=value"
_MARKER_RE = re.compile(
    r"(?:^\s*(?:--\s*)?)?([A-Z][A-Z0-9_]+):\s+(\S+)\s*(.*)$"
)

# Matches individual key=value pairs.
_KV_RE = re.compile(r"(\w+)=(\S+)")

# Strips ANSI escape sequences.
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


@dataclass
class Marker:
    """A parsed Verbose marker from the Asterisk dialplan."""

    name: str  # e.g. "SBC_ENTER", "INBOUND_ROUTE"
    context: str  # e.g. tenant ID or flow context name
    kv: dict[str, str] = field(default_factory=dict)
    raw: str = ""
    channel: str = ""
    uniqueid: str = ""


def parse_marker(line: str) -> Marker | None:
    """Parse a verbose line into a Marker, or return None if not recognized."""
    line = _ANSI_RE.sub("", line)

    m = _MARKER_RE.match(line)
    if not m:
        return None

    kv = {}
    kv_part = m.group(3)
    if kv_part:
        for kv_match in _KV_RE.finditer(kv_part):
            kv[kv_match.group(1)] = kv_match.group(2)

    return Marker(
        name=m.group(1),
        context=m.group(2),
        kv=kv,
        raw=line,
    )


class MarkerTrace:
    """Ordered collection of markers for a single test call."""

    def __init__(self, test_id: str = "", caller_id: str = ""):
        self.test_id = test_id
        self.caller_id = caller_id
        self.channel: str = ""
        self.uniqueid: str = ""
        self.linkedid: str = ""
        self.markers: list[Marker] = []

    def marker_names(self) -> list[str]:
        """Return list of marker names in order."""
        return [m.name for m in self.markers]

    def has_marker(self, name: str) -> bool:
        """Check if a marker name exists in the trace."""
        return any(m.name == name for m in self.markers)

    def get_marker(self, name: str) -> Marker | None:
        """Return the first marker with the given name, or None."""
        for m in self.markers:
            if m.name == name:
                return m
        return None

    def get_marker_value(self, marker_name: str, key: str) -> str | None:
        """Return a key-value from the first marker with the given name."""
        m = self.get_marker(marker_name)
        if m is None:
            return None
        return m.kv.get(key)

    def contains_ordered(self, names: list[str]) -> bool:
        """Check if marker names appear in order (not necessarily adjacent)."""
        if not names:
            return True
        idx = 0
        for m in self.markers:
            if m.name == names[idx]:
                idx += 1
                if idx == len(names):
                    return True
        return False

    def __str__(self) -> str:
        lines = []
        for i, m in enumerate(self.markers):
            parts = [f"  {i}: {m.name}: {m.context}"]
            for k, v in m.kv.items():
                parts.append(f" {k}={v}")
            lines.append("".join(parts))
        return "\n".join(lines)
