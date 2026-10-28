-- list_completed.applescript <listName>
-- Prints one line per COMPLETED reminder in <listName>:  id <TAB> name <TAB> notes
on run argv
	set listName to item 1 of argv
	set txt to ""
	tell application "Reminders"
		if not (exists list listName) then return ""
		repeat with r in (reminders of list listName whose completed is true)
			set rbd to ""
			try
				set rbd to body of r
			end try
			if rbd is missing value then set rbd to ""
			set txt to txt & (id of r) & tab & (name of r) & tab & rbd & linefeed
		end repeat
	end tell
	return txt
end run
