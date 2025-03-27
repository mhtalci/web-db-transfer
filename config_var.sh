##### config.sh

##### SOURCE CONFIGURATION
SRCHOST=srv.example.com      # The source host (e.g., the server where the files are located)
SRCSSHPORT=22                # The SSH port on the source host
SRCUSER="sshuser1"           # SSH username on the source host
SRCDBNAME="dbname_db"        # Name of the database on the source host
SRCDBUSER="dbuser_db"        # Username for the source database
SRCDBPASS='S3CR3TPAssW0rd'   # Password for the source database

# Map of exclusion files for each source directory (e.g., *.log, *.bak)
# If no exclusions are needed for a directory, leave it unset (empty string or not defined)
declare -A EXCLUDE_MAP
EXCLUDE_MAP["public_html"]="*.log *.bak"  # Exclusions for public_html directory
EXCLUDE_MAP["App"]="*.tmp"               # Exclusions for App directory
# EXCLUDE_MAP["New_folder"]=""            # No exclusions for New_folder directory (can be commented out if not needed)

##### DESTINATION CONFIGURATION
DSTHOST=localhost             # The destination host (e.g., where files will be copied to)
DSTSSHPORT=22                 # The SSH port on the destination host
DSTUSER="sshuser2"            # SSH username on the destination host
DSTDBNAME="dbname_db"         # Name of the database on the destination host
DSTDBUSER="dbuser_db"         # Username for the destination database
DSTDBPASS='S3CR3TPAssW0rd'    # Password for the destination database

#####

# Base directory where the directories reside on the source host
SRCHOME="/home/sshuser1/"
# Additional directories to copy inside SRCHOME (directories to be copied)
SRCHOME_DIRS=("public_html" "App" "New_folder")

# Base directory where the directories reside on the destination host
DSTHOME="/home/sshuser2/"
# Additional directories to copy inside DSTHOME (directories to be copied)
DSTHOME_DIRS=("public_html" "App" "New_folder")

##### OPTIONS
DB_DUMP_NAME="db_backupdump.sql"  # Name of the database dump file
DB_DUMP_REMOVE=false              # Flag to decide if the dump file should be removed after restore

##### EXCLUDED FILES/DIR (optional)
# EXCLUDE_FILES="*.log *.tmp *temp /path/to/exclude/dir"  # Global exclusions (applies to all directories if no specific exclusion is set)
