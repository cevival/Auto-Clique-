$add1 = "$env:LOCALAPPDATA\Programs\Python\Python311"
$add2 = "$add1\Scripts"
$p = [Environment]::GetEnvironmentVariable("Path","User")
if ($p -notlike "*$add1*") {
    if ($p) { $p = $p + ";" + $add1 } else { $p = $add1 }
}
if ($p -notlike "*$add2*") { $p = $p + ";" + $add2 }
[Environment]::SetEnvironmentVariable("Path",$p,"User")
Write-Output "User PATH updated"
