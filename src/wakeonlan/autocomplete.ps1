$scriptblock = {
    param($wordToComplete, $commandAst, $cursorPosition)

    # Direct children of the command (the command name plus its arguments).
    $words = $commandAst.CommandElements

    # Index of the last word whose extent ends before the cursor -- the
    # "previous" word relative to the one being completed.
    $prevIdx = -1
    for ($i = 0; $i -le ($words.Count - 1); $i += 1) {
        if ($words[$i].Extent.EndOffset -lt $cursorPosition) {
            $prevIdx = $i
        }
    }
    $prev = if ($prevIdx -ge 0) { $words[$prevIdx].Extent.Text } else { '' }

    # Quote with single quotes if the value contains whitespace or a double
    # quote; double any embedded single quotes per PowerShell's rules.
    function emit($value) {
        if ($value -match '[\s"]') {
            "'$($value -replace ""'"", ""''"")'"
        } else {
            $value
        }
    }

    if (($prevIdx -eq 0) -or ($prev -eq '-d') -or ($prev -eq '--delete')) {
        foreach ($name in @(wakeonlan -n)) {
            if ($name.StartsWith($wordToComplete)) { emit $name }
        }
    }
    elseif ($prev -eq '-i') {
        foreach ($iface in @(wakeonlan --interfaces)) {
            if ($iface.StartsWith($wordToComplete)) { emit $iface }
        }
    }
}


Register-ArgumentCompleter -Native -CommandName wakeonlan -ScriptBlock $scriptblock
