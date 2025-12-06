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

# Function to check MySQL database connection
check_mysql_connection() {
    local host=$1
    local port=$2
    local user=$3
    local password=$4
    local dbname=$5
    
    # Check source MySQL connection
    if [ "$host" = "localhost" ]; then
        # Local MySQL check without SSH
        mysql -u "$user" -p"$password" -e "exit" 2>/dev/null
        if [ $? -ne 0 ]; then
            echo -e "${RED}#=== ERROR: Cannot connect to MySQL database $dbname on $host!${RESET}" >&2
            exit 1
        fi
    else
        # Remote MySQL check with SSH
        ssh -p "$port" "$SRCUSER@$host" "mysql -u \"$user\" -p\"$password\" -e \"exit\"" 2>/dev/null
        if [ $? -ne 0 ]; then
            echo -e "${RED}#=== ERROR: Cannot connect to MySQL database $dbname on $host via SSH!${RESET}" >&2
            exit 1
        fi
    fi
}

# Function to check SSH connection
check_ssh_connection() {
    local host=$1
    local port=$2
    local user=$3
    
    # Skip SSH check for local host
    if [ "$host" = "localhost" ]; then
        echo -e "${YELLOW}#=== Skipping SSH check for local host $host...${RESET}"
        return 0  # Local host doesn't need SSH check
    else
        # SSH check for remote host
        echo -e "${YELLOW}#=== Checking SSH connection to remote host $host on port $port...${RESET}"
        ssh -p "$port" "$user@$host" "exit" 2>/dev/null
    fi

    # Check SSH connection result
    if [ $? -ne 0 ]; then
        echo -e "${RED}#=== ERROR: Cannot connect via SSH to $user@$host:$port!${RESET}" >&2
        exit 1
    fi
}

# Load configuration(vars) from config_vars.sh
source ./config_var.sh

# Check required variables from config_vars.sh
check_var "SRCHOST" "$SRCHOST"
check_var "SRCSSHPORT" "$SRCSSHPORT"
check_var "SRCUSER" "$SRCUSER"
check_var "SRCDBNAME" "$SRCDBNAME"
check_var "SRCDBUSER" "$SRCDBUSER"
check_var "SRCDBPASS" "$SRCDBPASS"
check_var "SRCHOME" "$SRCHOME"
check_var "DSTHOST" "$DSTHOST"
check_var "DSTSSHPORT" "$DSTSSHPORT"
check_var "DSTUSER" "$DSTUSER"
check_var "DSTDBNAME" "$DSTDBNAME"
check_var "DSTDBUSER" "$DSTDBUSER"
check_var "DSTDBPASS" "$DSTDBPASS"
check_var "DSTHOME" "$DSTHOME"
check_var "DB_DUMP_NAME" "$DB_DUMP_NAME"

# Check multiple directories
if [ ${#SRCHOME_DIRS[@]} -eq 0 ]; then
    echo -e "${RED}#=== ERROR: SRCHOMES array is empty!${RESET}" >&2
    exit 1
fi
if [ ${#DSTHOME_DIRS[@]} -eq 0 ]; then
    echo -e "${RED}#=== ERROR: DSTHOMES array is empty!${RESET}" >&2
    exit 1
fi

# Check source MySQL database connectivity
echo -e "${YELLOW}#=== Checking source MySQL database connectivity...${RESET}"
check_mysql_connection "$SRCHOST" "$SRCSSHPORT" "$SRCDBUSER" "$SRCDBPASS" "$SRCDBNAME"

# Check destination MySQL database connectivity
echo -e "${YELLOW}#=== Checking destination MySQL database connectivity...${RESET}"
check_mysql_connection "$DSTHOST" "$DSTSSHPORT" "$DSTDBUSER" "$DSTDBPASS" "$DSTDBNAME"

# Example: Check SSH connection for the source host
check_ssh_connection "$SRCHOST" "$SRCSSHPORT" "$SRCUSER"

# Example: Check SSH connection for the destination host
check_ssh_connection "$DSTHOST" "$DSTSSHPORT" "$DSTUSER"

echo -e "${GREEN}#=== Precheck completed successfully!${RESET}"
