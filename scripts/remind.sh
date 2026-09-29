#!/usr/bin/env bash
# Daily study nudge (launchd, 20:55): a notification, then StudyQuest opens on today's quest.
URL="http://localhost:8765"
MSG="Your session starts at 21:00. One run, ~30 min."
if STATUS=$(curl -fsS "$URL/api/today" 2>/dev/null); then
  FOCUS=$(printf '%s' "$STATUS" | /usr/bin/python3 -c 'import json,sys
d=json.load(sys.stdin); f=d.get("exam_focus") or {}; m=d.get("mock_today")
print(f"📄 Mock exam day! {m[\"name\"]}, {m[\"minutes\"]} min on paper." if m else
      (f"{f[\"exam\"]} in {f[\"days\"]} days: {f[\"behind\"]} tasks waiting. Start with {f[\"zone_name\"]}." if f else ""))' 2>/dev/null)
  [ -n "$FOCUS" ] && MSG="$FOCUS"
fi
/usr/bin/osascript -e "display notification \"${MSG//\"/\\\"}\" with title \"StudyQuest\" subtitle \"Time to study\" sound name \"Glass\""
sleep 4
/usr/bin/open "$URL"
