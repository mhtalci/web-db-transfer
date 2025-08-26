package network

import (
	"fmt"
	"io"
	"net/http"
	"net/url"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"time"
)

type TransferResult struct {
	BytesTransferred int64         `json:"bytes_transferred"`
	Duration         time.Duration `json:"duration_ms"`
	TransferRate     float64       `json:"transfer_rate_mbps"`
	Method           string        `json:"method"`
	Success          bool          `json:"success"`
	Error            string        `json:"error,omitempty"`
}

type TransferConfig struct {
	ChunkSize       int           `json:"chunk_size"`
	MaxConcurrency  int           `json:"max_concurrency"`
	Timeout         time.Duration `json:"timeout"`
	RetryAttempts   int           `json:"retry_attempts"`
	RetryDelay      time.Duration `json:"retry_delay"`
}

// DefaultTransferConfig returns default transfer configuration
func DefaultTransferConfig() *TransferConfig {
	return &TransferConfig{
		ChunkSize:      1024 * 1024, // 1MB chunks
		MaxConcurrency: 4,
		Timeout:        30 * time.Second,
		RetryAttempts:  3,
		RetryDelay:     time.Second,
	}
}

// Transfer performs network transfer operations
func Transfer(source, destination, method string) (*TransferResult, error) {
	startTime := time.Now()
	config := DefaultTransferConfig()

	var result *TransferResult
	var err error

	switch strings.ToLower(method) {
	case "http", "https":
		result, err = httpTransfer(source, destination, config)
	case "concurrent":
		result, err = concurrentTransfer(source, destination, config)
	case "chunked":
		result, err = chunkedTransfer(source, destination, config)
	default:
		return nil, fmt.Errorf("unsupported transfer method: %s", method)
	}

	if err != nil {
		return &TransferResult{
			Duration: time.Since(startTime),
			Method:   method,
			Success:  false,
			Error:    err.Error(),
		}, nil
	}

	result.Duration = time.Since(startTime)
	result.Method = method
	result.Success = true

	// Calculate transfer rate in MB/s
	if result.Duration.Seconds() > 0 {
		result.TransferRate = float64(result.BytesTransferred) / (1024 * 1024) / result.Duration.Seconds()
	}

	return result, nil
}

// httpTransfer performs HTTP-based file transfer
func httpTransfer(source, destination string, config *TransferConfig) (*TransferResult, error) {
	// Parse source URL
	sourceURL, err := url.Parse(source)
	if err != nil {
		return nil, fmt.Errorf("invalid source URL: %w", err)
	}

	// Create HTTP client with timeout
	client := &http.Client{
		Timeout: config.Timeout,
	}

	// Create destination file
	destFile, err := os.Create(destination)
	if err != nil {
		return nil, fmt.Errorf("failed to create destination file: %w", err)
	}
	defer destFile.Close()

	var bytesTransferred int64

	// Retry logic
	for attempt := 0; attempt <= config.RetryAttempts; attempt++ {
		if attempt > 0 {
			time.Sleep(config.RetryDelay * time.Duration(attempt))
		}

		// Create request
		req, err := http.NewRequest("GET", sourceURL.String(), nil)
		if err != nil {
			if attempt == config.RetryAttempts {
				return nil, fmt.Errorf("failed to create request: %w", err)
			}
			continue
		}

		// Execute request
		resp, err := client.Do(req)
		if err != nil {
			if attempt == config.RetryAttempts {
				return nil, fmt.Errorf("failed to execute request: %w", err)
			}
			continue
		}

		if resp.StatusCode != http.StatusOK {
			resp.Body.Close()
			if attempt == config.RetryAttempts {
				return nil, fmt.Errorf("HTTP error: %s", resp.Status)
			}
			continue
		}

		// Copy response body to destination file
		bytesTransferred, err = io.Copy(destFile, resp.Body)
		resp.Body.Close()

		if err != nil {
			if attempt == config.RetryAttempts {
				return nil, fmt.Errorf("failed to copy response: %w", err)
			}
			continue
		}

		// Success
		break
	}

	return &TransferResult{
		BytesTransferred: bytesTransferred,
	}, nil
}

