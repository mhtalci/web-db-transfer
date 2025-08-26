package network

import (
	"context"
	"fmt"
	"io"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"
)

func TestHTTPDownload(t *testing.T) {
	// Create test server
	testContent := "This is test content for HTTP download"
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Length", fmt.Sprintf("%d", len(testContent)))
		w.WriteHeader(http.StatusOK)
		w.Write([]byte(testContent))
	}))
	defer server.Close()

	// Create temporary directory
	tempDir, err := os.MkdirTemp("", "http_download_test")
	if err != nil {
		t.Fatalf("Failed to create temp dir: %v", err)
	}
	defer os.RemoveAll(tempDir)

	// Test HTTP download
	destFile := filepath.Join(tempDir, "downloaded.txt")
	result, err := HTTPDownload(server.URL, destFile)
	if err != nil {
		t.Fatalf("HTTPDownload failed: %v", err)
	}

	// Verify result
	if !result.Success {
		t.Error("Download should be successful")
	}

	if result.BytesDownloaded != int64(len(testContent)) {
		t.Errorf("Expected %d bytes downloaded, got %d", len(testContent), result.BytesDownloaded)
	}

	if result.Duration <= 0 {
		t.Error("Duration should be positive")
	}

	if result.TransferRate <= 0 {
		t.Error("Transfer rate should be positive")
	}

	// Verify file content
	downloadedContent, err := os.ReadFile(destFile)
	if err != nil {
		t.Fatalf("Failed to read downloaded file: %v", err)
	}

	if string(downloadedContent) != testContent {
		t.Errorf("Content mismatch. Expected %q, got %q", testContent, string(downloadedContent))
	}
}

func TestHTTPUpload(t *testing.T) {
	// Create temporary directory
	tempDir, err := os.MkdirTemp("", "http_upload_test")
	if err != nil {
		t.Fatalf("Failed to create temp dir: %v", err)
	}
	defer os.RemoveAll(tempDir)

	// Create test file
	testContent := "This is test content for HTTP upload"
	sourceFile := filepath.Join(tempDir, "upload.txt")
	err = os.WriteFile(sourceFile, []byte(testContent), 0644)
	if err != nil {
		t.Fatalf("Failed to create source file: %v", err)
	}

	// Create test server that accepts uploads
	var receivedContent []byte
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost {
			w.WriteHeader(http.StatusMethodNotAllowed)
			return
		}

		body, err := io.ReadAll(r.Body)
		if err != nil {
			w.WriteHeader(http.StatusInternalServerError)
			return
		}
		receivedContent = body

		w.WriteHeader(http.StatusOK)
		w.Write([]byte("Upload successful"))
	}))
	defer server.Close()

	// Test HTTP upload
	result, err := HTTPUpload(sourceFile, server.URL)
	if err != nil {
		t.Fatalf("HTTPUpload failed: %v", err)
	}

	// Verify result
	if !result.Success {
		t.Error("Upload should be successful")
	}

	if result.BytesUploaded != int64(len(testContent)) {
		t.Errorf("Expected %d bytes uploaded, got %d", len(testContent), result.BytesUploaded)
	}

	// Verify server received correct content
	if string(receivedContent) != testContent {
		t.Errorf("Server received incorrect content. Expected %q, got %q", testContent, string(receivedContent))
	}
}

func TestParallelDownloads(t *testing.T) {
	// Create test server
	testContent := "This is test content for parallel downloads"
	requestCount := 0
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		requestCount++
		// Simulate some processing time
		time.Sleep(10 * time.Millisecond)
		w.Header().Set("Content-Length", fmt.Sprintf("%d", len(testContent)))
		w.WriteHeader(http.StatusOK)
		w.Write([]byte(testContent))
	}))
	defer server.Close()

	// Create temporary directory
	tempDir, err := os.MkdirTemp("", "parallel_download_test")
	if err != nil {
		t.Fatalf("Failed to create temp dir: %v", err)
	}
	defer os.RemoveAll(tempDir)

	// Prepare download tasks
	numDownloads := 5
	downloads := make([]DownloadTask, numDownloads)
	for i := 0; i < numDownloads; i++ {
		downloads[i] = DownloadTask{
			URL:      server.URL,
			FilePath: filepath.Join(tempDir, fmt.Sprintf("file_%d.txt", i)),
		}
	}

	// Test parallel downloads
	results, err := ParallelDownloads(downloads, 3) // Max 3 concurrent downloads
	if err != nil {
		t.Fatalf("ParallelDownloads failed: %v", err)
	}

	// Verify results
	if len(results) != numDownloads {
		t.Errorf("Expected %d results, got %d", numDownloads, len(results))
	}

	successCount := 0
	for i, result := range results {
		if result.Success {
			successCount++
		} else {
			t.Errorf("Download %d failed: %s", i, result.Error)
		}

		if result.BytesDownloaded != int64(len(testContent)) {
			t.Errorf("Download %d: expected %d bytes, got %d", i, len(testContent), result.BytesDownloaded)
		}
	}

	if successCount != numDownloads {
		t.Errorf("Expected %d successful downloads, got %d", numDownloads, successCount)
	}

	// Verify all files were created
	for i := 0; i < numDownloads; i++ {
		filePath := filepath.Join(tempDir, fmt.Sprintf("file_%d.txt", i))
		content, err := os.ReadFile(filePath)
		if err != nil {
			t.Errorf("Failed to read file %d: %v", i, err)
			continue
		}

		if string(content) != testContent {
			t.Errorf("File %d content mismatch", i)
		}
	}
}

