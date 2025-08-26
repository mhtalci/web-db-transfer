package monitoring

import (
	"sync"
	"time"
)

type PerformanceMetrics struct {
	mu                sync.RWMutex
	OperationMetrics  map[string]*OperationStats `json:"operation_metrics"`
	TransferMetrics   *TransferStats             `json:"transfer_metrics"`
	SystemMetrics     *SystemStats               `json:"system_metrics"`
	StartTime         time.Time                  `json:"start_time"`
	LastUpdated       time.Time                  `json:"last_updated"`
}

type OperationStats struct {
	Name            string        `json:"name"`
	Count           int64         `json:"count"`
	TotalDuration   time.Duration `json:"total_duration"`
	AverageDuration time.Duration `json:"average_duration"`
	MinDuration     time.Duration `json:"min_duration"`
	MaxDuration     time.Duration `json:"max_duration"`
	ErrorCount      int64         `json:"error_count"`
	LastExecution   time.Time     `json:"last_execution"`
}

type TransferStats struct {
	TotalBytes       int64         `json:"total_bytes"`
	TransferredBytes int64         `json:"transferred_bytes"`
	TransferRate     float64       `json:"transfer_rate_mbps"`
	Duration         time.Duration `json:"duration"`
	FilesProcessed   int64         `json:"files_processed"`
	FilesTotal       int64         `json:"files_total"`
	ErrorCount       int64         `json:"error_count"`
	StartTime        time.Time     `json:"start_time"`
	EstimatedETA     time.Duration `json:"estimated_eta"`
}

// NewPerformanceMetrics creates a new performance metrics tracker
func NewPerformanceMetrics() *PerformanceMetrics {
	return &PerformanceMetrics{
		OperationMetrics: make(map[string]*OperationStats),
		StartTime:        time.Now(),
		LastUpdated:      time.Now(),
	}
}

// RecordOperation records the execution of an operation
func (pm *PerformanceMetrics) RecordOperation(name string, duration time.Duration, success bool) {
	pm.mu.Lock()
	defer pm.mu.Unlock()

	stats, exists := pm.OperationMetrics[name]
	if !exists {
		stats = &OperationStats{
			Name:        name,
			MinDuration: duration,
			MaxDuration: duration,
		}
		pm.OperationMetrics[name] = stats
	}

	stats.Count++
	stats.TotalDuration += duration
	stats.AverageDuration = stats.TotalDuration / time.Duration(stats.Count)
	stats.LastExecution = time.Now()

	if duration < stats.MinDuration {
		stats.MinDuration = duration
	}
	if duration > stats.MaxDuration {
		stats.MaxDuration = duration
	}

	if !success {
		stats.ErrorCount++
	}

	pm.LastUpdated = time.Now()
}

// UpdateTransferStats updates transfer statistics
func (pm *PerformanceMetrics) UpdateTransferStats(totalBytes, transferredBytes int64, filesProcessed, filesTotal int64) {
	pm.mu.Lock()
	defer pm.mu.Unlock()

	if pm.TransferMetrics == nil {
		pm.TransferMetrics = &TransferStats{
			StartTime: time.Now(),
		}
	}

	pm.TransferMetrics.TotalBytes = totalBytes
	pm.TransferMetrics.TransferredBytes = transferredBytes
	pm.TransferMetrics.FilesProcessed = filesProcessed
	pm.TransferMetrics.FilesTotal = filesTotal
	pm.TransferMetrics.Duration = time.Since(pm.TransferMetrics.StartTime)

	// Calculate transfer rate in MB/s
	if pm.TransferMetrics.Duration.Seconds() > 0 {
		pm.TransferMetrics.TransferRate = float64(transferredBytes) / (1024 * 1024) / pm.TransferMetrics.Duration.Seconds()
	}

	// Calculate ETA
	if transferredBytes > 0 && totalBytes > transferredBytes {
		remainingBytes := totalBytes - transferredBytes
		if pm.TransferMetrics.TransferRate > 0 {
			remainingSeconds := float64(remainingBytes) / (1024 * 1024) / pm.TransferMetrics.TransferRate
			pm.TransferMetrics.EstimatedETA = time.Duration(remainingSeconds) * time.Second
		}
	}

	pm.LastUpdated = time.Now()
}

// RecordTransferError records a transfer error
func (pm *PerformanceMetrics) RecordTransferError() {
	pm.mu.Lock()
	defer pm.mu.Unlock()

	if pm.TransferMetrics == nil {
		pm.TransferMetrics = &TransferStats{
			StartTime: time.Now(),
		}
	}

	pm.TransferMetrics.ErrorCount++
	pm.LastUpdated = time.Now()
}

