#!/bin/bash

# Define color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
RESET='\033[0m'  # To reset to default color

# Function to check if a variable is empty
check_var() {
    local var_name=$1
    local var_value=$2
    if [ -z "$var_value" ]; then
        echo -e "${RED}#=== ERROR: $var_name is undefined or empty!${RESET}" >&2
        exit 1
    fi
}

# Check required variables
check_var "SRCHOST" "$SRCHOST"
check_var "SRCSSHPORT" "$SRCSSHPORT"
check_var "SRCUSER" "$SRCUSER"
check_var "SRCDBNAME" "$SRCDBNAME"
check_var "SRCDBUSER" "$SRCDBUSER"
check_var "SRCDBPASS" "$SRCDBPASS"
check_var "DSTHOST" "$DSTHOST"
check_var "DSTSSHPORT" "$DSTSSHPORT"
check_var "DSTUSER" "$DSTUSER"
check_var "DSTDBNAME" "$DSTDBNAME"
check_var "DSTDBUSER" "$DSTDBUSER"
check_var "DSTDBPASS" "$DSTDBPASS"

# Check multiple directories
if [ ${#SRCHOMES[@]} -eq 0 ]; then
    echo -e "${RED}#=== ERROR: SRCHOMES array is empty!${RESET}" >&2
    exit 1
fi
if [ ${#DSTHOMES[@]} -eq 0 ]; then
    echo -e "${RED}#=== ERROR: DSTHOMES array is empty!${RESET}" >&2
    exit 1
fi

# Check database connection
if [ "$DSTHOST" = "localhost" ] || [ "$DSTHOST" = "127.0.0.1" ]; then
    if [ "$SRCHOST" = "localhost" ] || [ "$SRCHOST" = "127.0.0.1" ]; then
        # Local MySQL check without SSH
        mysql -u "$SRCDBUSER" -p"$SRCDBPASS" -e "exit" 2>/dev/null
        if [ $? -ne 0 ]; then
            echo -e "${RED}#=== ERROR: Cannot connect to source database!${RESET}" >&2
            exit 1
        fi
    else
        # Remote MySQL check with SSH
        ssh -p "$SRCSSHPORT" "$SRCUSER@$SRCHOST" "mysql -u \"$SRCDBUSER\" -p\"$SRCDBPASS\" -e \"exit\"" 2>/dev/null
        if [ $? -ne 0 ]; then
            echo -e "${RED}#=== ERROR: Cannot connect to source database via SSH!${RESET}" >&2
            exit 1
        fi
    fi
else
    # Remote MySQL check with SSH (from remote to remote)
    ssh -p "$SRCSSHPORT" "$SRCUSER@$SRCHOST" "mysql -u \"$SRCDBUSER\" -p\"$SRCDBPASS\" -e \"exit\"" 2>/dev/null
    if [ $? -ne 0 ]; then
        echo -e "${RED}#=== ERROR: Cannot connect to source database via SSH!${RESET}" >&2
        exit 1
    fi
fi

if [ "$DSTHOST" = "localhost" ] || [ "$DSTHOST" = "127.0.0.1" ]; then
    # Local MySQL check without SSH
    mysql -u "$DSTDBUSER" -p"$DSTDBPASS" -e "exit" 2>/dev/null
    if [ $? -ne 0 ]; then
        echo -e "${RED}#=== ERROR: Cannot connect to destination database!${RESET}" >&2
        exit 1
    fi
else
    # Remote MySQL check with SSH
    ssh -p "$DSTSSHPORT" "$DSTUSER@$DSTHOST" "mysql -u \"$DSTDBUSER\" -p\"$DSTDBPASS\" -e \"exit\"" 2>/dev/null
    if [ $? -ne 0 ]; then
        echo -e "${RED}#=== ERROR: Cannot connect to destination database via SSH!${RESET}" >&2
        exit 1
    fi
fi

echo -e "${GREEN}#=== Precheck completed successfully!${RESET}"

# Added newlines
echo -e "\n\n"