func TestDownloadWithProgress(t *testing.T) {
	// Create test server with chunked response
	testContent := strings.Repeat("A", 10000) // 10KB
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Length", fmt.Sprintf("%d", len(testContent)))
		w.WriteHeader(http.StatusOK)

		// Send content in chunks to simulate progress
		chunkSize := 1000
		for i := 0; i < len(testContent); i += chunkSize {
			end := i + chunkSize
			if end > len(testContent) {
				end = len(testContent)
			}
			w.Write([]byte(testContent[i:end]))
			if f, ok := w.(http.Flusher); ok {
				f.Flush()
			}
			time.Sleep(1 * time.Millisecond) // Small delay to simulate network
		}
	}))
	defer server.Close()

	// Create temporary directory
	tempDir, err := os.MkdirTemp("", "progress_download_test")
	if err != nil {
		t.Fatalf("Failed to create temp dir: %v", err)
	}
	defer os.RemoveAll(tempDir)

	// Track progress updates
	var progressUpdates []ProgressUpdate
	progressCallback := func(update ProgressUpdate) {
		progressUpdates = append(progressUpdates, update)
	}

	// Test download with progress
	destFile := filepath.Join(tempDir, "progress_test.txt")
	result, err := HTTPDownloadWithProgress(server.URL, destFile, progressCallback)
	if err != nil {
		t.Fatalf("HTTPDownloadWithProgress failed: %v", err)
	}

	// Verify result
	if !result.Success {
		t.Error("Download should be successful")
	}

	if result.BytesDownloaded != int64(len(testContent)) {
		t.Errorf("Expected %d bytes downloaded, got %d", len(testContent), result.BytesDownloaded)
	}

	// Verify progress updates were received
	if len(progressUpdates) == 0 {
		t.Error("Expected progress updates, got none")
	}

	// Verify final progress update shows completion
	finalUpdate := progressUpdates[len(progressUpdates)-1]
	if finalUpdate.BytesTransferred != int64(len(testContent)) {
		t.Errorf("Final progress update should show %d bytes, got %d", len(testContent), finalUpdate.BytesTransferred)
	}
}

func TestDownloadWithTimeout(t *testing.T) {
	// Create test server with delay
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		time.Sleep(200 * time.Millisecond) // Delay longer than timeout
		w.WriteHeader(http.StatusOK)
		w.Write([]byte("This should timeout"))
	}))
	defer server.Close()

	// Create temporary directory
	tempDir, err := os.MkdirTemp("", "timeout_test")
	if err != nil {
		t.Fatalf("Failed to create temp dir: %v", err)
	}
	defer os.RemoveAll(tempDir)

	// Test download with short timeout
	destFile := filepath.Join(tempDir, "timeout_test.txt")
	ctx, cancel := context.WithTimeout(context.Background(), 100*time.Millisecond)
	defer cancel()

	result, err := HTTPDownloadWithContext(ctx, server.URL, destFile)
	
	// Should timeout
	if err == nil {
		t.Error("Expected timeout error")
	}

	if result.Success {
		t.Error("Download should not be successful due to timeout")
	}
}

func TestDownloadRetry(t *testing.T) {
	// Create test server that fails first few requests
	attemptCount := 0
	testContent := "Success after retries"
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		attemptCount++
		if attemptCount < 3 {
			w.WriteHeader(http.StatusInternalServerError)
			w.Write([]byte("Server error"))
			return
		}
		w.WriteHeader(http.StatusOK)
		w.Write([]byte(testContent))
	}))
	defer server.Close()

	// Create temporary directory
	tempDir, err := os.MkdirTemp("", "retry_test")
	if err != nil {
		t.Fatalf("Failed to create temp dir: %v", err)
	}
	defer os.RemoveAll(tempDir)

	// Test download with retry
	destFile := filepath.Join(tempDir, "retry_test.txt")
	result, err := HTTPDownloadWithRetry(server.URL, destFile, 5, 10*time.Millisecond)
	if err != nil {
		t.Fatalf("HTTPDownloadWithRetry failed: %v", err)
	}

	// Verify result
	if !result.Success {
		t.Error("Download should be successful after retries")
	}

	if result.RetryCount != 2 {
		t.Errorf("Expected 2 retries, got %d", result.RetryCount)
	}

	// Verify content
	content, err := os.ReadFile(destFile)
	if err != nil {
		t.Fatalf("Failed to read downloaded file: %v", err)
	}

	if string(content) != testContent {
		t.Errorf("Content mismatch. Expected %q, got %q", testContent, string(content))
	}
}

