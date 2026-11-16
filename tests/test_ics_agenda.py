"""Unit tests for skills/ics-agenda/scripts/ics_agenda.py (stdlib unittest only).

Run: python3 -m unittest discover -s tests
"""

import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills" / "ics-agenda" / "scripts"))

import ics_agenda as ia  # noqa: E402

FIXTURE = str(ROOT / "tests" / "fixtures" / "sample.ics")
NOW = "2026-11-16T08:00"  # a Monday, America/Los_Angeles
LA = ZoneInfo("America/Los_Angeles")


def run(*argv, env=None):
    """Run main() and return (exit_code, stdout, stderr)."""
    out, err = io.StringIO(), io.StringIO()
    old = dict(os.environ)
    os.environ.pop("ICS_AGENDA_URL", None)
    os.environ.pop("ICS_AGENDA_TZ", None)
    os.environ.update(env or {})
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = ia.main(list(argv))
    finally:
        os.environ.clear()
        os.environ.update(old)
    return code, out.getvalue(), err.getvalue()


def run_json(*argv):
    code, out, _ = run(*argv, "--json")
    assert code == 0, out
    return json.loads(out)


def window(days=14):
    start = datetime.fromisoformat(NOW).replace(tzinfo=LA)
    events = ia.parse_events(ia.read_source(FIXTURE), LA)
    return ia.expand(events, start, start + timedelta(days=days), LA)


class ParsingTests(unittest.TestCase):
    def test_unfold(self):
        lines = ia.unfold("SUMMARY:Hello\r\n  world\r\n\tagain\r\nUID:x\r\n")
        self.assertEqual(lines, ["SUMMARY:Hello world" + "again", "UID:x"])

    def test_parse_line_quoted_param(self):
        name, params, value = ia.parse_line('ATTENDEE;CN="Doe: Jane";ROLE=CHAIR:mailto:j@example.invalid')
        self.assertEqual(name, "ATTENDEE")
        self.assertEqual(params["CN"], "Doe: Jane")
        self.assertEqual(value, "mailto:j@example.invalid")

    def test_unescape(self):
        self.assertEqual(ia.unescape_text(r"a\, b\; c\\d\ne"), "a, b; c\\d\ne")

    def test_parse_dt_variants(self):
        utc = ia.parse_dt("20261116T180000Z", {}, LA)
        self.assertEqual(utc.astimezone(LA).hour, 10)
        ny = ia.parse_dt("20261116T133000", {"TZID": "America/New_York"}, LA)
        self.assertEqual(ny.astimezone(LA).strftime("%H:%M"), "10:30")
        d = ia.parse_dt("20261126", {"VALUE": "DATE"}, LA)
        self.assertEqual(str(d), "2026-11-26")
        floating = ia.parse_dt("20261116T090000", {}, LA)
        self.assertEqual(floating.tzinfo, LA)
        unknown = ia.parse_dt("20261116T090000", {"TZID": "Pacific Standard Time"}, LA)
        self.assertEqual(unknown.tzinfo, LA)  # falls back to display tz

    def test_duration(self):
        self.assertEqual(ia.parse_duration("PT90M"), timedelta(minutes=90))
        self.assertEqual(ia.parse_duration("P1DT2H"), timedelta(days=1, hours=2))
        self.assertEqual(ia.parse_duration("-P1W"), -timedelta(weeks=1))

    def test_valarm_is_ignored(self):
        evs = ia.parse_events(ia.read_source(FIXTURE), LA)
        standup = [e for e in evs if e.uid.startswith("standup") and e.recurrence_id is None][0]
        self.assertEqual(standup.summary, "Daily standup")  # not the VALARM's DESCRIPTION text
        self.assertEqual(standup.description, "")


