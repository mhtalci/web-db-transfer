package main

import (
	"encoding/json"
	"fmt"
	"log"
	"os"

	"migration-engine/internal/fileops"
	"migration-engine/internal/monitoring"
	"migration-engine/internal/network"
)

type Command struct {
	Operation string                 `json:"operation"`
	Args      map[string]interface{} `json:"args"`
}

type Response struct {
	Success bool        `json:"success"`
	Data    interface{} `json:"data,omitempty"`
	Error   string      `json:"error,omitempty"`
}

func main() {
	if len(os.Args) < 2 {
		printUsage()
		os.Exit(1)
	}

	operation := os.Args[1]
	
	switch operation {
	case "copy":
		handleCopy()
	case "checksum":
		handleChecksum()
	case "compress":
		handleCompress()
	case "monitor":
		handleMonitor()
	case "transfer":
		handleTransfer()
	case "version":
		handleVersion()
	default:
		respondError(fmt.Sprintf("Unknown operation: %s", operation))
	}
}

func printUsage() {
	fmt.Println("Migration Engine - High Performance Operations")
	fmt.Println("Usage: migration-engine <operation> [options]")
	fmt.Println("")
	fmt.Println("Operations:")
	fmt.Println("  copy      - High-speed file copying")
	fmt.Println("  checksum  - Parallel checksum calculation")
	fmt.Println("  compress  - File compression/decompression")
	fmt.Println("  monitor   - System resource monitoring")
	fmt.Println("  transfer  - Network transfer operations")
	fmt.Println("  version   - Show version information")
}

func handleCopy() {
	if len(os.Args) < 6 {
		respondError("copy requires --source <path> --destination <path>")
		return
	}

	var source, destination string
	for i := 2; i < len(os.Args)-1; i++ {
		switch os.Args[i] {
		case "--source":
			source = os.Args[i+1]
		case "--destination":
			destination = os.Args[i+1]
		}
	}

	if source == "" || destination == "" {
		respondError("Both --source and --destination are required")
		return
	}

	result, err := fileops.CopyFile(source, destination)
	if err != nil {
		respondError(err.Error())
		return
	}

	respondSuccess(result)
}

func handleChecksum() {
	if len(os.Args) < 4 {
		respondError("checksum requires --files <file1> [file2] ...")
		return
	}

	var files []string
	collectFiles := false
	for i := 2; i < len(os.Args); i++ {
		if os.Args[i] == "--files" {
			collectFiles = true
			continue
		}
		if collectFiles {
			files = append(files, os.Args[i])
		}
	}

	if len(files) == 0 {
		respondError("No files specified")
		return
	}

	result, err := fileops.CalculateChecksums(files)
	if err != nil {
		respondError(err.Error())
		return
	}

	respondSuccess(result)
}

func handleCompress() {
	if len(os.Args) < 6 {
		respondError("compress requires --source <path> --destination <path>")
		return
	}

	var source, destination string
	for i := 2; i < len(os.Args)-1; i++ {
		switch os.Args[i] {
		case "--source":
			source = os.Args[i+1]
		case "--destination":
			destination = os.Args[i+1]
		}
	}

	result, err := fileops.CompressFile(source, destination)
	if err != nil {
		respondError(err.Error())
		return
	}

	respondSuccess(result)
}

func handleMonitor() {
	result, err := monitoring.GetSystemStats()
	if err != nil {
		respondError(err.Error())
		return
	}

	respondSuccess(result)
}

func handleTransfer() {
	if len(os.Args) < 8 {
		respondError("transfer requires --source <url> --destination <url> --method <method>")
		return
	}

	var source, destination, method string
	for i := 2; i < len(os.Args)-1; i++ {
		switch os.Args[i] {
		case "--source":
			source = os.Args[i+1]
		case "--destination":
			destination = os.Args[i+1]
		case "--method":
			method = os.Args[i+1]
		}
	}

	result, err := network.Transfer(source, destination, method)
	if err != nil {
		respondError(err.Error())
		return
	}

	respondSuccess(result)
}

func handleVersion() {
	version := map[string]string{
		"version": "1.0.0",
		"go":      "1.21+",
		"build":   "development",
	}
	respondSuccess(version)
}

func respondSuccess(data interface{}) {
	response := Response{
		Success: true,
		Data:    data,
	}
	output, _ := json.Marshal(response)
	fmt.Println(string(output))
}

func respondError(message string) {
	response := Response{
		Success: false,
		Error:   message,
	}
	output, _ := json.Marshal(response)
	fmt.Println(string(output))
	log.Printf("Error: %s", message)
}