package fileops

import (
	"fmt"
	"os"
	"path/filepath"
	"testing"
)

func TestCompressFile(t *testing.T) {
	// Create temporary directory
	tempDir, err := os.MkdirTemp("", "compress_test")
	if err != nil {
		t.Fatalf("Failed to create temp dir: %v", err)
	}
	defer os.RemoveAll(tempDir)

	// Create source file
	sourceFile := filepath.Join(tempDir, "source.txt")
	testContent := "Hello, World! This is a test file for compression. " +
		"It contains some repeated text to ensure good compression ratios. " +
		"Repeated text, repeated text, repeated text."
	err = os.WriteFile(sourceFile, []byte(testContent), 0644)
	if err != nil {
		t.Fatalf("Failed to create source file: %v", err)
	}

	// Test file compression
	compressedFile := filepath.Join(tempDir, "compressed.gz")
	result, err := CompressFile(sourceFile, compressedFile)
	if err != nil {
		t.Fatalf("CompressFile failed: %v", err)
	}

	// Verify result
	if !result.Success {
		t.Error("Compression should be successful")
	}

	if result.OriginalSize != int64(len(testContent)) {
		t.Errorf("Expected original size %d, got %d", len(testContent), result.OriginalSize)
	}

	if result.CompressedSize <= 0 {
		t.Error("Compressed size should be positive")
	}

	if result.CompressionRatio <= 0 || result.CompressionRatio > 1 {
		t.Errorf("Compression ratio should be between 0 and 1, got %f", result.CompressionRatio)
	}

	// Verify compressed file exists
	if _, err := os.Stat(compressedFile); os.IsNotExist(err) {
		t.Error("Compressed file should exist")
	}

	// Verify compressed file is smaller (for this test content)
	if result.CompressedSize >= result.OriginalSize {
		t.Error("Compressed file should be smaller than original")
	}
}

func TestDecompressFile(t *testing.T) {
	// Create temporary directory
	tempDir, err := os.MkdirTemp("", "decompress_test")
	if err != nil {
		t.Fatalf("Failed to create temp dir: %v", err)
	}
	defer os.RemoveAll(tempDir)

	// Create and compress a test file first
	sourceFile := filepath.Join(tempDir, "source.txt")
	testContent := "This is test content for decompression testing."
	err = os.WriteFile(sourceFile, []byte(testContent), 0644)
	if err != nil {
		t.Fatalf("Failed to create source file: %v", err)
	}

	compressedFile := filepath.Join(tempDir, "compressed.gz")
	_, err = CompressFile(sourceFile, compressedFile)
	if err != nil {
		t.Fatalf("Failed to compress file: %v", err)
	}

	// Test file decompression
	decompressedFile := filepath.Join(tempDir, "decompressed.txt")
	result, err := DecompressFile(compressedFile, decompressedFile)
	if err != nil {
		t.Fatalf("DecompressFile failed: %v", err)
	}

	// Verify result
	if !result.Success {
		t.Error("Decompression should be successful")
	}

	if result.DecompressedSize != int64(len(testContent)) {
		t.Errorf("Expected decompressed size %d, got %d", len(testContent), result.DecompressedSize)
	}

	// Verify decompressed content matches original
	decompressedContent, err := os.ReadFile(decompressedFile)
	if err != nil {
		t.Fatalf("Failed to read decompressed file: %v", err)
	}

	if string(decompressedContent) != testContent {
		t.Errorf("Decompressed content doesn't match original. Expected %q, got %q", testContent, string(decompressedContent))
	}
}

