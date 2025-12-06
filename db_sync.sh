# Source config variables to ensure they are available
source ./config_var.sh

# Helper to generate dump command
_get_dump_cmd() {
    local type=$1
    local user=$2
    local pass=$3
    local db=$4
    
    case "$type" in
        mysql)
            echo "mysqldump --single-transaction --quick --no-tablespaces -u \"$user\" -p\"$pass\" \"$db\""
            ;;
        postgresql|pgsql)
            # Uses PGPASSWORD env var for non-interactive auth
            echo "PGPASSWORD=\"$pass\" pg_dump -U \"$user\" -F c -b -v -f - \"$db\""
            ;;
        *)
            echo "echo 'Error: Unknown DB type $type'"
            ;;
    esac
}

# Helper to generate restore command
_get_restore_cmd() {
    local type=$1
    local user=$2
    local pass=$3
    local db=$4
    
    case "$type" in
        mysql)
            echo "mysql -u \"$user\" -p\"$pass\" \"$db\""
            ;;
        postgresql|pgsql)
            echo "PGPASSWORD=\"$pass\" pg_restore -U \"$user\" -d \"$db\" -v"
            ;;
        *)
            echo "echo 'Error: Unknown DB type $type'"
            ;;
    esac
}

# Function to sync a single database
# Arguments are optional. If not provided, defaults from config_var.sh are used.
sync_database() {
    local src_host=${1:-$SRCHOST}
    local src_ssh_port=${2:-$SRCSSHPORT}
    local src_ssh_user=${3:-$SRCUSER}
    local src_db_name=${4:-$SRCDBNAME}
    local src_db_user=${5:-$SRCDBUSER}
    local src_db_pass=${6:-$SRCDBPASS}
    
    local dst_host=${7:-$DSTHOST}
    local dst_ssh_port=${8:-$DSTSSHPORT}
    local dst_ssh_user=${9:-$DSTUSER}
    local dst_db_name=${10:-$DSTDBNAME}
    local dst_db_user=${11:-$DSTDBUSER}
    local dst_db_pass=${12:-$DSTDBPASS}
    
    local db_type=${13:-${DB_TYPE:-mysql}}

    # Use /tmp for dumps to ensure non-root users have write permissions
    # Add timestamp to avoid collisions
    local dump_file="/tmp/${DB_DUMP_NAME}_$(date +%s).sql"
    local dst_dump_file="/tmp/${DB_DUMP_NAME}_$(date +%s).sql"
    
    echo -e "${YELLOW}#=== Syncing Database ($db_type): $src_db_name -> $dst_db_name${RESET}"

    # Generate Commands
    local cmd_dump=$(_get_dump_cmd "$db_type" "$src_db_user" "$src_db_pass" "$src_db_name")
    local cmd_restore=$(_get_restore_cmd "$db_type" "$dst_db_user" "$dst_db_pass" "$dst_db_name")

    # SMART LOCAL TRANSFER (Pipe directly)
    if [[ ("$src_host" == "localhost") && \
          ("$dst_host" == "localhost" || "$dst_host" == "127.0.0.1") ]]; then
        
        echo -e "${BLUE}#=== Local-to-Local detected. Piping directly...${RESET}"
        
        # Execute the pipe
        eval "$cmd_dump | $cmd_restore" 2>/dev/null
        
        if [ $? -eq 0 ]; then
            echo -e "  ${GREEN}✔ Database synced successfully${RESET}"
        else
            echo -e "  ${RED}✘ Database sync failed${RESET}" >&2
            exit 1
        fi
        return
    fi

    # STANDARD TRANSFER (Dump -> Transfer -> Restore)
    
    # 1. Dump Source
    echo -e "${BLUE}#=== Dumping source database...${RESET}"
    if [[ "$src_host" == "localhost" ]]; then
        eval "$cmd_dump > \"$dump_file\"" 2>/dev/null
    else
        # Note: We need to escape quotes for the SSH command
        # The cmd_dump already contains quotes, so we need to be careful.
        # Simplest way for remote execution of complex command strings is often to write a temp script, 
        # but here we will try to wrap it.
        ssh -p "$src_ssh_port" "$src_ssh_user@$src_host" "$cmd_dump > \"$dump_file\"" 2>/dev/null
    fi

    # 2. Transfer Dump
    echo -e "${BLUE}#=== Transferring dump file...${RESET}"
    
    if [[ "$dst_host" == "localhost" || "$dst_host" == "127.0.0.1" ]]; then
        if [[ "$src_host" == "localhost" ]]; then
             cp "$dump_file" "$dst_dump_file"
        else
             scp -P "$src_ssh_port" "$src_ssh_user@$src_host:$dump_file" "$dst_dump_file" >/dev/null 2>&1
        fi
    else
        # Remote Destination
        if [[ "$src_host" == "localhost" ]]; then
             scp -P "$dst_ssh_port" "$dump_file" "$dst_ssh_user@$dst_host:$dst_dump_file" >/dev/null 2>&1
        else
             # Remote to Remote
             ssh -p "$src_ssh_port" "$src_ssh_user@$src_host" "scp -P $dst_ssh_port \"$dump_file\" \"$dst_ssh_user@$dst_host:$dst_dump_file\"" >/dev/null 2>&1
        fi
    fi

    # 3. Restore Destination
    echo -e "${BLUE}#=== Restoring database on destination...${RESET}"
    if [[ "$dst_host" == "localhost" || "$dst_host" == "127.0.0.1" ]]; then
        eval "$cmd_restore < \"$dst_dump_file\"" 2>/dev/null
    else
        ssh -p "$dst_ssh_port" "$dst_ssh_user@$dst_host" "$cmd_restore < \"$dst_dump_file\"" 2>/dev/null
    fi

    # 4. Cleanup
    if [[ "$DB_DUMP_REMOVE" == true ]]; then
        echo -e "${BLUE}#=== Cleaning up dump files...${RESET}"
        # Remove from Source
        if [[ "$src_host" == "localhost" ]]; then
            rm -f "$dump_file"
        else
            ssh -p "$src_ssh_port" "$src_ssh_user@$src_host" "rm -f \"$dump_file\""
        fi
        
        # Remove from Destination
        if [[ "$dst_host" == "localhost" || "$dst_host" == "127.0.0.1" ]]; then
            rm -f "$dst_dump_file"
        else
            ssh -p "$dst_ssh_port" "$dst_ssh_user@$dst_host" "rm -f \"$dst_dump_file\""
        fi
    fi
    
    echo -e "  ${GREEN}✔ Database $src_db_name synced successfully${RESET}"
}