class ExpansionTests(unittest.TestCase):
    def titles_on(self, day):
        return [i.summary for i in window() if i.start.date().isoformat() == day]

    def test_weekly_byday_exdate_and_override(self):
        standups = [i for i in window() if i.summary.startswith("Daily standup")]
        got = [(i.start.strftime("%m-%d %H:%M"), i.summary) for i in standups]
        self.assertEqual(got, [
            ("11-16 09:30", "Daily standup"),
            # 11-18 removed by EXDATE
            ("11-20 10:00", "Daily standup (moved)"),  # RECURRENCE-ID override
            ("11-23 09:30", "Daily standup"),
            ("11-25 09:30", "Daily standup"),
            ("11-27 09:30", "Daily standup"),
        ])

    def test_weekly_until(self):
        start = datetime(2026, 11, 30, tzinfo=LA)
        evs = ia.parse_events(ia.read_source(FIXTURE), LA)
        insts = [i for i in ia.expand(evs, start, start + timedelta(days=21), LA)
                 if i.summary == "Daily standup"]
        self.assertEqual([i.start.day for i in insts], [30, 2, 4])  # UNTIL 2026-12-04

    def test_daily_count(self):
        start = datetime(2026, 11, 1, tzinfo=LA)
        evs = ia.parse_events(ia.read_source(FIXTURE), LA)
        gym = [i for i in ia.expand(evs, start, start + timedelta(days=60), LA) if i.summary == "Gym"]
        self.assertEqual(len(gym), 10)
        self.assertEqual(gym[0].start.date().isoformat(), "2026-11-12")
        self.assertEqual(gym[-1].start.date().isoformat(), "2026-11-21")

    def test_dst_wall_clock_preserved(self):
        ics = ("BEGIN:VCALENDAR\r\nBEGIN:VEVENT\r\nUID:d\r\n"
               "DTSTART;TZID=America/Los_Angeles:20261026T090000\r\n"
               "DTEND;TZID=America/Los_Angeles:20261026T100000\r\n"
               "RRULE:FREQ=WEEKLY;COUNT=3\r\nSUMMARY:x\r\nEND:VEVENT\r\nEND:VCALENDAR\r\n")
        evs = ia.parse_events(ics, LA)
        start = datetime(2026, 10, 20, tzinfo=LA)
        insts = ia.expand(evs, start, start + timedelta(days=30), LA)
        self.assertEqual([i.start.strftime("%m-%d %H:%M") for i in insts],
                         ["10-26 09:00", "11-02 09:00", "11-09 09:00"])
        self.assertTrue(all(i.end - i.start == timedelta(hours=1) for i in insts))

    def test_daily_interval_byday_filter(self):
        ics = ("BEGIN:VCALENDAR\r\nBEGIN:VEVENT\r\nUID:w\r\nDTSTART:20261116T170000Z\r\n"
               "DURATION:PT30M\r\nRRULE:FREQ=DAILY;BYDAY=MO,TU,WE,TH,FR;COUNT=6\r\n"
               "SUMMARY:weekday\r\nEND:VEVENT\r\nEND:VCALENDAR\r\n")
        start = datetime(2026, 11, 16, tzinfo=LA)
        insts = ia.expand(ia.parse_events(ics, LA), start, start + timedelta(days=14), LA)
        self.assertEqual([i.start.day for i in insts], [16, 17, 18, 19, 20, 23])

    def test_all_day_and_cancelled(self):
        titles = [i.summary for i in window()]
        self.assertIn("Example Conference", titles)
        self.assertIn("Holiday (office closed)", titles)
        self.assertNotIn("Cancelled review", titles)
        conf = [i for i in window() if i.summary == "Example Conference"][0]
        self.assertTrue(conf.all_day)
        self.assertEqual(conf.end - conf.start, timedelta(days=2))

    def test_duration_event(self):
        ws = [i for i in window() if i.summary == "Workshop"][0]
        self.assertEqual((ws.start.strftime("%H:%M"), ws.end.strftime("%H:%M")), ("15:00", "16:30"))


