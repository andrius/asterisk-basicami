"""Unit tests for marker parsing — ported from Go collector/parser_test.go patterns."""

from basicami.marker import Marker, MarkerTrace, parse_marker


class TestParseMarker:
    def test_basic_marker(self):
        m = parse_marker("SBC_ENTER: 001D-dev-testing tenant=001D-dev-testing")
        assert m is not None
        assert m.name == "SBC_ENTER"
        assert m.context == "001D-dev-testing"
        assert m.kv == {"tenant": "001D-dev-testing"}

    def test_marker_with_prefix(self):
        m = parse_marker("    -- SBC_ENTER: 001D-dev-testing tenant=001D")
        assert m is not None
        assert m.name == "SBC_ENTER"
        assert m.context == "001D-dev-testing"
        assert m.kv == {"tenant": "001D"}

    def test_marker_multiple_kv(self):
        m = parse_marker(
            "INBOUND_ROUTE: did did=37100050001 dest=extension target=1001"
        )
        assert m is not None
        assert m.name == "INBOUND_ROUTE"
        assert m.context == "did"
        assert m.kv == {
            "did": "37100050001",
            "dest": "extension",
            "target": "1001",
        }

    def test_marker_no_kv(self):
        m = parse_marker("SBC_UNMAPPED: 37199999999")
        assert m is not None
        assert m.name == "SBC_UNMAPPED"
        assert m.context == "37199999999"
        assert m.kv == {}

    def test_non_marker_line(self):
        assert parse_marker("Just a regular log line") is None

    def test_lowercase_not_marker(self):
        assert parse_marker("lowercase: not-a-marker") is None

    def test_empty_string(self):
        assert parse_marker("") is None

    def test_ansi_stripping(self):
        m = parse_marker("\x1b[32mSBC_ENTER: ctx\x1b[0m")
        assert m is not None
        assert m.name == "SBC_ENTER"
        assert m.context == "ctx"

    def test_verbose_level_prefix(self):
        """AppData from AMI often has '1,' prefix."""
        m = parse_marker("SBC_ROUTE: 001D did=37100050001")
        assert m is not None
        assert m.name == "SBC_ROUTE"


class TestMarkerTrace:
    def _make_trace(self) -> MarkerTrace:
        t = MarkerTrace(test_id="test-1", caller_id="15550099001")
        t.markers = [
            Marker(name="SBC_ENTER", context="001D", kv={"tenant": "001D-dev-testing"}),
            Marker(name="SBC_ROUTE", context="001D", kv={"did": "37100050001"}),
            Marker(name="INBOUND_ENTER", context="001D", kv={}),
            Marker(name="INBOUND_ROUTE", context="did", kv={"did": "37100050001"}),
        ]
        return t

    def test_marker_names(self):
        t = self._make_trace()
        assert t.marker_names() == [
            "SBC_ENTER",
            "SBC_ROUTE",
            "INBOUND_ENTER",
            "INBOUND_ROUTE",
        ]

    def test_has_marker(self):
        t = self._make_trace()
        assert t.has_marker("SBC_ENTER")
        assert not t.has_marker("SBC_UNMAPPED")

    def test_get_marker(self):
        t = self._make_trace()
        m = t.get_marker("SBC_ENTER")
        assert m is not None
        assert m.kv["tenant"] == "001D-dev-testing"
        assert t.get_marker("NONEXISTENT") is None

    def test_get_marker_value(self):
        t = self._make_trace()
        assert t.get_marker_value("SBC_ENTER", "tenant") == "001D-dev-testing"
        assert t.get_marker_value("SBC_ENTER", "nope") is None
        assert t.get_marker_value("NONEXISTENT", "tenant") is None

    def test_contains_ordered_true(self):
        t = self._make_trace()
        assert t.contains_ordered(["SBC_ENTER", "INBOUND_ENTER", "INBOUND_ROUTE"])

    def test_contains_ordered_false(self):
        t = self._make_trace()
        assert not t.contains_ordered(["INBOUND_ROUTE", "SBC_ENTER"])

    def test_contains_ordered_empty(self):
        t = self._make_trace()
        assert t.contains_ordered([])

    def test_contains_ordered_exact(self):
        t = self._make_trace()
        assert t.contains_ordered(
            ["SBC_ENTER", "SBC_ROUTE", "INBOUND_ENTER", "INBOUND_ROUTE"]
        )

    def test_str(self):
        t = self._make_trace()
        s = str(t)
        assert "SBC_ENTER" in s
        assert "tenant=001D-dev-testing" in s
