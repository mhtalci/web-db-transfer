package fileops

import (
	"archive/tar"
	"compress/gzip"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"strings"
	"time"

	"github.com/klauspost/compress/zstd"
)

type CompressionResult struct {
	OriginalSize   int64         `json:"original_size"`
	CompressedSize int64         `json:"compressed_size"`
	CompressionRatio float64     `json:"compression_ratio"`
	Duration       time.Duration `json:"duration_ms"`
	Method         string        `json:"method"`
	Success        bool          `json:"success"`
}

// CompressFile compresses a file or directory using the specified method
func CompressFile(source, destination string) (*CompressionResult, error) {
	startTime := time.Now()
	
	// Determine compression method from destination extension
	method := getCompressionMethod(destination)
	
	sourceInfo, err := os.Stat(source)
	if err != nil {
		return nil, fmt.Errorf("failed to stat source: %w", err)
	}
	
	var originalSize int64
	var compressedSize int64
	
	if sourceInfo.IsDir() {
		originalSize, compressedSize, err = compressDirectory(source, destination, method)
	} else {
		originalSize, compressedSize, err = compressSingleFile(source, destination, method)
	}
	
	if err != nil {
		return nil, err
	}
	
	duration := time.Since(startTime)
	compressionRatio := float64(compressedSize) / float64(originalSize)
	
	return &CompressionResult{
		OriginalSize:     originalSize,
		CompressedSize:   compressedSize,
		CompressionRatio: compressionRatio,
		Duration:         duration,
		Method:           method,
		Success:          true,
	}, nil
}

func getCompressionMethod(filename string) string {
	ext := strings.ToLower(filepath.Ext(filename))
	switch ext {
	case ".gz", ".gzip":
		return "gzip"
	case ".zst", ".zstd":
		return "zstd"
	case ".tar":
		return "tar"
	default:
		if strings.Contains(filename, ".tar.gz") {
			return "tar.gz"
		}
		if strings.Contains(filename, ".tar.zst") {
			return "tar.zst"
		}
		return "gzip" // default
	}
}

func compressSingleFile(source, destination, method string) (int64, int64, error) {
	sourceFile, err := os.Open(source)
	if err != nil {
		return 0, 0, fmt.Errorf("failed to open source file: %w", err)
	}
	defer sourceFile.Close()
	
	sourceInfo, err := sourceFile.Stat()
	if err != nil {
		return 0, 0, fmt.Errorf("failed to get source file info: %w", err)
	}
	
	destFile, err := os.Create(destination)
	if err != nil {
		return 0, 0, fmt.Errorf("failed to create destination file: %w", err)
	}
	defer destFile.Close()
	
	var writer io.WriteCloser
	switch method {
	case "gzip":
		writer = gzip.NewWriter(destFile)
	case "zstd":
		encoder, err := zstd.NewWriter(destFile)
		if err != nil {
			return 0, 0, fmt.Errorf("failed to create zstd encoder: %w", err)
		}
		writer = encoder
	default:
		return 0, 0, fmt.Errorf("unsupported compression method: %s", method)
	}
	defer writer.Close()
	
	_, err = io.Copy(writer, sourceFile)
	if err != nil {
		return 0, 0, fmt.Errorf("failed to compress file: %w", err)
	}
	
	err = writer.Close()
	if err != nil {
		return 0, 0, fmt.Errorf("failed to close compressor: %w", err)
	}
	
	destInfo, err := destFile.Stat()
	if err != nil {
		return 0, 0, fmt.Errorf("failed to get destination file info: %w", err)
	}
	
	return sourceInfo.Size(), destInfo.Size(), nil
}

func compressDirectory(source, destination, method string) (int64, int64, error) {
	destFile, err := os.Create(destination)
	if err != nil {
		return 0, 0, fmt.Errorf("failed to create destination file: %w", err)
	}
	defer destFile.Close()
	
	var writer io.WriteCloser
	var tarWriter *tar.Writer
	
	switch method {
	case "tar.gz":
		gzWriter := gzip.NewWriter(destFile)
		tarWriter = tar.NewWriter(gzWriter)
		writer = &tarGzipWriter{gzWriter, tarWriter}
	case "tar.zst":
		zstWriter, err := zstd.NewWriter(destFile)
		if err != nil {
			return 0, 0, fmt.Errorf("failed to create zstd encoder: %w", err)
		}
		tarWriter = tar.NewWriter(zstWriter)
		writer = &tarZstdWriter{zstWriter, tarWriter}
	case "tar":
		tarWriter = tar.NewWriter(destFile)
		writer = tarWriter
	default:
		return 0, 0, fmt.Errorf("unsupported directory compression method: %s", method)
	}
	defer writer.Close()
	
	var originalSize int64
	
	err = filepath.Walk(source, func(path string, info os.FileInfo, err error) error {
		if err != nil {
			return err
		}
		
		// Calculate relative path
		relPath, err := filepath.Rel(source, path)
		if err != nil {
			return err
		}
		
		// Create tar header
		header, err := tar.FileInfoHeader(info, "")
		if err != nil {
			return err
		}
		header.Name = relPath
		
		// Write header
		if err := tarWriter.WriteHeader(header); err != nil {
			return err
		}
		
		// If it's a file, write its content
		if !info.IsDir() {
			file, err := os.Open(path)
			if err != nil {
				return err
			}
			defer file.Close()
			
			_, err = io.Copy(tarWriter, file)
			if err != nil {
				return err
			}
			
			originalSize += info.Size()
		}
		
		return nil
	})
	
	if err != nil {
		return 0, 0, fmt.Errorf("failed to compress directory: %w", err)
	}
	
	err = writer.Close()
	if err != nil {
		return 0, 0, fmt.Errorf("failed to close compressor: %w", err)
	}
	
	destInfo, err := destFile.Stat()
	if err != nil {
		return 0, 0, fmt.Errorf("failed to get destination file info: %w", err)
	}
	
	return originalSize, destInfo.Size(), nil
}

