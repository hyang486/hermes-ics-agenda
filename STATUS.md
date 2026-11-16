# STATUS: ics-agenda skill tap (A3 "Advanced integration")
1. Built the original skill `skills/ics-agenda/` (SKILL.md + scripts/ics_agenda.py + assets/sample.ics). It is Python 3.11+ stdlib only and read-only.
2. Commands: `agenda --days N`, `free --date D --min M --start HH:MM --end HH:MM [--all-day-busy]`, `conflicts --days N`, `next`, plus `--json`, `--tz`, `--source`, `--now`, `--details`.
3. Parsing covers unfolding, escapes, quoted params, TZID/UTC/floating times, all-day and multi-day events, DURATION, CANCELLED, TRANSPARENT, VALARM skipping, DAILY/WEEKLY RRULE (INTERVAL/COUNT/UNTIL/BYDAY), EXDATE, RECURRENCE-ID and DST.
4. Safety: https-only fetch (webcal rewritten, non-https redirects refused), 10 s timeout, 2 MB cap. Event text has control/ANSI/bidi characters stripped and is labeled untrusted. SKILL.md forbids following event instructions.
5. SKILL.md frontmatter: name, description (57 chars), version 1.0.0, author "ics-agenda contributors" (the lead may want a real name), MIT license, and metadata.hermes.tags/requires_toolsets.
6. Tests: `python3 -m unittest discover -s tests` passes 27 tests on Python 3.14. The fixture includes recurrence, an override, all-day events, a conflict and a prompt-injection DESCRIPTION.
7. `scripts/fresh_install_test.sh` (OWNER_REPO=<owner>/<repo>; MODE=auto|docker|local|print) uses a throwaway /tmp HERMES_HOME. It runs tap add, install and the skill on the bundled sample, and writes the log to transcripts/.
8. The fresh-install script was dry-run only, with a stub `hermes` (that log was deleted). Docker and hermes are NOT installed on this machine, so no real transcript exists yet.
9. Unverified: the Docker image's entrypoint and HERMES_HOME handling (the script uses --entrypoint hermes and -e HERMES_HOME=/hermes-home), and whether `skills install` prompts (the script pipes 'y').
10. The git repo is initialized with one commit. No remote and no push. Next step for the lead: publish the public repo, then run `OWNER_REPO=... COMMIT=<hash> scripts/fresh_install_test.sh` and commit the transcript.
