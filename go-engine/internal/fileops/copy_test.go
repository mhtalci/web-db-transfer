package fileops

import (
	"fmt"
	"os"
	"path/filepath"
	"testing"
)

func TestCopyFile(t *testing.T) {
	// Create temporary directory
	tempDir, err := os.MkdirTemp("", "copy_test")
	if err != nil {
		t.Fatalf("Failed to create temp dir: %v", err)
	}
	defer os.RemoveAll(tempDir)

	// Create source file
	sourceFile := filepath.Join(tempDir, "source.txt")
	testContent := "Hello, World! This is a test file for copying."
	err = os.WriteFile(sourceFile, []byte(testContent), 0644)
	if err != nil {
		t.Fatalf("Failed to create source file: %v", err)
	}

	// Test file copy
	destFile := filepath.Join(tempDir, "destination.txt")
	result, err := CopyFile(sourceFile, destFile)
	if err != nil {
		t.Fatalf("CopyFile failed: %v", err)
	}

	// Verify result
	if !result.Success {
		t.Error("Copy operation should be successful")
	}

	if result.BytesCopied != int64(len(testContent)) {
		t.Errorf("Expected %d bytes copied, got %d", len(testContent), result.BytesCopied)
	}

	if result.Duration <= 0 {
		t.Error("Duration should be positive")
	}

	if result.TransferRate <= 0 {
		t.Error("Transfer rate should be positive")
	}

	// Verify destination file exists and has correct content
	destContent, err := os.ReadFile(destFile)
	if err != nil {
		t.Fatalf("Failed to read destination file: %v", err)
	}

	if string(destContent) != testContent {
		t.Errorf("Content mismatch. Expected %q, got %q", testContent, string(destContent))
	}

	// Verify checksum is not empty
	if result.Checksum == "" {
		t.Error("Checksum should not be empty")
	}
}

func TestCopyDirectory(t *testing.T) {
	// Create temporary directory
	tempDir, err := os.MkdirTemp("", "copy_dir_test")
	if err != nil {
		t.Fatalf("Failed to create temp dir: %v", err)
	}
	defer os.RemoveAll(tempDir)

	// Create source directory structure
	sourceDir := filepath.Join(tempDir, "source")
	err = os.MkdirAll(filepath.Join(sourceDir, "subdir"), 0755)
	if err != nil {
		t.Fatalf("Failed to create source directory: %v", err)
	}

	// Create test files
	files := map[string]string{
		"file1.txt":        "Content of file 1",
		"file2.txt":        "Content of file 2",
		"subdir/file3.txt": "Content of file 3",
	}

	var totalSize int64
	for filename, content := range files {
		filePath := filepath.Join(sourceDir, filename)
		err = os.WriteFile(filePath, []byte(content), 0644)
		if err != nil {
			t.Fatalf("Failed to create test file %s: %v", filename, err)
		}
		totalSize += int64(len(content))
	}

	// Test directory copy
	destDir := filepath.Join(tempDir, "destination")
	result, err := CopyDirectory(sourceDir, destDir)
	if err != nil {
		t.Fatalf("CopyDirectory failed: %v", err)
	}

	// Verify result
	if !result.Success {
		t.Error("Copy operation should be successful")
	}

	if result.BytesCopied != totalSize {
		t.Errorf("Expected %d bytes copied, got %d", totalSize, result.BytesCopied)
	}

	// Verify all files were copied
	for filename, expectedContent := range files {
		destFilePath := filepath.Join(destDir, filename)
		content, err := os.ReadFile(destFilePath)
		if err != nil {
			t.Errorf("Failed to read copied file %s: %v", filename, err)
			continue
		}

		if string(content) != expectedContent {
			t.Errorf("Content mismatch for %s. Expected %q, got %q", filename, expectedContent, string(content))
		}
	}
}