// UpdateSystemMetrics updates system metrics
func (pm *PerformanceMetrics) UpdateSystemMetrics() error {
	stats, err := GetSystemStats()
	if err != nil {
		return err
	}

	pm.mu.Lock()
	defer pm.mu.Unlock()

	pm.SystemMetrics = stats
	pm.LastUpdated = time.Now()

	return nil
}

// GetMetrics returns a copy of current metrics
func (pm *PerformanceMetrics) GetMetrics() *PerformanceMetrics {
	pm.mu.RLock()
	defer pm.mu.RUnlock()

	// Create a deep copy
	copy := &PerformanceMetrics{
		OperationMetrics: make(map[string]*OperationStats),
		StartTime:        pm.StartTime,
		LastUpdated:      pm.LastUpdated,
	}

	for name, stats := range pm.OperationMetrics {
		copy.OperationMetrics[name] = &OperationStats{
			Name:            stats.Name,
			Count:           stats.Count,
			TotalDuration:   stats.TotalDuration,
			AverageDuration: stats.AverageDuration,
			MinDuration:     stats.MinDuration,
			MaxDuration:     stats.MaxDuration,
			ErrorCount:      stats.ErrorCount,
			LastExecution:   stats.LastExecution,
		}
	}

	if pm.TransferMetrics != nil {
		copy.TransferMetrics = &TransferStats{
			TotalBytes:       pm.TransferMetrics.TotalBytes,
			TransferredBytes: pm.TransferMetrics.TransferredBytes,
			TransferRate:     pm.TransferMetrics.TransferRate,
			Duration:         pm.TransferMetrics.Duration,
			FilesProcessed:   pm.TransferMetrics.FilesProcessed,
			FilesTotal:       pm.TransferMetrics.FilesTotal,
			ErrorCount:       pm.TransferMetrics.ErrorCount,
			StartTime:        pm.TransferMetrics.StartTime,
			EstimatedETA:     pm.TransferMetrics.EstimatedETA,
		}
	}

	if pm.SystemMetrics != nil {
		copy.SystemMetrics = pm.SystemMetrics
	}

	return copy
}

// GetOperationStats returns statistics for a specific operation
func (pm *PerformanceMetrics) GetOperationStats(name string) *OperationStats {
	pm.mu.RLock()
	defer pm.mu.RUnlock()

	stats, exists := pm.OperationMetrics[name]
	if !exists {
		return nil
	}

	// Return a copy
	return &OperationStats{
		Name:            stats.Name,
		Count:           stats.Count,
		TotalDuration:   stats.TotalDuration,
		AverageDuration: stats.AverageDuration,
		MinDuration:     stats.MinDuration,
		MaxDuration:     stats.MaxDuration,
		ErrorCount:      stats.ErrorCount,
		LastExecution:   stats.LastExecution,
	}
}

// GetTransferProgress returns current transfer progress as percentage
func (pm *PerformanceMetrics) GetTransferProgress() float64 {
	pm.mu.RLock()
	defer pm.mu.RUnlock()

	if pm.TransferMetrics == nil || pm.TransferMetrics.TotalBytes == 0 {
		return 0.0
	}

	return float64(pm.TransferMetrics.TransferredBytes) / float64(pm.TransferMetrics.TotalBytes) * 100.0
}

// Reset resets all metrics
func (pm *PerformanceMetrics) Reset() {
	pm.mu.Lock()
	defer pm.mu.Unlock()

	pm.OperationMetrics = make(map[string]*OperationStats)
	pm.TransferMetrics = nil
	pm.SystemMetrics = nil
	pm.StartTime = time.Now()
	pm.LastUpdated = time.Now()
}

// GetSummary returns a summary of performance metrics
func (pm *PerformanceMetrics) GetSummary() map[string]interface{} {
	pm.mu.RLock()
	defer pm.mu.RUnlock()

	summary := make(map[string]interface{})
	
	// Overall stats
	summary["uptime"] = time.Since(pm.StartTime)
	summary["last_updated"] = pm.LastUpdated
	summary["total_operations"] = len(pm.OperationMetrics)

	// Operation summary
	var totalOperationCount int64
	var totalErrorCount int64
	for _, stats := range pm.OperationMetrics {
		totalOperationCount += stats.Count
		totalErrorCount += stats.ErrorCount
	}
	summary["total_operation_count"] = totalOperationCount
	summary["total_error_count"] = totalErrorCount
	
	if totalOperationCount > 0 {
		summary["error_rate"] = float64(totalErrorCount) / float64(totalOperationCount) * 100.0
	}

	// Transfer summary
	if pm.TransferMetrics != nil {
		summary["transfer_progress"] = pm.GetTransferProgress()
		summary["transfer_rate"] = pm.TransferMetrics.TransferRate
		summary["files_processed"] = pm.TransferMetrics.FilesProcessed
		summary["files_total"] = pm.TransferMetrics.FilesTotal
		summary["estimated_eta"] = pm.TransferMetrics.EstimatedETA
	}

	return summary
}