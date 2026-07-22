param([string]$ServerName = "aisc-project-cognition")
$server = (Resolve-Path (Join-Path $PSScriptRoot '..\dist\src\server.js')).Path
codex mcp add $ServerName --env "CODEBASE_MEMORY_COMMAND=C:/Users/HP/.local/bin/codebase-memory-mcp.exe" -- node $server
