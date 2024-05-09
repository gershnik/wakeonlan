
if [ -n "$BASH_VERSION" ]; then
    function _wakeonlan() {
        local command=$1
        local curWord=$2
        local prevWord=$3

        COMPREPLY=()
        if [[ "$prevWord" != "$command" && "$prevWord" != "-d" && "$prevWord" != "--delete" ]]; then
            return 0
        fi

        local -a names
        local lines=`wakeonlan -n`
        for line in $lines; do
            names+=("$line")
        done

        for name in "${names[@]}"; do
            case $name in $curWord*)
                COMPREPLY+=($name)
            esac
        done
        
        return 0
    }

    complete -F "_wakeonlan" "wakeonlan"

elif [ -n "$ZSH_VERSION" ]; then 
    function _wakeonlan() {
        local -a args
        local context state state_descr line
        typeset -A opt_args

        local exargs="-h --help -v --version"
        local edargs="-s --save -d --delete -l --list -n --names" 

        args=(
            "(1 $edargs $exargs)"{-s,--save=}'[save new name]:name:( ):mac:( )'
            "(1 $edargs $exargs)"{-d,--delete=}'[delete saved name]:name:->names'
            "(1 $edargs $exargs)"{-l,--list=}'[list saved definitions]'
            "(1 $edargs $exargs)"{-n,--names=}'[list saved names]'
            '(1 -)'{-h,--help}'[display help information]'
            '(1 -)'{-v,--version}'[print program version]'
            "(-d --delete -l --list -n --names $exargs)"-a'[ip address]:addr:= (255.255.255.255)'
            "(-d --delete -l --list -n --names $exargs)"-p'[port]:port:= (9)'
            "($edargs $exargs)"':name:->names'
        )
        _arguments $args
        case $state in
            names)
                for line in "${(@f)"$(wakeonlan -n)"}"
                {
                    compadd $line
                }
            ;;
        esac
        return 0
    }


    compdef _wakeonlan wakeonlan
else
    echo You shell is not supported for wakeonlan autocomplete
fi



