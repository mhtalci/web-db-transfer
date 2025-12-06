#!/bin/bash

# Source the config file to include the variables
source ./config_var.sh

# Now, you can use the variables from config.sh in your transfer.sh script
echo "Starting transfer from $SRCHOST to $DSTHOST..."

# Start time
start_time=$(date +%s)

# Define color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
RESET='\033[0m'  # To reset to default color

# Include pre-check script (if necessary)
source ./precheck.sh

echo -e "${GREEN}#=== Starting website copy from $SRCHOST to $DSTHOST...${RESET}"
# Step 1: Rsync files from source to destination/local
# Loop through source directories and copy to destination
for i in "${!SRCHOME_DIRS[@]}"; do
    SRCHOME_DIR=${SRCHOME_DIRS[$i]}
    DSTHOME_DIR=${DSTHOME_DIRS[$i]}
    echo -e "${BLUE}#=== Copying from $SRCHOME/$SRCHOME_DIR to $DSTHOME/$DSTHOME_DIR...${RESET}"

    # Initialize rsync exclude option
    RSYNC_EXCLUDE_OPTION=""

    # Check if there are exclusions for this source directory
    if [ -n "${EXCLUDE_MAP[$SRCHOME_DIR]}" ]; then
        # Add exclusions for the specific source directory
        for exclude in ${EXCLUDE_MAP[$SRCHOME_DIR]}; do
            RSYNC_EXCLUDE_OPTION="$RSYNC_EXCLUDE_OPTION --exclude=$exclude"
        done
    fi

    # Determine the source and destination based on whether they are local or remote
    # We suppress detailed stats (-q) but keep progress (-P or --info=progress2) if interactive, 
    # but for a clean script output, we'll hide the wall of text and just show the result.
    
    if [ "$DSTHOST" = "localhost" ] || [ "$DSTHOST" = "127.0.0.1" ]; then
        if [ "$SRCHOST" = "localhost" ]; then
            # Local copy without SSH
            rsync -az --no-o --no-g --info=progress2 $RSYNC_EXCLUDE_OPTION "$SRCHOME/$SRCHOME_DIR/" "$DSTHOME/$DSTHOME_DIR/"
        else
            # Remote copy with SSH
            rsync -az --no-o --no-g --info=progress2 -e "ssh -p $SRCSSHPORT" $RSYNC_EXCLUDE_OPTION "$SRCUSER@$SRCHOST:$SRCHOME/$SRCHOME_DIR/" "$DSTHOME/$DSTHOME_DIR/"
        fi
    else
        # Remote copy with SSH on remote destination
        rsync -az --no-o --no-g --info=progress2 -e "ssh -p $SRCSSHPORT" $RSYNC_EXCLUDE_OPTION "$SRCUSER@$SRCHOST:$SRCHOME/$SRCHOME_DIR/" "$DSTUSER@$DSTHOST:$DSTHOME/$DSTHOME_DIR/"
    fi

    if [ $? -eq 0 ]; then
        echo -e "  ${GREEN}✔ Success${RESET}"
    else
        echo -e "  ${RED}✘ Failed${RESET}" >&2
        exit 1
    fi
done

# Step 2: Database Synchronization
source ./db_sync.sh

# Call the sync function (uses defaults from config_var.sh)
# To sync a different database, pass arguments:
# sync_database "src_host" "src_port" ...
sync_database

# End time
end_time=$(date +%s)
# Calculate duration
duration=$((end_time - start_time))

echo -e "${GREEN}#=== Website and database copy completed successfully in $duration seconds.${RESET}"
