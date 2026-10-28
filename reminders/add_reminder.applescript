-- add_reminder.applescript <listName> <reminderName> <noteTitle>
-- Creates one reminder in <listName> (making the list if needed). iCloud syncs it to iPhone/Watch.
on run argv
	set listName to item 1 of argv
	set taskName to item 2 of argv
	set noteTitle to item 3 of argv
	tell application "Reminders"
		if not (exists list listName) then make new list with properties {name:listName}
		make new reminder at end of list listName with properties {name:taskName, body:("From meeting: " & noteTitle)}
	end tell
end run