func TestCompressDirectory(t *testing.T) {
	// Create temporary directory
	tempDir, err := os.MkdirTemp("", "compress_dir_test")
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
		"file1.txt":        "Content of file 1 with some text to compress",
		"file2.txt":        "Content of file 2 with different text",
		"subdir/file3.txt": "Content of file 3 in subdirectory",
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

	// Test directory compression
	archiveFile := filepath.Join(tempDir, "archive.tar.gz")
	result, err := CompressDirectory(sourceDir, archiveFile)
	if err != nil {
		t.Fatalf("CompressDirectory failed: %v", err)
	}

	// Verify result
	if !result.Success {
		t.Error("Directory compression should be successful")
	}

	if result.OriginalSize != totalSize {
		t.Errorf("Expected original size %d, got %d", totalSize, result.OriginalSize)
	}

	if result.CompressedSize <= 0 {
		t.Error("Compressed size should be positive")
	}

	// Verify archive file exists
	if _, err := os.Stat(archiveFile); os.IsNotExist(err) {
		t.Error("Archive file should exist")
	}

	if result.FilesCompressed != len(files) {
		t.Errorf("Expected %d files compressed, got %d", len(files), result.FilesCompressed)
	}
}

func TestDecompressDirectory(t *testing.T) {
	// Create temporary directory
	tempDir, err := os.MkdirTemp("", "decompress_dir_test")
	if err != nil {
		t.Fatalf("Failed to create temp dir: %v", err)
	}
	defer os.RemoveAll(tempDir)

	// Create and compress a directory first
	sourceDir := filepath.Join(tempDir, "source")
	err = os.MkdirAll(sourceDir, 0755)
	if err != nil {
		t.Fatalf("Failed to create source directory: %v", err)
	}

	// Create test files
	testFiles := map[string]string{
		"test1.txt": "Test content 1",
		"test2.txt": "Test content 2",
	}

	for filename, content := range testFiles {
		filePath := filepath.Join(sourceDir, filename)
		err = os.WriteFile(filePath, []byte(content), 0644)
		if err != nil {
			t.Fatalf("Failed to create test file: %v", err)
		}
	}

	// Compress the directory
	archiveFile := filepath.Join(tempDir, "test_archive.tar.gz")
	_, err = CompressDirectory(sourceDir, archiveFile)
	if err != nil {
		t.Fatalf("Failed to compress directory: %v", err)
	}

	// Test directory decompression
	destDir := filepath.Join(tempDir, "destination")
	result, err := DecompressDirectory(archiveFile, destDir)
	if err != nil {
		t.Fatalf("DecompressDirectory failed: %v", err)
	}

	// Verify result
	if !result.Success {
		t.Error("Directory decompression should be successful")
	}

	if result.FilesExtracted != len(testFiles) {
		t.Errorf("Expected %d files extracted, got %d", len(testFiles), result.FilesExtracted)
	}

	// Verify extracted files
	for filename, expectedContent := range testFiles {
		extractedFile := filepath.Join(destDir, filename)
		content, err := os.ReadFile(extractedFile)
		if err != nil {
			t.Errorf("Failed to read extracted file %s: %v", filename, err)
			continue
		}

		if string(content) != expectedContent {
			t.Errorf("Content mismatch for %s. Expected %q, got %q", filename, expectedContent, string(content))
		}
	}
}

func BenchmarkCompressFile(b *testing.B) {
	// Create temporary directory
	tempDir, err := os.MkdirTemp("", "compress_benchmark")
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
		compressedFile := filepath.Join(tempDir, fmt.Sprintf("compressed_%d.gz", i))
		_, err := CompressFile(sourceFile, compressedFile)
		if err != nil {
			b.Fatalf("CompressFile failed: %v", err)
		}
		os.Remove(compressedFile) // Clean up for next iteration
	}
}

func BenchmarkDecompressFile(b *testing.B) {
	// Create temporary directory
	tempDir, err := os.MkdirTemp("", "decompress_benchmark")
	if err != nil {
		b.Fatalf("Failed to create temp dir: %v", err)
	}
	defer os.RemoveAll(tempDir)

	// Create and compress source file
	sourceFile := filepath.Join(tempDir, "source.txt")
	data := make([]byte, 1024*1024) // 1MB
	for i := range data {
		data[i] = byte(i % 256)
	}
	err = os.WriteFile(sourceFile, data, 0644)
	if err != nil {
		b.Fatalf("Failed to create source file: %v", err)
	}

	compressedFile := filepath.Join(tempDir, "compressed.gz")
	_, err = CompressFile(sourceFile, compressedFile)
	if err != nil {
		b.Fatalf("Failed to compress file: %v", err)
	}

	b.ResetTimer()
	b.ReportAllocs()

	for i := 0; i < b.N; i++ {
		decompressedFile := filepath.Join(tempDir, fmt.Sprintf("decompressed_%d.txt", i))
		_, err := DecompressFile(compressedFile, decompressedFile)
		if err != nil {
			b.Fatalf("DecompressFile failed: %v", err)
		}
		os.Remove(decompressedFile) // Clean up for next iteration
	}
}