func BenchmarkCopyFile(b *testing.B) {
	// Create temporary directory
	tempDir, err := os.MkdirTemp("", "copy_benchmark")
	if err != nil {
		b.Fatalf("Failed to create temp dir: %v", err)
	}
	defer os.RemoveAll(tempDir)

	// Create source file with 1MB of data
	sourceFile := filepath.Join(tempDir, "source.txt")
	data := make([]byte, 1024*1024) // 1MB
	for i := range data {
		data[i] = byte(i % 256)
	}
	err = os.WriteFile(sourceFile, data, 0644)
	if err != nil {
		b.Fatalf("Failed to create source file: %v", err)
	}

	b.ResetTimer()
	b.ReportAllocs()

	for i := 0; i < b.N; i++ {
		destFile := filepath.Join(tempDir, fmt.Sprintf("dest_%d.txt", i))
		_, err := CopyFile(sourceFile, destFile)
		if err != nil {
			b.Fatalf("CopyFile failed: %v", err)
		}
		os.Remove(destFile) // Clean up for next iteration
	}
}

func BenchmarkCopyFileSmall(b *testing.B) {
	// Create temporary directory
	tempDir, err := os.MkdirTemp("", "copy_small_benchmark")
	if err != nil {
		b.Fatalf("Failed to create temp dir: %v", err)
	}
	defer os.RemoveAll(tempDir)

	// Create small source file (1KB)
	sourceFile := filepath.Join(tempDir, "source.txt")
	data := make([]byte, 1024) // 1KB
	for i := range data {
		data[i] = byte(i % 256)
	}
	err = os.WriteFile(sourceFile, data, 0644)
	if err != nil {
		b.Fatalf("Failed to create source file: %v", err)
	}

	b.ResetTimer()
	b.ReportAllocs()

	for i := 0; i < b.N; i++ {
		destFile := filepath.Join(tempDir, fmt.Sprintf("dest_%d.txt", i))
		_, err := CopyFile(sourceFile, destFile)
		if err != nil {
			b.Fatalf("CopyFile failed: %v", err)
		}
		os.Remove(destFile) // Clean up for next iteration
	}
}

func TestCopyFileNonExistent(t *testing.T) {
	tempDir, err := os.MkdirTemp("", "copy_error_test")
	if err != nil {
		t.Fatalf("Failed to create temp dir: %v", err)
	}
	defer os.RemoveAll(tempDir)

	sourceFile := filepath.Join(tempDir, "nonexistent.txt")
	destFile := filepath.Join(tempDir, "destination.txt")

	_, err = CopyFile(sourceFile, destFile)
	if err == nil {
		t.Error("Expected error when copying non-existent file")
	}
}

func TestCopyFilePermissions(t *testing.T) {
	tempDir, err := os.MkdirTemp("", "copy_permissions_test")
	if err != nil {
		t.Fatalf("Failed to create temp dir: %v", err)
	}
	defer os.RemoveAll(tempDir)

	// Create source file with specific permissions
	sourceFile := filepath.Join(tempDir, "source.txt")
	err = os.WriteFile(sourceFile, []byte("test content"), 0600)
	if err != nil {
		t.Fatalf("Failed to create source file: %v", err)
	}

	// Copy file
	destFile := filepath.Join(tempDir, "destination.txt")
	_, err = CopyFile(sourceFile, destFile)
	if err != nil {
		t.Fatalf("CopyFile failed: %v", err)
	}

	// Check that permissions were preserved
	sourceInfo, err := os.Stat(sourceFile)
	if err != nil {
		t.Fatalf("Failed to stat source file: %v", err)
	}

	destInfo, err := os.Stat(destFile)
	if err != nil {
		t.Fatalf("Failed to stat destination file: %v", err)
	}

	if sourceInfo.Mode() != destInfo.Mode() {
		t.Errorf("Permissions not preserved. Source: %v, Dest: %v", sourceInfo.Mode(), destInfo.Mode())
	}
}