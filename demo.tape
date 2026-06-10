Output tabletop-demo.gif

Set FontSize 20
Set FontFamily "Menlo"
Set Theme "Catppuccin Mocha"
Set Width 1500
Set Height 600
Set Padding 24
Set Margin 12
Set MarginFill "#1e1e2e"
Set BorderRadius 8
Set Framerate 30
Set TypingSpeed 30ms
Set WindowBar Colorful
Set WindowBarSize 32

# Show raw df -h output to establish the problem
Type "# default console table output"
Sleep 100ms
Enter
Sleep 300ms
Type "df -h"
Sleep 150ms
Enter
Sleep 2.5s

Ctrl+L
Sleep 250ms

# Pipe through tabletop (default: rich table)
Type "# Pipe through tabletop for enhanced rich table format"
Sleep 150ms
Enter
Sleep 300ms
Type "df -h | tabletop"
Sleep 200ms
Enter
Sleep 2.5s

Ctrl+L
Sleep 250ms

# Sort by Used ascending (smart unit detection: 6Mi > 6Gi)
Type "# Sort by Used with smart unit detection (Mi < Gi)"
Sleep 200ms
Enter
Sleep 300ms
Type "df -h | tabletop -s Used"
Sleep 300ms
Enter
Sleep 2.5s

Ctrl+L
Sleep 250ms

# Filter + reverse sort + plain format
Type "# Filter and reverse sort by Capacity, markdown output"
Sleep 200ms
Enter
Sleep 300ms
Type "df -h | tabletop -sr Capacity -f Filesystem:^/ --md"
Sleep 500ms
Enter
Sleep 2.5s
