#compdef ghr-cli

_ghr_cli() {
    local -a opts
    
    opts=(
        '--config[Configuration file]:config file:_files -g "*.y(a)ml"'
        '--clean[Clean old versions according to keep_versions setting]'
        '--install[Install all tools or specify a repository]:repository:'
        '--add[Add a new repository to the toolset configuration]:repository format (owner/repo):'
        '--install-after-add[Automatically install a tool after adding it with --add]'
        '--remove[Remove a repository from the toolset configuration]:repository format (owner/repo):'
        '--list[List all configured tools and their versions]'
        '--rollback[Rollback to previous version of a tool]:repository:'
        '--check-sudo[Check if sudo access is available]'
        '--clear-cache[Clear the download and API response cache]'
        '--cache-info[Show cache information and statistics]'
        '--cache-dir[Show cache information and statistics]'
        '--no-cache[Disable caching for this run]'
        '--force-cache[Force caching for this run, ignoring config setting]'
        '--version[Show the version and exit]'
        '--init[Initialize a default config file in the user'"'"'s config directory]'
        '--history[Show the history of tool operations]'
        '--history-limit[Limit history to N entries]:number:(5 10 20 50 100)'
        '--clear-history[Clear the operation history logs]'
    )
    
    _arguments -s $opts
}

_ghr_cli "$@"