-- set_reminder.applescript <listName> <reminderName> <true|false>
-- Marks the matching reminder(s) completed (true) or open again (false). Prints how many changed.
on run argv
	set listName to item 1 of argv
	set remName to item 2 of argv
	set wantDone to ((item 3 of argv) is "true")
	tell application "Reminders"
		if not (exists list listName) then return "0"
		set hits to (every reminder of list listName whose name is remName and completed is not wantDone)
		repeat with r in hits
			set completed of r to wantDone
		end repeat
		return (count of hits) as text
	end tell
end run
