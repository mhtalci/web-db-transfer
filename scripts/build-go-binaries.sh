#!/bin/bash

# Build script for Go binaries across platforms (Linux, macOS, Windows)
# This script builds the migration-engine Go binary for multiple platforms

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
GO_MODULE_PATH="go-engine"
BINARY_NAME="migration-engine"
OUTPUT_DIR="migration_assistant/bin"
VERSION=${VERSION:-$(git describe --tags --always --dirty 2>/dev/null || echo "dev")}
BUILD_TIME=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
GIT_COMMIT=${GIT_COMMIT:-$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")}

# Build flags
LDFLAGS="-s -w -X main.version=${VERSION} -X main.buildTime=${BUILD_TIME} -X main.gitCommit=${GIT_COMMIT}"
GCFLAGS="-l=4"  # Aggressive inlining for performance

# Supported platforms
declare -A PLATFORMS=(
    ["linux/amd64"]="linux-amd64"
    ["linux/arm64"]="linux-arm64"
    ["darwin/amd64"]="darwin-amd64"
    ["darwin/arm64"]="darwin-arm64"
    ["windows/amd64"]="windows-amd64.exe"
    ["windows/arm64"]="windows-arm64.exe"
)

print_header() {
    echo -e "${BLUE}================================${NC}"
    echo -e "${BLUE}  Go Binary Build Script${NC}"
    echo -e "${BLUE}================================${NC}"
    echo -e "Version: ${GREEN}${VERSION}${NC}"
    echo -e "Build Time: ${GREEN}${BUILD_TIME}${NC}"
    echo -e "Git Commit: ${GREEN}${GIT_COMMIT}${NC}"
    echo ""
}

check_prerequisites() {
    echo -e "${YELLOW}Checking prerequisites...${NC}"
    
    # Check if Go is installed
    if ! command -v go &> /dev/null; then
        echo -e "${RED}Error: Go is not installed or not in PATH${NC}"
        echo "Please install Go 1.21 or later from https://golang.org/dl/"
        exit 1
    fi
    
    # Check Go version
    GO_VERSION=$(go version | awk '{print $3}' | sed 's/go//')
    REQUIRED_VERSION="1.21"
    if ! printf '%s\n%s\n' "$REQUIRED_VERSION" "$GO_VERSION" | sort -V -C; then
        echo -e "${RED}Error: Go version $GO_VERSION is too old. Required: $REQUIRED_VERSION or later${NC}"
        exit 1
    fi
    
    echo -e "${GREEN}✓ Go version $GO_VERSION${NC}"
    
    # Check if Go module exists
    if [ ! -f "$GO_MODULE_PATH/go.mod" ]; then
        echo -e "${RED}Error: Go module not found at $GO_MODULE_PATH/go.mod${NC}"
        exit 1
    fi
    
    echo -e "${GREEN}✓ Go module found${NC}"
    
    # Create output directory
    mkdir -p "$OUTPUT_DIR"
    echo -e "${GREEN}✓ Output directory created: $OUTPUT_DIR${NC}"
    echo ""
}

build_binary() {
    local platform=$1
    local output_name=$2
    local goos=$(echo $platform | cut -d'/' -f1)
    local goarch=$(echo $platform | cut -d'/' -f2)
    local output_path="$OUTPUT_DIR/$BINARY_NAME-$output_name"
    
    echo -e "${YELLOW}Building for $platform...${NC}"
    
    cd "$GO_MODULE_PATH"
    
    # Set environment variables
    export GOOS=$goos
    export GOARCH=$goarch
    export CGO_ENABLED=0  # Disable CGO for static binaries
    
    # Build the binary
    if go build -ldflags="$LDFLAGS" -gcflags="$GCFLAGS" -o "../$output_path" ./cmd/migration-engine; then
        # Get file size
        if [ "$goos" = "windows" ]; then
            size=$(stat -c%s "../$output_path" 2>/dev/null || echo "unknown")
        else
            size=$(stat -f%z "../$output_path" 2>/dev/null || stat -c%s "../$output_path" 2>/dev/null || echo "unknown")
        fi
        
        if [ "$size" != "unknown" ]; then
            size_mb=$(echo "scale=2; $size / 1024 / 1024" | bc 2>/dev/null || echo "unknown")
            echo -e "${GREEN}✓ Built: $output_path (${size_mb}MB)${NC}"
        else
            echo -e "${GREEN}✓ Built: $output_path${NC}"
        fi
    else
        echo -e "${RED}✗ Failed to build for $platform${NC}"
        cd ..
        return 1
    fi
    
    cd ..
}

create_default_symlink() {
    local current_os=$(uname -s | tr '[:upper:]' '[:lower:]')
    local current_arch=$(uname -m)
    
    # Map architecture names
    case $current_arch in
        x86_64) current_arch="amd64" ;;
        aarch64|arm64) current_arch="arm64" ;;
    esac
    
    # Map OS names
    case $current_os in
        darwin) current_os="darwin" ;;
        linux) current_os="linux" ;;
        mingw*|msys*|cygwin*) current_os="windows" ;;
    esac
    
    local default_binary="$BINARY_NAME-$current_os-$current_arch"
    if [ "$current_os" = "windows" ]; then
        default_binary="$default_binary.exe"
    fi
    
    local default_path="$OUTPUT_DIR/$default_binary"
    local symlink_path="$OUTPUT_DIR/$BINARY_NAME"
    
    if [ -f "$default_path" ]; then
        # Remove existing symlink/file
        rm -f "$symlink_path"
        
        # Create symlink (or copy on Windows)
        if [ "$current_os" = "windows" ]; then
            cp "$default_path" "$symlink_path.exe"
            echo -e "${GREEN}✓ Created default binary: $symlink_path.exe${NC}"
        else
            ln -s "$(basename "$default_path")" "$symlink_path"
            echo -e "${GREEN}✓ Created default symlink: $symlink_path -> $default_binary${NC}"
        fi
    else
        echo -e "${YELLOW}⚠ Default binary for current platform not found: $default_path${NC}"
    fi
}