class CommandTests(unittest.TestCase):
    def test_agenda_text(self):
        code, out, _ = run("agenda", "--days", "2", "--source", FIXTURE, "--now", NOW)
        self.assertEqual(code, 0)
        self.assertIn("Mon 2026-11-16", out)
        self.assertIn("10:00-11:00  Team sync @ Video call", out)
        self.assertIn("Lunch; with Sam, Alex @ Cafe, 2nd floor", out)
        self.assertNotIn("IGNORE", out)  # descriptions only shown with --details

    def test_global_options_before_subcommand_and_env(self):
        code, out, _ = run("--source", FIXTURE, "--now", NOW, "next")
        self.assertEqual(code, 0)
        self.assertIn("Next: Mon 2026-11-16 09:30-09:45", out)
        code, out, _ = run("next", "--now", NOW, env={"ICS_AGENDA_URL": FIXTURE})
        self.assertEqual(code, 0)
        self.assertIn("Daily standup", out)

    def test_tz_option(self):
        data = run_json("agenda", "--days", "1", "--source", FIXTURE, "--now", "2026-11-16T11:00",
                        "--tz", "America/New_York")
        sync = [e for e in data["events"] if e["summary"] == "Team sync"][0]
        self.assertEqual(sync["start"], "2026-11-16T13:00:00-05:00")

    def test_free(self):
        data = run_json("free", "--date", "2026-11-16", "--min", "30", "--source", FIXTURE, "--now", NOW)
        slots = [(s["start"][11:16], s["end"][11:16]) for s in data["slots"]]
        self.assertEqual(slots, [("09:00", "09:30"), ("11:30", "15:00"), ("17:00", "18:00")])

    def test_free_ignores_transparent(self):
        data = run_json("free", "--date", "2026-11-17", "--min", "60", "--start", "11:00",
                        "--end", "16:00", "--source", FIXTURE, "--now", NOW)
        slots = [(s["start"][11:16], s["end"][11:16]) for s in data["slots"]]
        self.assertEqual(slots, [("11:00", "12:00"), ("13:00", "16:00")])  # 'Optional focus block' is TRANSP:TRANSPARENT

    def test_conflicts(self):
        data = run_json("conflicts", "--days", "14", "--source", FIXTURE, "--now", NOW)
        self.assertEqual(len(data["conflicts"]), 1)
        c = data["conflicts"][0]
        self.assertEqual({c["a"]["summary"], c["b"]["summary"]}, {"Team sync", "Advisor meeting"})
        self.assertEqual(c["overlap_start"][11:16], "10:30")
        self.assertEqual(c["overlap_end"][11:16], "11:00")

    def test_next_with_ongoing(self):
        code, out, _ = run("next", "--source", FIXTURE, "--now", "2026-11-16T10:45")
        self.assertIn("Now (until 11:00): Team sync", out)
        self.assertIn("Next: Mon 2026-11-16 15:00-16:30", out)

    def test_missing_source(self):
        code, _, err = run("agenda")
        self.assertEqual(code, 2)
        self.assertIn("ICS_AGENDA_URL", err)


class SafetyTests(unittest.TestCase):
    def test_bundled_sample_matches_fixture(self):
        bundled = ROOT / "skills" / "ics-agenda" / "assets" / "sample.ics"
        self.assertEqual(bundled.read_bytes(), Path(FIXTURE).read_bytes())

    def test_injection_text_is_sanitized_data(self):
        code, out, _ = run("agenda", "--days", "2", "--details", "--source", FIXTURE, "--now", NOW)
        line = [l for l in out.splitlines() if "IGNORE ALL PREVIOUS" in l][0]
        self.assertTrue(line.lstrip().startswith("[event text, untrusted]"))
        self.assertNotIn("\x1b", out)
        self.assertTrue(all(ch == "\n" or ch >= " " for ch in out))

    def test_json_marks_untrusted(self):
        data = run_json("agenda", "--days", "2", "--source", FIXTURE, "--now", NOW)
        self.assertIn("untrusted", data["note"])
        lunch = [e for e in data["events"] if e["summary"].startswith("Lunch")][0]
        self.assertNotIn("\x1b", lunch["description"])
        self.assertNotIn("\n", lunch["description"])

    def test_clean_strips_bidi_and_limits_length(self):
        self.assertEqual(ia.clean("a‮b​c\x07"), "abc")
        self.assertLessEqual(len(ia.clean("x" * 1000)), ia.MAX_TEXT)

    def test_rejects_non_https(self):
        for url in ("http://example.invalid/cal.ics", "file:///etc/passwd", "ftp://x/y.ics"):
            with self.assertRaises(ia.IcsError):
                ia.read_source(url)

    def test_size_cap(self):
        with tempfile.NamedTemporaryFile("wb", suffix=".ics", delete=False) as fh:
            fh.write(b"X" * (ia.MAX_BYTES + 10))
        try:
            with self.assertRaises(ia.IcsError):
                ia.read_source(fh.name)
        finally:
            os.unlink(fh.name)


if __name__ == "__main__":
    unittest.main()
