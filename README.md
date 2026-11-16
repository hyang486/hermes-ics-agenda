# ics-agenda: a Hermes Agent skill tap

`ics-agenda` is a self-contained [Hermes Agent](https://github.com/NousResearch/hermes-agent)
skill. It answers calendar questions from any iCalendar (`.ics`) feed:

- **agenda**: events in the next *N* days
- **free**: free slots on a day, inside working hours
- **conflicts**: double-booked (overlapping) events
- **next**: what's on now and what's next

It is read-only and uses only the Python 3.11+ standard library (no pip
installs). It handles folded lines, `TZID`/UTC/floating times, all-day and
multi-day events, `RRULE` (`DAILY`/`WEEKLY` with `INTERVAL`, `COUNT`, `UNTIL`,
`BYDAY`), `EXDATE`, `RECURRENCE-ID` overrides, and DST changes.

## Install (as a Hermes skill tap)

This repository is a tap: skills live under `skills/<slug>/SKILL.md`.

```bash
hermes skills tap add hyang486/hermes-ics-agenda
hermes skills install hyang486/hermes-ics-agenda/ics-agenda
```

Pin a version by installing from a tagged release or commit of this repo. See
the release notes for the commit hash.

Then point it at a calendar. Put this in `$HERMES_HOME/.env`, and keep the
value secret:

```bash
ICS_AGENDA_URL=https://calendar.google.com/calendar/ical/.../basic.ics   # "Secret address in iCal format"
ICS_AGENDA_TZ=America/Los_Angeles                                        # optional
```

Then ask Hermes things like *"what's on my calendar this week?"*, *"find me
45 free minutes tomorrow afternoon"* or *"do I have any conflicts next week?"*.

## Run the script directly

```bash
python3 skills/ics-agenda/scripts/ics_agenda.py agenda --days 3 \
  --source skills/ics-agenda/assets/sample.ics --now 2026-11-16T08:00
python3 skills/ics-agenda/scripts/ics_agenda.py free --date 2026-11-16 --min 30 \
  --source skills/ics-agenda/assets/sample.ics --now 2026-11-16T08:00 --json
```

## Safety

- Event text (titles, locations, descriptions) is **untrusted**. The script
  strips control characters, ANSI escapes and bidi overrides, flattens and
  truncates the text, and labels it as untrusted. `SKILL.md` tells the agent
  never to follow instructions found inside calendar events. The test fixture
  includes a prompt-injection description to check this.
- Network: `https://` only (`webcal://` is rewritten to https). 10 s timeout,
  2 MB cap, and it refuses redirects to non-https URLs.
- No credentials, personal data or machine-specific paths ship with the
  skill. The bundled `assets/sample.ics` is synthetic.

## Development

```bash
python3 -m unittest discover -s tests       # 27 tests, stdlib only
OWNER_REPO=hyang486/hermes-ics-agenda scripts/fresh_install_test.sh   # fresh Hermes install + transcript
```

`scripts/fresh_install_test.sh` creates a throwaway `HERMES_HOME` under
`/tmp`. It then runs the official `nousresearch/hermes-agent:v0.22.7` Docker
image (or a local `hermes`), adds this tap, installs the skill, runs it on the
bundled sample, and saves the transcript in `transcripts/`.

## Layout

```
skills/ics-agenda/SKILL.md              # skill definition (frontmatter + instructions)
skills/ics-agenda/scripts/ics_agenda.py # the tool
skills/ics-agenda/assets/sample.ics     # synthetic demo calendar
tests/                                  # unittest suite + fixture
scripts/fresh_install_test.sh           # fresh-install verification
```

## License

MIT. See [LICENSE](LICENSE).
