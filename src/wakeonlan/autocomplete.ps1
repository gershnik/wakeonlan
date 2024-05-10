


$scriptblock = {
    param($wordToComplete, $commandAst, $cursorPosition)
        
    $words = @()
    $commandAst.FindAll({ $args[0].Parent -eq $commandAst }, $false) | ForEach-Object {
        $words += $_
    }
    
    $prevIdx = -1
    for ($i = 0; $i -le ($words.length - 1); $i += 1) {
        $word=$words[$i]
        if ($word.Extent.EndOffset -lt $cursorPosition) {
            $prevIdx = $i
        }
    }
    
    $found = $false
    if (($prevIdx -eq 0) -or ("$($words[$prevIdx])" -eq "-d") -or ("$($words[$prevIdx])" -eq "--delete")) {
        [string[]]$names = $(wakeonlan -n)
        foreach ($name in $names) {
            if ($name.StartsWith($wordToComplete)) {
                if ($null -ne ($(' ', '"') | Where-Object { $name -match $_ })) {
                    "'$name'"
                } else {
                    "$name"
                }
                $found = $true
            }
        }
        
    } 
    if (-not $found) {
        ""
    }
}


Register-ArgumentCompleter -Native -CommandName wakeonlan -ScriptBlock $scriptblock
