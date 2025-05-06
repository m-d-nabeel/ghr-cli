#!/usr/bin/env bash

_ghr_cli_completion() {
    local cur prev opts
    COMPREPLY=()
    cur="${COMP_WORDS[COMP_CWORD]}"
    prev="${COMP_WORDS[COMP_CWORD-1]}"
    
    # List of all options
    opts="--config --clean --install --add --install-after-add --remove --list --rollback \
          --check-sudo --clear-cache --cache-info --cache-dir --no-cache --force-cache \
          --version --init --history --history-limit --clear-history"
    
    # Handle special cases
    case "${prev}" in
        --config)
            # Complete with yaml files
            COMPREPLY=( $(compgen -f -X '!*.y?(a)ml' -- "${cur}") )
            return 0
            ;;
        --install|--rollback|--remove)
            # If tools are stored in the configuration, this could be enhanced 
            # to dynamically complete with available tool names
            return 0
            ;;
        --history-limit)
            # Complete with numbers
            COMPREPLY=( $(compgen -W "5 10 20 50 100" -- "${cur}") )
            return 0
            ;;
        *)
            ;;
    esac
    
    # Complete with available options if typing a new flag
    if [[ ${cur} == -* ]]; then
        COMPREPLY=( $(compgen -W "${opts}" -- "${cur}") )
        return 0
    fi
}

# Register the completion function
complete -F _ghr_cli_completion ghr-cli