func TestCompressFileNonExistent(t *testing.T) {
	tempDir, err := os.MkdirTemp("", "compress_error_test")
	if err != nil {
		t.Fatalf("Failed to create temp dir: %v", err)
	}
	defer os.RemoveAll(tempDir)

	sourceFile := filepath.Join(tempDir, "nonexistent.txt")
	compressedFile := filepath.Join(tempDir, "compressed.gz")

	_, err = CompressFile(sourceFile, compressedFile)
	if err == nil {
		t.Error("Expected error when compressing non-existent file")
	}
}

func TestDecompressFileInvalid(t *testing.T) {
	tempDir, err := os.MkdirTemp("", "decompress_error_test")
	if err != nil {
		t.Fatalf("Failed to create temp dir: %v", err)
	}
	defer os.RemoveAll(tempDir)

	// Create invalid compressed file (not actually compressed)
	invalidFile := filepath.Join(tempDir, "invalid.gz")
	err = os.WriteFile(invalidFile, []byte("not compressed data"), 0644)
	if err != nil {
		t.Fatalf("Failed to create invalid file: %v", err)
	}

	decompressedFile := filepath.Join(tempDir, "decompressed.txt")
	_, err = DecompressFile(invalidFile, decompressedFile)
	if err == nil {
		t.Error("Expected error when decompressing invalid file")
	}
}

func TestCompressionRatios(t *testing.T) {
	tempDir, err := os.MkdirTemp("", "compression_ratio_test")
	if err != nil {
		t.Fatalf("Failed to create temp dir: %v", err)
	}
	defer os.RemoveAll(tempDir)

	// Test different types of content for compression ratios
	testCases := []struct {
		name     string
		content  string
		minRatio float64 // Minimum expected compression ratio
	}{
		{
			name:     "highly_repetitive",
			content:  strings.Repeat("AAAA", 1000),
			minRatio: 0.9, // Should compress very well
		},
		{
			name:     "text_content",
			content:  strings.Repeat("The quick brown fox jumps over the lazy dog. ", 100),
			minRatio: 0.3, // Should compress reasonably well
		},
		{
			name:     "random_like",
			content:  generateRandomLikeString(4000),
			minRatio: 0.0, // May not compress well, but shouldn't fail
		},
	}

	for _, tc := range testCases {
		t.Run(tc.name, func(t *testing.T) {
			sourceFile := filepath.Join(tempDir, tc.name+".txt")
			err := os.WriteFile(sourceFile, []byte(tc.content), 0644)
			if err != nil {
				t.Fatalf("Failed to create source file: %v", err)
			}

			compressedFile := filepath.Join(tempDir, tc.name+".gz")
			result, err := CompressFile(sourceFile, compressedFile)
			if err != nil {
				t.Fatalf("CompressFile failed: %v", err)
			}

			if !result.Success {
				t.Error("Compression should be successful")
			}

			if result.CompressionRatio < tc.minRatio {
				t.Errorf("Expected compression ratio >= %f, got %f", tc.minRatio, result.CompressionRatio)
			}

			// Clean up
			os.Remove(sourceFile)
			os.Remove(compressedFile)
		})
	}
}

// Helper function to generate pseudo-random string
func generateRandomLikeString(length int) string {
	chars := "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
	result := make([]byte, length)
	for i := range result {
		result[i] = chars[i%len(chars)]
	}
	return string(result)
}