// concurrentTransfer performs concurrent file transfer for multiple files
func concurrentTransfer(source, destination string, config *TransferConfig) (*TransferResult, error) {
	// Check if source is a directory
	sourceInfo, err := os.Stat(source)
	if err != nil {
		return nil, fmt.Errorf("failed to stat source: %w", err)
	}

	if !sourceInfo.IsDir() {
		// Single file transfer
		return singleFileTransfer(source, destination)
	}

	// Directory transfer with concurrency
	var files []string
	err = filepath.Walk(source, func(path string, info os.FileInfo, err error) error {
		if err != nil {
			return err
		}
		if !info.IsDir() {
			files = append(files, path)
		}
		return nil
	})

	if err != nil {
		return nil, fmt.Errorf("failed to walk source directory: %w", err)
	}

	// Create semaphore for concurrency control
	semaphore := make(chan struct{}, config.MaxConcurrency)
	var wg sync.WaitGroup
	var mu sync.Mutex
	var totalBytes int64
	var transferError error

	for _, file := range files {
		wg.Add(1)
		go func(srcFile string) {
			defer wg.Done()

			// Acquire semaphore
			semaphore <- struct{}{}
			defer func() { <-semaphore }()

			// Calculate destination path
			relPath, err := filepath.Rel(source, srcFile)
			if err != nil {
				mu.Lock()
				if transferError == nil {
					transferError = err
				}
				mu.Unlock()
				return
			}
			destPath := filepath.Join(destination, relPath)

			// Transfer file
			result, err := singleFileTransfer(srcFile, destPath)
			if err != nil {
				mu.Lock()
				if transferError == nil {
					transferError = err
				}
				mu.Unlock()
				return
			}

			mu.Lock()
			totalBytes += result.BytesTransferred
			mu.Unlock()
		}(file)
	}

	wg.Wait()

	if transferError != nil {
		return nil, transferError
	}

	return &TransferResult{
		BytesTransferred: totalBytes,
	}, nil
}

// chunkedTransfer performs chunked file transfer
func chunkedTransfer(source, destination string, config *TransferConfig) (*TransferResult, error) {
	sourceFile, err := os.Open(source)
	if err != nil {
		return nil, fmt.Errorf("failed to open source file: %w", err)
	}
	defer sourceFile.Close()

	destFile, err := os.Create(destination)
	if err != nil {
		return nil, fmt.Errorf("failed to create destination file: %w", err)
	}
	defer destFile.Close()

	buffer := make([]byte, config.ChunkSize)
	var totalBytes int64

	for {
		n, err := sourceFile.Read(buffer)
		if err != nil && err != io.EOF {
			return nil, fmt.Errorf("failed to read source file: %w", err)
		}

		if n == 0 {
			break
		}

		written, err := destFile.Write(buffer[:n])
		if err != nil {
			return nil, fmt.Errorf("failed to write to destination file: %w", err)
		}

		totalBytes += int64(written)
	}

	return &TransferResult{
		BytesTransferred: totalBytes,
	}, nil
}

// singleFileTransfer transfers a single file
func singleFileTransfer(source, destination string) (*TransferResult, error) {
	sourceFile, err := os.Open(source)
	if err != nil {
		return nil, fmt.Errorf("failed to open source file: %w", err)
	}
	defer sourceFile.Close()

	// Create destination directory if it doesn't exist
	destDir := filepath.Dir(destination)
	if err := os.MkdirAll(destDir, 0755); err != nil {
		return nil, fmt.Errorf("failed to create destination directory: %w", err)
	}

	destFile, err := os.Create(destination)
	if err != nil {
		return nil, fmt.Errorf("failed to create destination file: %w", err)
	}
	defer destFile.Close()

	bytesTransferred, err := io.Copy(destFile, sourceFile)
	if err != nil {
		return nil, fmt.Errorf("failed to copy file: %w", err)
	}

	return &TransferResult{
		BytesTransferred: bytesTransferred,
	}, nil
}

