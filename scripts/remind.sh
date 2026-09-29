#!/usr/bin/env bash
# Daily study nudge (launchd, 20:55): a notification, then StudyQuest opens on today's quest.
URL="http://localhost:8765"
MSG="Your session starts at 21:00. One run, ~30 min."
if STATUS=$(curl -fsS "$URL/api/today" 2>/dev/null); then
  FOCUS=$(printf '%s' "$STATUS" | /usr/bin/python3 -c '
import json, sys
d = json.load(sys.stdin)
f = d.get("exam_focus") or {}
m = d.get("mock_today")
if m:
    print("Mock exam day! %s, %s min on paper." % (m["name"], m["minutes"]))
elif f:
    print("%s in %s days: %s tasks waiting. Start with %s." % (f["exam"], f["days"], f["behind"], f["zone_name"]))
' 2>/dev/null)
  [ -n "$FOCUS" ] && MSG="$FOCUS"
fi
/usr/bin/osascript -e "display notification \"${MSG//\"/\\\"}\" with title \"StudyQuest\" subtitle \"Time to study\" sound name \"Glass\""
sleep 4
/usr/bin/open "$URL"