run_tests() {
    echo -e "${YELLOW}Running Go tests...${NC}"
    cd "$GO_MODULE_PATH"
    
    if go test -v ./...; then
        echo -e "${GREEN}✓ All tests passed${NC}"
    else
        echo -e "${RED}✗ Some tests failed${NC}"
        cd ..
        return 1
    fi
    
    cd ..
}

generate_checksums() {
    echo -e "${YELLOW}Generating checksums...${NC}"
    
    cd "$OUTPUT_DIR"
    
    # Generate SHA256 checksums
    if command -v sha256sum &> /dev/null; then
        sha256sum $BINARY_NAME-* > checksums.sha256
    elif command -v shasum &> /dev/null; then
        shasum -a 256 $BINARY_NAME-* > checksums.sha256
    else
        echo -e "${YELLOW}⚠ No SHA256 utility found, skipping checksums${NC}"
        cd ..
        return 0
    fi
    
    echo -e "${GREEN}✓ Checksums generated: checksums.sha256${NC}"
    cd ..
}

create_build_info() {
    local build_info_file="$OUTPUT_DIR/build-info.json"
    
    echo -e "${YELLOW}Creating build info...${NC}"
    
    cat > "$build_info_file" << EOF
{
  "version": "$VERSION",
  "build_time": "$BUILD_TIME",
  "git_commit": "$GIT_COMMIT",
  "go_version": "$(go version | awk '{print $3}')",
  "platforms": [
$(for platform in "${!PLATFORMS[@]}"; do
    echo "    \"$platform\""
    if [ "$platform" != "${!PLATFORMS[@]: -1}" ]; then
        echo ","
    fi
done)
  ],
  "binaries": [
$(for platform in "${!PLATFORMS[@]}"; do
    output_name="${PLATFORMS[$platform]}"
    echo "    {"
    echo "      \"platform\": \"$platform\","
    echo "      \"filename\": \"$BINARY_NAME-$output_name\","
    echo "      \"path\": \"$OUTPUT_DIR/$BINARY_NAME-$output_name\""
    echo "    }"
    if [ "$platform" != "${!PLATFORMS[@]: -1}" ]; then
        echo ","
    fi
done)
  ]
}
EOF
    
    echo -e "${GREEN}✓ Build info created: $build_info_file${NC}"
}