// Custom writers for combined tar+compression
type tarGzipWriter struct {
	gzWriter  *gzip.Writer
	tarWriter *tar.Writer
}

func (w *tarGzipWriter) Write(p []byte) (n int, err error) {
	return w.tarWriter.Write(p)
}

func (w *tarGzipWriter) Close() error {
	if err := w.tarWriter.Close(); err != nil {
		return err
	}
	return w.gzWriter.Close()
}

type tarZstdWriter struct {
	zstWriter *zstd.Encoder
	tarWriter *tar.Writer
}

func (w *tarZstdWriter) Write(p []byte) (n int, err error) {
	return w.tarWriter.Write(p)
}

func (w *tarZstdWriter) Close() error {
	if err := w.tarWriter.Close(); err != nil {
		return err
	}
	return w.zstWriter.Close()
}

// DecompressFile decompresses a file
func DecompressFile(source, destination string) (*CompressionResult, error) {
	startTime := time.Now()
	
	method := getCompressionMethod(source)
	
	sourceFile, err := os.Open(source)
	if err != nil {
		return nil, fmt.Errorf("failed to open source file: %w", err)
	}
	defer sourceFile.Close()
	
	sourceInfo, err := sourceFile.Stat()
	if err != nil {
		return nil, fmt.Errorf("failed to get source file info: %w", err)
	}
	
	var reader io.ReadCloser
	switch method {
	case "gzip", "tar.gz":
		reader, err = gzip.NewReader(sourceFile)
		if err != nil {
			return nil, fmt.Errorf("failed to create gzip reader: %w", err)
		}
	case "zstd", "tar.zst":
		decoder, err := zstd.NewReader(sourceFile)
		if err != nil {
			return nil, fmt.Errorf("failed to create zstd decoder: %w", err)
		}
		reader = decoder.IOReadCloser()
	default:
		return nil, fmt.Errorf("unsupported decompression method: %s", method)
	}
	defer reader.Close()
	
	var decompressedSize int64
	
	if strings.Contains(method, "tar") {
		decompressedSize, err = extractTar(reader, destination)
	} else {
		decompressedSize, err = extractSingleFile(reader, destination)
	}
	
	if err != nil {
		return nil, err
	}
	
	duration := time.Since(startTime)
	compressionRatio := float64(sourceInfo.Size()) / float64(decompressedSize)
	
	return &CompressionResult{
		OriginalSize:     decompressedSize,
		CompressedSize:   sourceInfo.Size(),
		CompressionRatio: compressionRatio,
		Duration:         duration,
		Method:           method,
		Success:          true,
	}, nil
}

func extractSingleFile(reader io.Reader, destination string) (int64, error) {
	destFile, err := os.Create(destination)
	if err != nil {
		return 0, fmt.Errorf("failed to create destination file: %w", err)
	}
	defer destFile.Close()
	
	size, err := io.Copy(destFile, reader)
	if err != nil {
		return 0, fmt.Errorf("failed to decompress file: %w", err)
	}
	
	return size, nil
}

func extractTar(reader io.Reader, destination string) (int64, error) {
	tarReader := tar.NewReader(reader)
	var totalSize int64
	
	for {
		header, err := tarReader.Next()
		if err == io.EOF {
			break
		}
		if err != nil {
			return 0, fmt.Errorf("failed to read tar header: %w", err)
		}
		
		path := filepath.Join(destination, header.Name)
		
		switch header.Typeflag {
		case tar.TypeDir:
			if err := os.MkdirAll(path, os.FileMode(header.Mode)); err != nil {
				return 0, fmt.Errorf("failed to create directory: %w", err)
			}
		case tar.TypeReg:
			if err := os.MkdirAll(filepath.Dir(path), 0755); err != nil {
				return 0, fmt.Errorf("failed to create parent directory: %w", err)
			}
			
			file, err := os.Create(path)
			if err != nil {
				return 0, fmt.Errorf("failed to create file: %w", err)
			}
			
			size, err := io.Copy(file, tarReader)
			file.Close()
			if err != nil {
				return 0, fmt.Errorf("failed to extract file: %w", err)
			}
			
			if err := os.Chmod(path, os.FileMode(header.Mode)); err != nil {
				return 0, fmt.Errorf("failed to set file permissions: %w", err)
			}
			
			totalSize += size
		}
	}
	
	return totalSize, nil
}