// DownloadFile downloads a file from a URL
func DownloadFile(url, destination string, config *TransferConfig) (*TransferResult, error) {
	return httpTransfer(url, destination, config)
}

// UploadFile uploads a file to a URL (placeholder for future implementation)
func UploadFile(source, url string, config *TransferConfig) (*TransferResult, error) {
	// This would implement HTTP POST/PUT upload
	return nil, fmt.Errorf("upload functionality not yet implemented")
}

// TransferWithProgress transfers files with progress callback
func TransferWithProgress(source, destination, method string, progressCallback func(int64, int64)) (*TransferResult, error) {
	// Get total size for progress calculation
	sourceInfo, err := os.Stat(source)
	if err != nil {
		return nil, fmt.Errorf("failed to stat source: %w", err)
	}

	totalSize := sourceInfo.Size()
	var transferred int64

	// Create a progress reader wrapper
	sourceFile, err := os.Open(source)
	if err != nil {
		return nil, fmt.Errorf("failed to open source file: %w", err)
	}
	defer sourceFile.Close()

	destFile, err := os.Create(destination)
	if err != nil {
		return nil, fmt.Errorf("failed to create destination file: %w", err)
	}
	defer destFile.Close()

	// Progress tracking reader
	progressReader := &progressReader{
		reader: sourceFile,
		callback: func(n int64) {
			transferred += n
			if progressCallback != nil {
				progressCallback(transferred, totalSize)
			}
		},
	}

	bytesTransferred, err := io.Copy(destFile, progressReader)
	if err != nil {
		return nil, fmt.Errorf("failed to copy with progress: %w", err)
	}

	return &TransferResult{
		BytesTransferred: bytesTransferred,
		Method:           method,
		Success:          true,
	}, nil
}

// progressReader wraps an io.Reader to provide progress callbacks
type progressReader struct {
	reader   io.Reader
	callback func(int64)
}

func (pr *progressReader) Read(p []byte) (n int, err error) {
	n, err = pr.reader.Read(p)
	if n > 0 && pr.callback != nil {
		pr.callback(int64(n))
	}
	return n, err
}

// ConcurrentDownload downloads multiple files concurrently
func ConcurrentDownload(urls []string, destinationDir string, config *TransferConfig) ([]*TransferResult, error) {
	semaphore := make(chan struct{}, config.MaxConcurrency)
	var wg sync.WaitGroup
	results := make([]*TransferResult, len(urls))
	var mu sync.Mutex

	for i, downloadURL := range urls {
		wg.Add(1)
		go func(index int, downloadURL string) {
			defer wg.Done()

			// Acquire semaphore
			semaphore <- struct{}{}
			defer func() { <-semaphore }()

			// Extract filename from URL
			parsedURL, err := url.Parse(downloadURL)
			if err != nil {
				mu.Lock()
				results[index] = &TransferResult{
					Success: false,
					Error:   err.Error(),
				}
				mu.Unlock()
				return
			}

			filename := filepath.Base(parsedURL.Path)
			if filename == "" || filename == "." {
				filename = fmt.Sprintf("download_%d", index)
			}

			destination := filepath.Join(destinationDir, filename)

			// Download file
			result, err := httpTransfer(downloadURL, destination, config)
			if err != nil {
				mu.Lock()
				results[index] = &TransferResult{
					Success: false,
					Error:   err.Error(),
				}
				mu.Unlock()
				return
			}

			mu.Lock()
			results[index] = result
			mu.Unlock()
		}(i, downloadURL)
	}

	wg.Wait()
	return results, nil
}