func BenchmarkHTTPDownload(b *testing.B) {
	// Create test server
	testContent := strings.Repeat("A", 1024*1024) // 1MB
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Length", fmt.Sprintf("%d", len(testContent)))
		w.WriteHeader(http.StatusOK)
		w.Write([]byte(testContent))
	}))
	defer server.Close()

	// Create temporary directory
	tempDir, err := os.MkdirTemp("", "download_benchmark")
	if err != nil {
		b.Fatalf("Failed to create temp dir: %v", err)
	}
	defer os.RemoveAll(tempDir)

	b.ResetTimer()
	b.ReportAllocs()

	for i := 0; i < b.N; i++ {
		destFile := filepath.Join(tempDir, fmt.Sprintf("benchmark_%d.txt", i))
		_, err := HTTPDownload(server.URL, destFile)
		if err != nil {
			b.Fatalf("HTTPDownload failed: %v", err)
		}
		os.Remove(destFile) // Clean up for next iteration
	}
}

func BenchmarkParallelDownloads(b *testing.B) {
	// Create test server
	testContent := "Benchmark content"
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Length", fmt.Sprintf("%d", len(testContent)))
		w.WriteHeader(http.StatusOK)
		w.Write([]byte(testContent))
	}))
	defer server.Close()

	// Create temporary directory
	tempDir, err := os.MkdirTemp("", "parallel_benchmark")
	if err != nil {
		b.Fatalf("Failed to create temp dir: %v", err)
	}
	defer os.RemoveAll(tempDir)

	b.ResetTimer()
	b.ReportAllocs()

	for i := 0; i < b.N; i++ {
		// Create download tasks
		downloads := make([]DownloadTask, 10)
		for j := 0; j < 10; j++ {
			downloads[j] = DownloadTask{
				URL:      server.URL,
				FilePath: filepath.Join(tempDir, fmt.Sprintf("bench_%d_%d.txt", i, j)),
			}
		}

		_, err := ParallelDownloads(downloads, 5)
		if err != nil {
			b.Fatalf("ParallelDownloads failed: %v", err)
		}

		// Clean up files
		for j := 0; j < 10; j++ {
			os.Remove(filepath.Join(tempDir, fmt.Sprintf("bench_%d_%d.txt", i, j)))
		}
	}
}

func TestHTTPDownloadError(t *testing.T) {
	// Test download from non-existent server
	tempDir, err := os.MkdirTemp("", "error_test")
	if err != nil {
		t.Fatalf("Failed to create temp dir: %v", err)
	}
	defer os.RemoveAll(tempDir)

	destFile := filepath.Join(tempDir, "error_test.txt")
	_, err = HTTPDownload("http://nonexistent.server.local/file.txt", destFile)
	if err == nil {
		t.Error("Expected error when downloading from non-existent server")
	}
}

func TestHTTPUploadError(t *testing.T) {
	// Test upload to non-existent server
	tempDir, err := os.MkdirTemp("", "upload_error_test")
	if err != nil {
		t.Fatalf("Failed to create temp dir: %v", err)
	}
	defer os.RemoveAll(tempDir)

	// Create test file
	sourceFile := filepath.Join(tempDir, "upload.txt")
	err = os.WriteFile(sourceFile, []byte("test"), 0644)
	if err != nil {
		t.Fatalf("Failed to create source file: %v", err)
	}

	_, err = HTTPUpload(sourceFile, "http://nonexistent.server.local/upload")
	if err == nil {
		t.Error("Expected error when uploading to non-existent server")
	}
}

func TestConcurrentDownloads(t *testing.T) {
	// Create test server
	testContent := "Concurrent download test"
	requestCount := 0
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		requestCount++
		w.Header().Set("Content-Length", fmt.Sprintf("%d", len(testContent)))
		w.WriteHeader(http.StatusOK)
		w.Write([]byte(testContent))
	}))
	defer server.Close()

	// Create temporary directory
	tempDir, err := os.MkdirTemp("", "concurrent_test")
	if err != nil {
		t.Fatalf("Failed to create temp dir: %v", err)
	}
	defer os.RemoveAll(tempDir)

	// Test concurrent downloads
	numConcurrent := 10
	results := make(chan *DownloadResult, numConcurrent)
	
	for i := 0; i < numConcurrent; i++ {
		go func(index int) {
			destFile := filepath.Join(tempDir, fmt.Sprintf("concurrent_%d.txt", index))
			result, err := HTTPDownload(server.URL, destFile)
			if err != nil {
				result = &DownloadResult{Success: false, Error: err.Error()}
			}
			results <- result
		}(i)
	}

	// Collect results
	successCount := 0
	for i := 0; i < numConcurrent; i++ {
		result := <-results
		if result.Success {
			successCount++
		}
	}

	if successCount != numConcurrent {
		t.Errorf("Expected %d successful downloads, got %d", numConcurrent, successCount)
	}

	if requestCount != numConcurrent {
		t.Errorf("Expected %d requests to server, got %d", numConcurrent, requestCount)
	}
}