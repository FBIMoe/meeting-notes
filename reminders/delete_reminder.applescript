-- delete_reminder.applescript <listName> <reminderName>
-- Deletes reminders with this exact name from the list (used only by push-reminders.py --test).
on run argv
	set listName to item 1 of argv
	set remName to item 2 of argv
	tell application "Reminders"
		if exists list listName then delete (every reminder of list listName whose name is remName)
	end tell
end run