cleanup() {
    echo -e "${YELLOW}Cleaning up...${NC}"
    
    # Clean Go module cache if requested
    if [ "$CLEAN_CACHE" = "true" ]; then
        cd "$GO_MODULE_PATH"
        go clean -modcache
        cd ..
        echo -e "${GREEN}✓ Go module cache cleaned${NC}"
    fi
    
    # Remove old binaries if requested
    if [ "$CLEAN_OLD" = "true" ]; then
        find "$OUTPUT_DIR" -name "$BINARY_NAME-*" -mtime +7 -delete 2>/dev/null || true
        echo -e "${GREEN}✓ Old binaries cleaned${NC}"
    fi
}

main() {
    print_header
    check_prerequisites
    
    # Run tests if requested
    if [ "$RUN_TESTS" = "true" ]; then
        run_tests || exit 1
        echo ""
    fi
    
    # Build binaries for all platforms
    echo -e "${YELLOW}Building binaries for all platforms...${NC}"
    echo ""
    
    local failed_builds=()
    
    for platform in "${!PLATFORMS[@]}"; do
        output_name="${PLATFORMS[$platform]}"
        if ! build_binary "$platform" "$output_name"; then
            failed_builds+=("$platform")
        fi
    done
    
    echo ""
    
    # Report results
    if [ ${#failed_builds[@]} -eq 0 ]; then
        echo -e "${GREEN}✓ All binaries built successfully!${NC}"
    else
        echo -e "${YELLOW}⚠ Some builds failed:${NC}"
        for platform in "${failed_builds[@]}"; do
            echo -e "${RED}  ✗ $platform${NC}"
        done
    fi
    
    echo ""
    
    # Create default symlink for current platform
    create_default_symlink
    
    # Generate checksums
    generate_checksums
    
    # Create build info
    create_build_info
    
    # Cleanup if requested
    if [ "$CLEANUP" = "true" ]; then
        cleanup
    fi
    
    echo ""
    echo -e "${GREEN}Build completed!${NC}"
    echo -e "Binaries are available in: ${BLUE}$OUTPUT_DIR${NC}"
    
    # List built binaries
    echo ""
    echo -e "${YELLOW}Built binaries:${NC}"
    ls -la "$OUTPUT_DIR/$BINARY_NAME"* 2>/dev/null || echo "No binaries found"
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --clean-cache)
            CLEAN_CACHE="true"
            shift
            ;;
        --clean-old)
            CLEAN_OLD="true"
            shift
            ;;
        --cleanup)
            CLEANUP="true"
            shift
            ;;
        --run-tests)
            RUN_TESTS="true"
            shift
            ;;
        --version)
            VERSION="$2"
            shift 2
            ;;
        --help|-h)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --clean-cache    Clean Go module cache after build"
            echo "  --clean-old      Remove old binaries (older than 7 days)"
            echo "  --cleanup        Run cleanup tasks"
            echo "  --run-tests      Run tests before building"
            echo "  --version VER    Set version string"
            echo "  --help, -h       Show this help message"
            echo ""
            echo "Environment variables:"
            echo "  VERSION          Version string (default: git describe)"
            echo "  GIT_COMMIT       Git commit hash (default: git rev-parse)"
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Run main function
main