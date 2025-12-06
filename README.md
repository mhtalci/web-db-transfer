# Website and Database Transfer Script

This script automates the process of copying website files and database dumps from one server to another. It is designed to be robust, secure, and flexible, supporting local, remote, and mixed environments.

## Features

- **File Synchronization**:
  - Uses `rsync` with exclude patterns.
  - **Smart Ownership**: Automatically handles ownership (`--no-o --no-g`) to ensure destination files are owned by the current user, preventing permission lockouts.
  - **Progress Bar**: Clean, non-intrusive progress bar for file transfers.
- **Database Synchronization**:
  - Supports **MySQL/MariaDB** and **PostgreSQL**.
  - **Smart Local Transfer**: Automatically detects local-to-local transfers and pipes data directly, skipping temporary files.
  - **Non-Root Friendly**: Uses `/tmp` for temporary dumps and safe flags (like `--single-transaction`) to run without root privileges.
- **Flexible Topologies**:
  - **Local-to-Local**: Supports transferring between users on the same machine (e.g., `prod` -> `dev`) by treating `127.0.0.1` as a remote host to bypass file permission issues via SSH.
  - **Remote-to-Local** / **Local-to-Remote** / **Remote-to-Remote**.

## Prerequisites

- SSH access to source and destination servers.
- Database access credentials.
- **SSH Keys** for password-less authentication.
- **Software**: `rsync`, `mysql`/`mysqldump` (or `psql`/`pg_dump`).

## Configuration

1. Edit `config_var.sh` with your server details.
2. **Important for Local User-to-User Transfers**:
   - If transferring between two users on the same machine (e.g., `prod` user to `dev` user), set `SRCHOST=127.0.0.1` instead of `localhost`.
   - This forces the script to use SSH, allowing it to read files owned by the other user.

## Usage

1. **Pre-check** (Optional):
   ```bash
   ./precheck.sh
   ```

2. **Run Transfer**:
   ```bash
   ./transfer.sh
   ```

## SSH Keys Setup (Recommended)

To make the script run smoothly without entering passwords each time, set up SSH keys:

```bash
# Generate key
ssh-keygen -t rsa -b 4096

# Copy to remote (or localhost for user-to-user transfer)
ssh-copy-id username@remote_server
```

## License

MIT License
