package fileops

import (
	"crypto/sha256"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"sync"
	"time"
)

type CopyResult struct {
	BytesCopied   int64         `json:"bytes_copied"`
	Duration      time.Duration `json:"duration_ms"`
	Checksum      string        `json:"checksum"`
	TransferRate  float64       `json:"transfer_rate_mbps"`
	Success       bool          `json:"success"`
}

// CopyFile performs high-speed file copying with checksum verification
func CopyFile(source, destination string) (*CopyResult, error) {
	startTime := time.Now()
	
	// Open source file
	srcFile, err := os.Open(source)
	if err != nil {
		return nil, fmt.Errorf("failed to open source file: %w", err)
	}
	defer srcFile.Close()

	// Get source file info
	srcInfo, err := srcFile.Stat()
	if err != nil {
		return nil, fmt.Errorf("failed to get source file info: %w", err)
	}

	// Create destination directory if it doesn't exist
	destDir := filepath.Dir(destination)
	if err := os.MkdirAll(destDir, 0755); err != nil {
		return nil, fmt.Errorf("failed to create destination directory: %w", err)
	}

	// Create destination file
	destFile, err := os.Create(destination)
	if err != nil {
		return nil, fmt.Errorf("failed to create destination file: %w", err)
	}
	defer destFile.Close()

	// Use a larger buffer for better performance
	buffer := make([]byte, 1024*1024) // 1MB buffer
	
	// Create hash for checksum calculation
	hash := sha256.New()
	
	// Use MultiWriter to write to both destination and hash
	multiWriter := io.MultiWriter(destFile, hash)
	
	// Copy with custom buffer
	bytesCopied, err := io.CopyBuffer(multiWriter, srcFile, buffer)
	if err != nil {
		return nil, fmt.Errorf("failed to copy file: %w", err)
	}

	// Sync to ensure data is written to disk
	if err := destFile.Sync(); err != nil {
		return nil, fmt.Errorf("failed to sync destination file: %w", err)
	}

	// Set file permissions to match source
	if err := os.Chmod(destination, srcInfo.Mode()); err != nil {
		return nil, fmt.Errorf("failed to set file permissions: %w", err)
	}

	duration := time.Since(startTime)
	checksum := fmt.Sprintf("%x", hash.Sum(nil))
	
	// Calculate transfer rate in MB/s
	transferRate := float64(bytesCopied) / (1024 * 1024) / duration.Seconds()

	return &CopyResult{
		BytesCopied:  bytesCopied,
		Duration:     duration,
		Checksum:     checksum,
		TransferRate: transferRate,
		Success:      true,
	}, nil
}

// CopyDirectory recursively copies a directory with parallel processing
func CopyDirectory(source, destination string) (*CopyResult, error) {
	startTime := time.Now()
	var totalBytes int64
	var wg sync.WaitGroup
	var mu sync.Mutex
	var copyError error

	// Walk through source directory
	err := filepath.Walk(source, func(path string, info os.FileInfo, err error) error {
		if err != nil {
			return err
		}

		// Calculate relative path
		relPath, err := filepath.Rel(source, path)
		if err != nil {
			return err
		}
		destPath := filepath.Join(destination, relPath)

		if info.IsDir() {
			// Create directory
			return os.MkdirAll(destPath, info.Mode())
		}

		// Copy file in goroutine for parallel processing
		wg.Add(1)
		go func(src, dst string, size int64) {
			defer wg.Done()
			
			result, err := CopyFile(src, dst)
			if err != nil {
				mu.Lock()
				if copyError == nil {
					copyError = err
				}
				mu.Unlock()
				return
			}

			mu.Lock()
			totalBytes += result.BytesCopied
			mu.Unlock()
		}(path, destPath, info.Size())

		return nil
	})

	if err != nil {
		return nil, fmt.Errorf("failed to walk source directory: %w", err)
	}

	// Wait for all copy operations to complete
	wg.Wait()

	if copyError != nil {
		return nil, copyError
	}

	duration := time.Since(startTime)
	transferRate := float64(totalBytes) / (1024 * 1024) / duration.Seconds()

	return &CopyResult{
		BytesCopied:  totalBytes,
		Duration:     duration,
		TransferRate: transferRate,
		Success:      true,
	}, nil
}