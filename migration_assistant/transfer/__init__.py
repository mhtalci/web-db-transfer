"""
File transfer module for the Migration Assistant.

This module provides a comprehensive file transfer system with support for
multiple transfer methods including SSH/SCP/SFTP, FTP/FTPS, cloud storage,
rsync, and container-based transfers.
"""

from .base import TransferMethod, TransferResult, TransferProgress
from .factory import TransferMethodFactory
from .integrity import IntegrityVerifier

__all__ = [
    'TransferMethod',
    'TransferResult', 
    'TransferProgress',
    'TransferMethodFactory',
    'IntegrityVerifier'
]