package fileops

import (
	"fmt"
	"os"
	"path/filepath"
	"testing"
)

func TestCalculateChecksums(t *testing.T) {
	// Create temporary directory
	tempDir, err := os.MkdirTemp("", "checksum_test")
	if err != nil {
		t.Fatalf("Failed to create temp dir: %v", err)
	}
	defer os.RemoveAll(tempDir)

	// Create test files
	testFiles := map[string]string{
		"file1.txt": "Hello, World!",
		"file2.txt": "This is a test file.",
		"file3.txt": "Another test file with different content.",
	}

	var filePaths []string
	for filename, content := range testFiles {
		filePath := filepath.Join(tempDir, filename)
		err = os.WriteFile(filePath, []byte(content), 0644)
		if err != nil {
			t.Fatalf("Failed to create test file %s: %v", filename, err)
		}
		filePaths = append(filePaths, filePath)
	}

	// Calculate checksums
	result, err := CalculateChecksums(filePaths)
	if err != nil {
		t.Fatalf("CalculateChecksums failed: %v", err)
	}

	// Verify result
	if !result.Success {
		t.Error("Checksum calculation should be successful")
	}

	if len(result.Results) != len(filePaths) {
		t.Errorf("Expected %d results, got %d", len(filePaths), len(result.Results))
	}

	// Verify each result
	for _, checksumResult := range result.Results {
		if checksumResult.Error != "" {
			t.Errorf("Unexpected error for file %s: %s", checksumResult.File, checksumResult.Error)
		}

		if checksumResult.MD5 == "" {
			t.Errorf("MD5 checksum should not be empty for file %s", checksumResult.File)
		}

		if checksumResult.SHA1 == "" {
			t.Errorf("SHA1 checksum should not be empty for file %s", checksumResult.File)
		}

		if checksumResult.SHA256 == "" {
			t.Errorf("SHA256 checksum should not be empty for file %s", checksumResult.File)
		}

		if checksumResult.Size <= 0 {
			t.Errorf("File size should be positive for file %s", checksumResult.File)
		}

		// Verify checksum lengths
		if len(checksumResult.MD5) != 32 {
			t.Errorf("MD5 checksum should be 32 characters, got %d for file %s", len(checksumResult.MD5), checksumResult.File)
		}

		if len(checksumResult.SHA1) != 40 {
			t.Errorf("SHA1 checksum should be 40 characters, got %d for file %s", len(checksumResult.SHA1), checksumResult.File)
		}

		if len(checksumResult.SHA256) != 64 {
			t.Errorf("SHA256 checksum should be 64 characters, got %d for file %s", len(checksumResult.SHA256), checksumResult.File)
		}
	}
}

func TestVerifyChecksum(t *testing.T) {
	// Create temporary directory
	tempDir, err := os.MkdirTemp("", "verify_checksum_test")
	if err != nil {
		t.Fatalf("Failed to create temp dir: %v", err)
	}
	defer os.RemoveAll(tempDir)

	// Create test file
	testFile := filepath.Join(tempDir, "test.txt")
	testContent := "Hello, World!"
	err = os.WriteFile(testFile, []byte(testContent), 0644)
	if err != nil {
		t.Fatalf("Failed to create test file: %v", err)
	}

	// Calculate known checksums for "Hello, World!"
	knownMD5 := "65a8e27d8879283831b664bd8b7f0ad4"
	knownSHA1 := "0a0a9f2a6772942557ab5355d76af442f8f65e01"
	knownSHA256 := "dffd6021bb2bd5b0af676290809ec3a53191dd81c7f70a4b28688a362182986f"

	// Test MD5 verification
	valid, err := VerifyChecksum(testFile, knownMD5, "md5")
	if err != nil {
		t.Fatalf("MD5 verification failed: %v", err)
	}
	if !valid {
		t.Error("MD5 checksum should be valid")
	}

	// Test SHA1 verification
	valid, err = VerifyChecksum(testFile, knownSHA1, "sha1")
	if err != nil {
		t.Fatalf("SHA1 verification failed: %v", err)
	}
	if !valid {
		t.Error("SHA1 checksum should be valid")
	}

	// Test SHA256 verification
	valid, err = VerifyChecksum(testFile, knownSHA256, "sha256")
	if err != nil {
		t.Fatalf("SHA256 verification failed: %v", err)
	}
	if !valid {
		t.Error("SHA256 checksum should be valid")
	}

	// Test invalid checksum
	valid, err = VerifyChecksum(testFile, "invalid_checksum", "md5")
	if err != nil {
		t.Fatalf("Invalid checksum verification failed: %v", err)
	}
	if valid {
		t.Error("Invalid checksum should not be valid")
	}

	// Test unsupported hash type
	_, err = VerifyChecksum(testFile, knownMD5, "unsupported")
	if err == nil {
		t.Error("Expected error for unsupported hash type")
	}
}

