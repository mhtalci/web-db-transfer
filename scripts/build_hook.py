#!/usr/bin/env python3
"""
Build hook for packaging the Migration Assistant.

This script is called during the build process to:
1. Build Go binaries for multiple platforms
2. Include Go binaries in the package
3. Generate version information
4. Prepare documentation
"""

import os
import sys
import subprocess
import shutil
import json
from pathlib import Path
from typing import Dict, Any

from hatchling.plugin import hookimpl


class BuildHook:
    """Custom build hook for Migration Assistant packaging."""
    
    def __init__(self, root: str, config: Dict[str, Any]):
        self.root = Path(root)
        self.config = config
        self.go_module_path = self.root / "go-engine"
        self.bin_dir = self.root / "migration_assistant" / "bin"
        
    def initialize(self, version: str, build_data: Dict[str, Any]) -> None:
        """Initialize the build process."""
        print(f"🚀 Initializing Migration Assistant build (version: {version})")
        
        # Ensure bin directory exists
        self.bin_dir.mkdir(parents=True, exist_ok=True)
        
        # Build Go binaries if Go is available
        if self._check_go_available():
            self._build_go_binaries(version)
        else:
            print("⚠️  Go not available, skipping Go binary build")
            
        # Generate build metadata
        self._generate_build_metadata(version, build_data)
        
        print("✅ Build initialization completed")
    
    def _check_go_available(self) -> bool:
        """Check if Go is available and version is sufficient."""
        try:
            result = subprocess.run(
                ["go", "version"], 
                capture_output=True, 
                text=True, 
                check=True
            )
            version_str = result.stdout.strip()
            print(f"📦 Found Go: {version_str}")
            
            # Extract version number
            version_parts = version_str.split()
            if len(version_parts) >= 3:
                go_version = version_parts[2].replace("go", "")
                # Simple version check (should be 1.21+)
                major, minor = map(int, go_version.split(".")[:2])
                if major > 1 or (major == 1 and minor >= 21):
                    return True
                else:
                    print(f"⚠️  Go version {go_version} is too old (need 1.21+)")
                    return False
            
            return True
            
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False
    
    def _build_go_binaries(self, version: str) -> None:
        """Build Go binaries for multiple platforms."""
        print("🔨 Building Go binaries...")
        
        if not self.go_module_path.exists():
            print("⚠️  Go module not found, skipping Go binary build")
            return
        
        # Platforms to build for
        platforms = {
            "linux/amd64": "linux-amd64",
            "linux/arm64": "linux-arm64", 
            "darwin/amd64": "darwin-amd64",
            "darwin/arm64": "darwin-arm64",
            "windows/amd64": "windows-amd64.exe",
        }
        
        # Build settings
        ldflags = f"-s -w -X main.version={version}"
        gcflags = "-l=4"  # Aggressive inlining
        
        built_binaries = []
        
        for platform, output_name in platforms.items():
            goos, goarch = platform.split("/")
            output_path = self.bin_dir / f"migration-engine-{output_name}"
            
            print(f"  📦 Building for {platform}...")
            
            env = os.environ.copy()
            env.update({
                "GOOS": goos,
                "GOARCH": goarch,
                "CGO_ENABLED": "0",  # Static binaries
            })
            
            try:
                subprocess.run([
                    "go", "build",
                    f"-ldflags={ldflags}",
                    f"-gcflags={gcflags}",
                    "-o", str(output_path),
                    "./cmd/migration-engine"
                ], 
                cwd=self.go_module_path,
                env=env,
                check=True,
                capture_output=True
                )
                
                # Check if binary was created and get size
                if output_path.exists():
                    size_mb = output_path.stat().st_size / (1024 * 1024)
                    print(f"    ✅ Built: {output_path.name} ({size_mb:.2f}MB)")
                    built_binaries.append({
                        "platform": platform,
                        "filename": output_path.name,
                        "size_bytes": output_path.stat().st_size
                    })
                else:
                    print(f"    ❌ Failed: {output_path.name}")
                    
            except subprocess.CalledProcessError as e:
                print(f"    ❌ Build failed for {platform}: {e}")
                continue
        
        # Create default symlink for current platform
        self._create_default_binary_link()
        
        # Save build info
        build_info = {
            "version": version,
            "go_binaries": built_binaries,
            "total_binaries": len(built_binaries)
        }
        
        build_info_path = self.bin_dir / "build-info.json"
        with open(build_info_path, "w") as f:
            json.dump(build_info, f, indent=2)
        
        print(f"✅ Built {len(built_binaries)} Go binaries")
    
    def _create_default_binary_link(self) -> None:
        """Create default binary link for current platform."""
        import platform
        
        system = platform.system().lower()
        machine = platform.machine().lower()
        
        # Map architecture names
        if machine in ["x86_64", "amd64"]:
            arch = "amd64"
        elif machine in ["aarch64", "arm64"]:
            arch = "arm64"
        else:
            print(f"⚠️  Unknown architecture: {machine}")
            return
        
        # Map system names
        if system == "darwin":
            system = "darwin"
        elif system == "linux":
            system = "linux"
        elif system == "windows":
            system = "windows"
        else:
            print(f"⚠️  Unknown system: {system}")
            return
        
        # Find the appropriate binary
        if system == "windows":
            binary_name = f"migration-engine-{system}-{arch}.exe"
            default_name = "migration-engine.exe"
        else:
            binary_name = f"migration-engine-{system}-{arch}"
            default_name = "migration-engine"
        
        binary_path = self.bin_dir / binary_name
        default_path = self.bin_dir / default_name
        
        if binary_path.exists():
            # Remove existing default
            if default_path.exists():
                default_path.unlink()
            
            # Create symlink or copy
            try:
                if system == "windows":
                    shutil.copy2(binary_path, default_path)
                else:
                    default_path.symlink_to(binary_name)
                print(f"✅ Created default binary: {default_name}")
            except OSError as e:
                print(f"⚠️  Could not create default binary link: {e}")
    
    def _generate_build_metadata(self, version: str, build_data: Dict[str, Any]) -> None:
        """Generate build metadata."""
        import datetime
        
        metadata = {
            "version": version,
            "build_time": datetime.datetime.utcnow().isoformat() + "Z",
            "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            "platform": {
                "system": sys.platform,
                "architecture": subprocess.check_output(["uname", "-m"], text=True).strip() if sys.platform != "win32" else "unknown"
            },
            "build_data": build_data
        }
        
        # Try to get git information
        try:
            git_commit = subprocess.check_output(
                ["git", "rev-parse", "--short", "HEAD"],
                cwd=self.root,
                text=True
            ).strip()
            metadata["git_commit"] = git_commit
        except (subprocess.CalledProcessError, FileNotFoundError):
            metadata["git_commit"] = "unknown"
        
        # Save metadata
        metadata_path = self.root / "migration_assistant" / "build_metadata.json"
        with open(metadata_path, "w") as f:
            json.dump(metadata, f, indent=2)
        
        print(f"✅ Generated build metadata: {metadata_path}")


@hookimpl
def hatch_build_hook(root: str, config: Dict[str, Any]) -> None:
    """Hatch build hook entry point."""
    hook = BuildHook(root, config)
    
    # Get version from environment or default
    version = os.environ.get("HATCH_BUILD_VERSION", "1.0.0")
    
    # Initialize build
    hook.initialize(version, config)


if __name__ == "__main__":
    # Allow running as standalone script for testing
    import argparse
    
    parser = argparse.ArgumentParser(description="Migration Assistant build hook")
    parser.add_argument("--version", default="1.0.0", help="Version to build")
    parser.add_argument("--root", default=".", help="Root directory")
    
    args = parser.parse_args()
    
    hook = BuildHook(args.root, {})
    hook.initialize(args.version, {})