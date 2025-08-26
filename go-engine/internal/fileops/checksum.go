package fileops

import (
	"crypto/md5"
	"crypto/sha1"
	"crypto/sha256"
	"fmt"
	"hash"
	"io"
	"os"
	"path/filepath"
	"sync"
)

type ChecksumResult struct {
	File     string `json:"file"`
	MD5      string `json:"md5"`
	SHA1     string `json:"sha1"`
	SHA256   string `json:"sha256"`
	Size     int64  `json:"size"`
	Error    string `json:"error,omitempty"`
}

type ChecksumResults struct {
	Results []ChecksumResult `json:"results"`
	Success bool             `json:"success"`
}

// CalculateChecksums calculates multiple hash types for files in parallel
func CalculateChecksums(files []string) (*ChecksumResults, error) {
	var wg sync.WaitGroup
	results := make([]ChecksumResult, len(files))
	
	// Process files in parallel
	for i, file := range files {
		wg.Add(1)
		go func(index int, filename string) {
			defer wg.Done()
			result := calculateFileChecksum(filename)
			results[index] = result
		}(i, file)
	}
	
	wg.Wait()
	
	return &ChecksumResults{
		Results: results,
		Success: true,
	}, nil
}

func calculateFileChecksum(filename string) ChecksumResult {
	result := ChecksumResult{
		File: filename,
	}
	
	// Check if file exists and get size
	info, err := os.Stat(filename)
	if err != nil {
		result.Error = fmt.Sprintf("failed to stat file: %v", err)
		return result
	}
	result.Size = info.Size()
	
	// Open file
	file, err := os.Open(filename)
	if err != nil {
		result.Error = fmt.Sprintf("failed to open file: %v", err)
		return result
	}
	defer file.Close()
	
	// Create hash instances
	md5Hash := md5.New()
	sha1Hash := sha1.New()
	sha256Hash := sha256.New()
	
	// Use MultiWriter to calculate all hashes in one pass
	multiWriter := io.MultiWriter(md5Hash, sha1Hash, sha256Hash)
	
	// Copy file content to all hash writers
	_, err = io.Copy(multiWriter, file)
	if err != nil {
		result.Error = fmt.Sprintf("failed to read file: %v", err)
		return result
	}
	
	// Get hash results
	result.MD5 = fmt.Sprintf("%x", md5Hash.Sum(nil))
	result.SHA1 = fmt.Sprintf("%x", sha1Hash.Sum(nil))
	result.SHA256 = fmt.Sprintf("%x", sha256Hash.Sum(nil))
	
	return result
}

// VerifyChecksum verifies a file against a known checksum
func VerifyChecksum(filename, expectedChecksum, hashType string) (bool, error) {
	file, err := os.Open(filename)
	if err != nil {
		return false, fmt.Errorf("failed to open file: %w", err)
	}
	defer file.Close()
	
	var hasher hash.Hash
	switch hashType {
	case "md5":
		hasher = md5.New()
	case "sha1":
		hasher = sha1.New()
	case "sha256":
		hasher = sha256.New()
	default:
		return false, fmt.Errorf("unsupported hash type: %s", hashType)
	}
	
	_, err = io.Copy(hasher, file)
	if err != nil {
		return false, fmt.Errorf("failed to read file: %w", err)
	}
	
	actualChecksum := fmt.Sprintf("%x", hasher.Sum(nil))
	return actualChecksum == expectedChecksum, nil
}

// CalculateDirectoryChecksum calculates checksums for all files in a directory
func CalculateDirectoryChecksum(dirPath string) (*ChecksumResults, error) {
	var files []string
	
	err := filepath.Walk(dirPath, func(path string, info os.FileInfo, err error) error {
		if err != nil {
			return err
		}
		
		if !info.IsDir() {
			files = append(files, path)
		}
		
		return nil
	})
	
	if err != nil {
		return nil, fmt.Errorf("failed to walk directory: %w", err)
	}
	
	return CalculateChecksums(files)
}