func TestCalculateDirectoryChecksum(t *testing.T) {
	// Create temporary directory
	tempDir, err := os.MkdirTemp("", "dir_checksum_test")
	if err != nil {
		t.Fatalf("Failed to create temp dir: %v", err)
	}
	defer os.RemoveAll(tempDir)

	// Create directory structure
	testDir := filepath.Join(tempDir, "testdir")
	err = os.MkdirAll(filepath.Join(testDir, "subdir"), 0755)
	if err != nil {
		t.Fatalf("Failed to create test directory: %v", err)
	}

	// Create test files
	testFiles := map[string]string{
		"file1.txt":        "Content 1",
		"file2.txt":        "Content 2",
		"subdir/file3.txt": "Content 3",
	}

	for filename, content := range testFiles {
		filePath := filepath.Join(testDir, filename)
		err = os.WriteFile(filePath, []byte(content), 0644)
		if err != nil {
			t.Fatalf("Failed to create test file %s: %v", filename, err)
		}
	}

	// Calculate directory checksums
	result, err := CalculateDirectoryChecksum(testDir)
	if err != nil {
		t.Fatalf("CalculateDirectoryChecksum failed: %v", err)
	}

	// Verify result
	if !result.Success {
		t.Error("Directory checksum calculation should be successful")
	}

	if len(result.Results) != len(testFiles) {
		t.Errorf("Expected %d results, got %d", len(testFiles), len(result.Results))
	}

	// Verify each file was processed
	processedFiles := make(map[string]bool)
	for _, checksumResult := range result.Results {
		if checksumResult.Error != "" {
			t.Errorf("Unexpected error for file %s: %s", checksumResult.File, checksumResult.Error)
		}
		processedFiles[checksumResult.File] = true
	}

	// Check that all expected files were processed
	for filename := range testFiles {
		expectedPath := filepath.Join(testDir, filename)
		if !processedFiles[expectedPath] {
			t.Errorf("File %s was not processed", expectedPath)
		}
	}
}

func BenchmarkCalculateChecksums(b *testing.B) {
	// Create temporary directory
	tempDir, err := os.MkdirTemp("", "checksum_benchmark")
	if err != nil {
		b.Fatalf("Failed to create temp dir: %v", err)
	}
	defer os.RemoveAll(tempDir)

	// Create test file with 1MB of data
	testFile := filepath.Join(tempDir, "test.txt")
	data := make([]byte, 1024*1024) // 1MB
	for i := range data {
		data[i] = byte(i % 256)
	}
	err = os.WriteFile(testFile, data, 0644)
	if err != nil {
		b.Fatalf("Failed to create test file: %v", err)
	}

	files := []string{testFile}

	b.ResetTimer()
	b.ReportAllocs()

	for i := 0; i < b.N; i++ {
		_, err := CalculateChecksums(files)
		if err != nil {
			b.Fatalf("CalculateChecksums failed: %v", err)
		}
	}
}

func BenchmarkCalculateChecksumsParallel(b *testing.B) {
	// Create temporary directory
	tempDir, err := os.MkdirTemp("", "checksum_parallel_benchmark")
	if err != nil {
		b.Fatalf("Failed to create temp dir: %v", err)
	}
	defer os.RemoveAll(tempDir)

	// Create multiple test files
	var files []string
	for i := 0; i < 10; i++ {
		testFile := filepath.Join(tempDir, fmt.Sprintf("test_%d.txt", i))
		data := make([]byte, 100*1024) // 100KB each
		for j := range data {
			data[j] = byte((i + j) % 256)
		}
		err = os.WriteFile(testFile, data, 0644)
		if err != nil {
			b.Fatalf("Failed to create test file: %v", err)
		}
		files = append(files, testFile)
	}

	b.ResetTimer()
	b.ReportAllocs()

	for i := 0; i < b.N; i++ {
		_, err := CalculateChecksums(files)
		if err != nil {
			b.Fatalf("CalculateChecksums failed: %v", err)
		}
	}
}

func TestCalculateChecksumsNonExistent(t *testing.T) {
	files := []string{"/nonexistent/file.txt"}
	result, err := CalculateChecksums(files)
	if err != nil {
		t.Fatalf("CalculateChecksums should not fail for non-existent files: %v", err)
	}

	if len(result.Results) != 1 {
		t.Errorf("Expected 1 result, got %d", len(result.Results))
	}

	if result.Results[0].Error == "" {
		t.Error("Expected error for non-existent file")
	}
}