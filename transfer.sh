##### SOURCE
SRCHOST=srv.example.com
SRCSSHPORT=22
SRCUSER=sshuser1
SRCDBNAME="dbname_db"
SRCDBUSER="dbuser_db"
SRCDBPASS='S3CR3TPAssW0rd'
SRCHOME=/home/sshuser1/public_html

##### DESTINATION
DSTHOST=localhost
DSTSSHPORT=22
DSTUSER="sshuser2"
DSTDBNAME="dbname_db"
DSTDBUSER="dbuser_db"
DSTDBPASS='S3CR3TPAssW0rd'
DSTHOME=/home/sshuser2/public_html

##### OPTIONS
DB_DUMP_NAME="db_backupdump.sql"
DB_DUMP_REMOVE=false

##### CREATE a timestamp
TIMESTAMP=$(date +"%A, %B %d, %Y %I:%M:%S %p")
echo $TIMESTAMP

# Start time
start_time=$(date +%s)

# Define color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
RESET='\033[0m'  # To reset to default color

echo -e "${GREEN}#=== Starting website copy from $SRCHOST to $DSTHOST...${RESET}"

# Step 1: Rsync files from source to destination/local
if [ "$DSTHOST" = "localhost" ] || [ "$DSTHOST" = "127.0.0.1" ]; then
    if [ "$SRCHOST" = "localhost" ] || [ "$SRCHOST" = "127.0.0.1" ]; then
       # Local copy without SSH
       rsync -az --info=progress2 --stats $SRCHOME/ $DSTHOME/
    else
       # Remote copy with SSH
       rsync -az --info=progress2 --stats -e "ssh -p $SRCSSHPORT" $SRCUSER@$SRCHOST:$SRCHOME/ $DSTHOME/
    fi
else
    # Remote copy with SSH on remote dest
    rsync -az --info=progress2 --stats -e "ssh -p $SRCSSHPORT" $SRCUSER@$SRCHOST:$SRCHOME/ $DSTUSER@$DSTHOST:$DSTHOME/
fi

if [ $? -eq 0 ]; then
    echo -e "${GREEN}#=== Files copied successfully to $DSTHOME${RESET}"
else
    echo -e "${RED}#===Error copying files${RESET}" >&2
    exit 1
fi

# Step 2: Dump the source database
echo -e  "${YELLOW}#=== Dumping source database...${RESET}"

if [ "$DSTHOST" = "localhost" ] || [ "$DSTHOST" = "127.0.0.1" ]; then
    if [ "$SRCHOST" = "localhost" ] || [ "$SRCHOST" = "127.0.0.1" ]; then
        # Local MySQL dump without SSH
        mysqldump --no-tablespaces -u $SRCDBUSER -p"$SRCDBPASS" $SRCDBNAME > $SRCHOME/${DB_DUMP_NAME}
    else
        # Remote MySQL dump with SSH
        ssh -p $SRCSSHPORT $SRCUSER@$SRCHOST "mysqldump --no-tablespaces -u $SRCDBUSER -p\"$SRCDBPASS\" $SRCDBNAME > $SRCHOME/${DB_DUMP_NAME}"
    fi
else
    # Remote MySQL dump with SSH (from remote to remote)
    ssh -p $SRCSSHPORT $SRCUSER@$SRCHOST "mysqldump --no-tablespaces -u $SRCDBUSER -p\"$SRCDBPASS\" $SRCDBNAME > $SRCHOME/${DB_DUMP_NAME}"
fi

# Step 3: Transfer database dump to destination/local
if [ "$DSTHOST" = "localhost" ] || [ "$DSTHOST" = "127.0.0.1" ]; then
    if [ "$SRCHOST" = "localhost" ] || [ "$SRCHOST" = "127.0.0.1" ]; then
        # Local copy of database dump without SSH
        cp $SRCHOME/${DB_DUMP_NAME} $DSTHOME/${DB_DUMP_NAME}
    else
        # Remote copy of database dump from local to remote destination
        scp -P $SRCSSHPORT $SRCUSER@$SRCHOST:$SRCHOME/${DB_DUMP_NAME} $DSTHOME/${DB_DUMP_NAME}
    fi
else
    # Remote copy of database dump from remote to remote destination
    scp -P $SRCSSHPORT $SRCUSER@$SRCHOST:$SRCHOME/${DB_DUMP_NAME} $DSTUSER@$DSTHOST:$DSTHOME/${DB_DUMP_NAME}
fi

# Step 4: Restore database on destination/local
echo -e "${YELLOW}#=== Restoring database on destination...${RESET}"
if [ "$DSTHOST" = "localhost" ] || [ "$DSTHOST" = "127.0.0.1" ]; then
    # Local restore without SSH
    mysql -u $DSTDBUSER -p"$DSTDBPASS" $DSTDBNAME < $DSTHOME/${DB_DUMP_NAME}
else
    # Remote restore with SSH (both source and destination are remote)
    ssh -p $DSTSSHPORT $DSTUSER@$DSTHOST "mysql -u $DSTDBUSER -p\"$DSTDBPASS\" $DSTDBNAME < $DSTHOME/${DB_DUMP_NAME}"
fi

# Clean up dump files if needed
echo -e "${RED}#=== $DB_DUMP_REMOVE | REMOVE DUMP db(${DB_DUMP_NAME})${RESET}"
if [ "$DB_DUMP_REMOVE" = true ]; then
    if [ "$DSTHOST" = "localhost" ] || [ "$DSTHOST" = "127.0.0.1" ]; then
        # Local removal on destination
        rm $DSTHOME/${DB_DUMP_NAME}
        echo -e "${RED}#=== REMOVED dump (${DB_DUMP_NAME})@$DSTHOST${RESET}"
    else
        # Remote removal on destination
        ssh -p $DSTSSHPORT $DSTUSER@$DSTHOST "rm $DSTHOME/${DB_DUMP_NAME}"
        echo -e "${RED}#=== REMOVED dump (${DB_DUMP_NAME})@$DSTHOST${RESET}"
    fi

    if [ "$SRCHOST" = "localhost" ] || [ "$SRCHOST" = "127.0.0.1" ]; then
        # Local removal on source
        rm $SRCHOME/${DB_DUMP_NAME}
        echo -e "${RED}#=== REMOVED dump (${DB_DUMP_NAME})@$SRCHOST${RESET}"
    else
        # Remote removal on source
        ssh -p $SRCSSHPORT $SRCUSER@$SRCHOST "rm $SRCHOME/${DB_DUMP_NAME}"
        echo -e "${RED}#=== REMOVED dump (${DB_DUMP_NAME})@$SRCHOST${RESET}"
    fi
fi

# End time
end_time=$(date +%s)
# Calculate duration
duration=$((end_time - start_time))

echo -e "${GREEN}#=== Website and database copy completed successfully in $duration seconds.${RESET}"
