```bash
git clone https://github.com/mhtalci/web-db-transfer.git
cd web-db-transfer
chmod +x transfer.sh
```
# Website and Database Transfer Script

This script automates the process of copying website files and database dumps from one server to another using `rsync` for files and `mysqldump` for the database.

## Prerequisites

- SSH access to both source and destination servers.
- MySQL/MariaDB access credentials for both source and destination databases.
- **SSH Keys** for password-less authentication.

## SSH Keys Setup (Recommended)

To make the script run smoothly without entering passwords each time, it's recommended to set up SSH keys for authentication between your local and remote servers.

### Step 1: Generate SSH Keys

If you don't already have an SSH key pair, you can generate one using the following command:

```bash
ssh-keygen -t rsa -b 4096 -C "your_email@example.com"
```

This will generate a public and private key pair. You will be prompted to enter a file to save the key (you can accept the default location) and an optional passphrase.

By default, the key pair will be saved in:
~/.ssh/id_rsa (private key)
~/.ssh/id_rsa.pub (public key)

### Step 2: Copy Public Key to Remote Servers

Next, you need to copy your public key (~/.ssh/id_rsa.pub) to both the source and destination servers. This can be done using the ssh-copy-id command:
```bash
ssh-copy-id -i ~/.ssh/id_rsa.pub username@remote_server
```
Replace username with your SSH username and remote_server with the actual server’s address (IP or hostname). This command will prompt you for the password of the remote server, and once it’s entered, it will copy your public key to the remote server’s ~/.ssh/authorized_keys file.

### Step 3: Test SSH Connection

After copying your public key to the remote servers, you can test the SSH connection to ensure password-less login is working:
```bash
ssh username@remote_server
```
If everything is set up correctly, you should be logged in without being prompted for a password.

### Step 4: Update the Script for SSH Key Authentication(optional)

Once your SSH keys are set up, the script will automatically use them for authentication when connecting to the remote servers, assuming the private key is located in ~/.ssh/id_rsa (default location).

If you have stored your SSH key in a different location, you can specify the key path in the script. For example, update the rsync command in the script like this:
```bash
rsync -az --info=progress2 --stats -e "ssh -i /path/to/your/private_key -p $SRCSSHPORT" $SRCUSER@$SRCHOST:$SRCHOME/ $DSTUSER@$DSTHOST:$DSTHOME/
```

This will allow you to use a custom private key file for the transfer.

## How to Use the Script:
- Clone or download the repository to your local machine.
- Update the variables in the script (SRCHOST, DSTHOST, SRCUSER, DSTUSER, etc.) with the correct server details.
- Make the script executable:
```bash
 chmod +x transfer.sh
```
This will:
- Copy website files from the source server to the destination server using rsync.
- Dump the source database and transfer the dump to the destination server.
- Restore the database on the destination server.
The script uses SSH keys for secure, password-less authentication.

## Example Configuration

In this example, the script is set to transfer files and databases from a source server (srv.example.com) to a local destination (localhost).

### Source Server Configuration:
```bash
##### SOURCE
SRCHOST=srv.example.com
SRCSSHPORT=22
SRCUSER=sshuser1
SRCDBNAME="dbname_db"
SRCDBUSER="dbuser_db"
SRCHOME=/home/sshuser1/public_html
SRCDBPASS='S3CR3TPAssW0rd'
```
### Destination Server Configuration:
```bash
##### DESTINATION
DSTHOST=localhost
DSTSSHPORT=22
DSTUSER="sshuser2"
DSTDBNAME="dbname_db"
DSTDBUSER="dbname_db"
DSTHOME=/home/sshuser2/public_html
DSTDBPASS='S3CR3TPAssW0rd'
```
### Options:
```bash
##### OPTIONS
DB_DUMP_NAME="db_backupdump.sql"
DB_DUMP_REMOVE=false
```

Once you have configured the variables above in the script, you can run it as follows:
```bash
bash transfer.sh
```

- Customize the variables in the script (e.g., source and destination server details).
- Run the script on your server.

## License

MIT License
