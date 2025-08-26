"""Security scanning utilities for dependencies and binaries."""

import os
import subprocess
import json
import logging
import hashlib
import requests
from typing import Dict, List, Any, Optional, Set
from dataclasses import dataclass
from enum import Enum
import pkg_resources
from pathlib import Path

logger = logging.getLogger(__name__)

class VulnerabilitySeverity(Enum):
    """Vulnerability severity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

@dataclass
class Vulnerability:
    """Represents a security vulnerability."""
    id: str
    package: str
    version: str
    severity: VulnerabilitySeverity
    description: str
    fixed_version: Optional[str] = None
    cve_id: Optional[str] = None

@dataclass
class ScanResult:
    """Results of a security scan."""
    scan_type: str
    vulnerabilities: List[Vulnerability]
    total_packages: int
    scan_time: float
    success: bool
    error_message: Optional[str] = None

class SecurityScanner:
    """Performs security scanning of dependencies and binaries."""
    
    def __init__(self):
        """Initialize security scanner."""
        self.known_vulnerabilities: Dict[str, List[Vulnerability]] = {}
        self.trusted_hashes: Dict[str, str] = {}
        self._load_trusted_hashes()
    
    def _load_trusted_hashes(self):
        """Load trusted binary hashes."""
        # In a real implementation, these would be loaded from a secure source
        self.trusted_hashes = {
            "migration-engine": {
                "linux": "sha256:expected_linux_hash_here",
                "darwin": "sha256:expected_macos_hash_here", 
                "windows": "sha256:expected_windows_hash_here"
            }
        }
    
    def scan_python_dependencies(self) -> ScanResult:
        """Scan Python dependencies for known vulnerabilities.
        
        Returns:
            Scan results with any vulnerabilities found
        """
        import time
        start_time = time.time()
        
        try:
            vulnerabilities = []
            installed_packages = list(pkg_resources.working_set)
            
            logger.info(f"Scanning {len(installed_packages)} Python packages")
            
            # Check each installed package
            for package in installed_packages:
                package_vulns = self._check_package_vulnerabilities(
                    package.project_name, 
                    package.version
                )
                vulnerabilities.extend(package_vulns)
            
            scan_time = time.time() - start_time
            
            return ScanResult(
                scan_type="python_dependencies",
                vulnerabilities=vulnerabilities,
                total_packages=len(installed_packages),
                scan_time=scan_time,
                success=True
            )
            
        except Exception as e:
            logger.error(f"Python dependency scan failed: {e}")
            return ScanResult(
                scan_type="python_dependencies",
                vulnerabilities=[],
                total_packages=0,
                scan_time=time.time() - start_time,
                success=False,
                error_message=str(e)
            )
    
    def _check_package_vulnerabilities(self, package_name: str, version: str) -> List[Vulnerability]:
        """Check a specific package for vulnerabilities.
        
        Args:
            package_name: Name of the package
            version: Version of the package
            
        Returns:
            List of vulnerabilities found
        """
        vulnerabilities = []
        
        # Check against known vulnerability database
        # In a real implementation, this would query a vulnerability database
        # like the Python Advisory Database or OSV
        
        # Example vulnerability checks for common packages
        if package_name.lower() == "requests" and version < "2.31.0":
            vulnerabilities.append(Vulnerability(
                id="VULN-001",
                package=package_name,
                version=version,
                severity=VulnerabilitySeverity.MEDIUM,
                description="Potential security issue in older requests versions",
                fixed_version="2.31.0"
            ))
        
        if package_name.lower() == "cryptography" and version < "41.0.0":
            vulnerabilities.append(Vulnerability(
                id="VULN-002", 
                package=package_name,
                version=version,
                severity=VulnerabilitySeverity.HIGH,
                description="Known vulnerability in cryptography library",
                fixed_version="41.0.0",
                cve_id="CVE-2023-example"
            ))
        
        return vulnerabilities
    
    def scan_go_binary(self, binary_path: str) -> ScanResult:
        """Scan Go binary for security issues.
        
        Args:
            binary_path: Path to Go binary
            
        Returns:
            Scan results
        """
        import time
        start_time = time.time()
        
        try:
            vulnerabilities = []
            
            if not os.path.exists(binary_path):
                return ScanResult(
                    scan_type="go_binary",
                    vulnerabilities=[],
                    total_packages=0,
                    scan_time=time.time() - start_time,
                    success=False,
                    error_message=f"Binary not found: {binary_path}"
                )
            
            # Check binary hash
            binary_hash = self._calculate_file_hash(binary_path)
            binary_name = os.path.basename(binary_path)
            
            if not self._verify_binary_hash(binary_name, binary_hash):
                vulnerabilities.append(Vulnerability(
                    id="HASH-001",
                    package=binary_name,
                    version="unknown",
                    severity=VulnerabilitySeverity.CRITICAL,
                    description=f"Binary hash mismatch: {binary_hash}"
                ))
            
            # Check binary permissions
            if self._check_binary_permissions(binary_path):
                vulnerabilities.append(Vulnerability(
                    id="PERM-001",
                    package=binary_name,
                    version="unknown",
                    severity=VulnerabilitySeverity.MEDIUM,
                    description="Binary has overly permissive permissions"
                ))
            
            # Try to get Go module information
            go_modules = self._get_go_modules(binary_path)
            for module_name, module_version in go_modules.items():
                module_vulns = self._check_go_module_vulnerabilities(module_name, module_version)
                vulnerabilities.extend(module_vulns)
            
            scan_time = time.time() - start_time
            
            return ScanResult(
                scan_type="go_binary",
                vulnerabilities=vulnerabilities,
                total_packages=len(go_modules),
                scan_time=scan_time,
                success=True
            )
            
        except Exception as e:
            logger.error(f"Go binary scan failed: {e}")
            return ScanResult(
                scan_type="go_binary",
                vulnerabilities=[],
                total_packages=0,
                scan_time=time.time() - start_time,
                success=False,
                error_message=str(e)
            )
    
    def _calculate_file_hash(self, file_path: str) -> str:
        """Calculate SHA-256 hash of a file.
        
        Args:
            file_path: Path to file
            
        Returns:
            SHA-256 hash as hex string
        """
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                sha256_hash.update(chunk)
        return sha256_hash.hexdigest()
    
    def _verify_binary_hash(self, binary_name: str, actual_hash: str) -> bool:
        """Verify binary hash against trusted hashes.
        
        Args:
            binary_name: Name of binary
            actual_hash: Actual hash of binary
            
        Returns:
            True if hash is trusted, False otherwise
        """
        import platform
        
        if binary_name not in self.trusted_hashes:
            logger.warning(f"No trusted hash found for binary: {binary_name}")
            return False
        
        platform_name = platform.system().lower()
        trusted_hash_info = self.trusted_hashes[binary_name].get(platform_name)
        
        if not trusted_hash_info:
            logger.warning(f"No trusted hash for {binary_name} on {platform_name}")
            return False
        
        # Extract hash from "sha256:hash" format
        if ":" in trusted_hash_info:
            trusted_hash = trusted_hash_info.split(":", 1)[1]
        else:
            trusted_hash = trusted_hash_info
        
        return actual_hash == trusted_hash
    
    def _check_binary_permissions(self, binary_path: str) -> bool:
        """Check if binary has overly permissive permissions.
        
        Args:
            binary_path: Path to binary
            
        Returns:
            True if permissions are too permissive, False otherwise
        """
        try:
            stat_info = os.stat(binary_path)
            mode = stat_info.st_mode
            
            # Check if world-writable
            if mode & 0o002:
                return True
            
            # Check if group-writable and not owned by user
            if (mode & 0o020) and stat_info.st_uid != os.getuid():
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Failed to check permissions for {binary_path}: {e}")
            return False
    
    def _get_go_modules(self, binary_path: str) -> Dict[str, str]:
        """Extract Go module information from binary.
        
        Args:
            binary_path: Path to Go binary
            
        Returns:
            Dictionary of module names to versions
        """
        try:
            # Try to use 'go version -m' to get module info
            result = subprocess.run(
                ["go", "version", "-m", binary_path],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            modules = {}
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                for line in lines:
                    if line.strip().startswith('dep'):
                        parts = line.strip().split()
                        if len(parts) >= 3:
                            module_name = parts[1]
                            module_version = parts[2]
                            modules[module_name] = module_version
            
            return modules
            
        except Exception as e:
            logger.warning(f"Failed to extract Go modules from {binary_path}: {e}")
            return {}
    
    def _check_go_module_vulnerabilities(self, module_name: str, version: str) -> List[Vulnerability]:
        """Check Go module for vulnerabilities.
        
        Args:
            module_name: Name of Go module
            version: Version of Go module
            
        Returns:
            List of vulnerabilities found
        """
        vulnerabilities = []
        
        # Example vulnerability checks for common Go modules
        # In a real implementation, this would query the Go vulnerability database
        
        if "github.com/gin-gonic/gin" in module_name and version < "v1.9.1":
            vulnerabilities.append(Vulnerability(
                id="GO-001",
                package=module_name,
                version=version,
                severity=VulnerabilitySeverity.MEDIUM,
                description="Known vulnerability in Gin framework",
                fixed_version="v1.9.1"
            ))
        
        return vulnerabilities
    
    def scan_system_dependencies(self) -> ScanResult:
        """Scan system-level dependencies.
        
        Returns:
            Scan results
        """
        import time
        start_time = time.time()
        
        try:
            vulnerabilities = []
            
            # Check for required system tools
            required_tools = ["ssh", "rsync", "curl", "openssl"]
            missing_tools = []
            
            for tool in required_tools:
                if not self._check_tool_available(tool):
                    missing_tools.append(tool)
            
            if missing_tools:
                vulnerabilities.append(Vulnerability(
                    id="SYS-001",
                    package="system_tools",
                    version="unknown",
                    severity=VulnerabilitySeverity.MEDIUM,
                    description=f"Missing required tools: {', '.join(missing_tools)}"
                ))
            
            # Check OpenSSL version if available
            openssl_version = self._get_openssl_version()
            if openssl_version and self._is_openssl_vulnerable(openssl_version):
                vulnerabilities.append(Vulnerability(
                    id="SSL-001",
                    package="openssl",
                    version=openssl_version,
                    severity=VulnerabilitySeverity.HIGH,
                    description="Vulnerable OpenSSL version detected"
                ))
            
            scan_time = time.time() - start_time
            
            return ScanResult(
                scan_type="system_dependencies",
                vulnerabilities=vulnerabilities,
                total_packages=len(required_tools),
                scan_time=scan_time,
                success=True
            )
            
        except Exception as e:
            logger.error(f"System dependency scan failed: {e}")
            return ScanResult(
                scan_type="system_dependencies",
                vulnerabilities=[],
                total_packages=0,
                scan_time=time.time() - start_time,
                success=False,
                error_message=str(e)
            )
    
    def _check_tool_available(self, tool: str) -> bool:
        """Check if a system tool is available.
        
        Args:
            tool: Name of tool to check
            
        Returns:
            True if tool is available, False otherwise
        """
        try:
            result = subprocess.run(
                ["which", tool],
                capture_output=True,
                timeout=10
            )
            return result.returncode == 0
        except Exception:
            return False
    
    def _get_openssl_version(self) -> Optional[str]:
        """Get OpenSSL version.
        
        Returns:
            OpenSSL version string or None
        """
        try:
            result = subprocess.run(
                ["openssl", "version"],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                # Parse version from output like "OpenSSL 1.1.1f  31 Mar 2020"
                parts = result.stdout.strip().split()
                if len(parts) >= 2:
                    return parts[1]
            
            return None
            
        except Exception as e:
            logger.warning(f"Failed to get OpenSSL version: {e}")
            return None
    
    def _is_openssl_vulnerable(self, version: str) -> bool:
        """Check if OpenSSL version has known vulnerabilities.
        
        Args:
            version: OpenSSL version string
            
        Returns:
            True if version is vulnerable, False otherwise
        """
        # Example vulnerability checks
        # In a real implementation, this would check against a vulnerability database
        
        vulnerable_versions = [
            "1.0.1", "1.0.2", "1.1.0"  # Example vulnerable versions
        ]
        
        for vuln_version in vulnerable_versions:
            if version.startswith(vuln_version):
                return True
        
        return False
    
    def generate_security_report(self, scan_results: List[ScanResult]) -> Dict[str, Any]:
        """Generate comprehensive security report.
        
        Args:
            scan_results: List of scan results
            
        Returns:
            Security report dictionary
        """
        total_vulnerabilities = 0
        severity_counts = {
            VulnerabilitySeverity.LOW: 0,
            VulnerabilitySeverity.MEDIUM: 0,
            VulnerabilitySeverity.HIGH: 0,
            VulnerabilitySeverity.CRITICAL: 0
        }
        
        scan_summary = []
        all_vulnerabilities = []
        
        for result in scan_results:
            total_vulnerabilities += len(result.vulnerabilities)
            
            for vuln in result.vulnerabilities:
                severity_counts[vuln.severity] += 1
                all_vulnerabilities.append(vuln)
            
            scan_summary.append({
                "scan_type": result.scan_type,
                "success": result.success,
                "vulnerabilities_found": len(result.vulnerabilities),
                "total_packages": result.total_packages,
                "scan_time": result.scan_time,
                "error_message": result.error_message
            })
        
        # Calculate risk score
        risk_score = (
            severity_counts[VulnerabilitySeverity.CRITICAL] * 10 +
            severity_counts[VulnerabilitySeverity.HIGH] * 7 +
            severity_counts[VulnerabilitySeverity.MEDIUM] * 4 +
            severity_counts[VulnerabilitySeverity.LOW] * 1
        )
        
        return {
            "scan_timestamp": time.time(),
            "total_vulnerabilities": total_vulnerabilities,
            "risk_score": risk_score,
            "severity_breakdown": {
                "critical": severity_counts[VulnerabilitySeverity.CRITICAL],
                "high": severity_counts[VulnerabilitySeverity.HIGH],
                "medium": severity_counts[VulnerabilitySeverity.MEDIUM],
                "low": severity_counts[VulnerabilitySeverity.LOW]
            },
            "scan_summary": scan_summary,
            "vulnerabilities": [
                {
                    "id": vuln.id,
                    "package": vuln.package,
                    "version": vuln.version,
                    "severity": vuln.severity.value,
                    "description": vuln.description,
                    "fixed_version": vuln.fixed_version,
                    "cve_id": vuln.cve_id
                }
                for vuln in all_vulnerabilities
            ],
            "recommendations": self._generate_recommendations(all_vulnerabilities)
        }
    
    def _generate_recommendations(self, vulnerabilities: List[Vulnerability]) -> List[str]:
        """Generate security recommendations based on vulnerabilities.
        
        Args:
            vulnerabilities: List of vulnerabilities
            
        Returns:
            List of recommendations
        """
        recommendations = []
        
        critical_vulns = [v for v in vulnerabilities if v.severity == VulnerabilitySeverity.CRITICAL]
        if critical_vulns:
            recommendations.append("URGENT: Address critical vulnerabilities immediately")
        
        high_vulns = [v for v in vulnerabilities if v.severity == VulnerabilitySeverity.HIGH]
        if high_vulns:
            recommendations.append("Update packages with high severity vulnerabilities")
        
        # Group by package for upgrade recommendations
        packages_to_update = {}
        for vuln in vulnerabilities:
            if vuln.fixed_version:
                if vuln.package not in packages_to_update:
                    packages_to_update[vuln.package] = vuln.fixed_version
        
        if packages_to_update:
            recommendations.append("Update the following packages:")
            for package, version in packages_to_update.items():
                recommendations.append(f"  - {package} to version {version}")
        
        if not vulnerabilities:
            recommendations.append("No vulnerabilities detected - system appears secure")
        
        return recommendations