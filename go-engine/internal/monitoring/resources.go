package monitoring

import (
	"runtime"
	"time"

	"github.com/shirou/gopsutil/v3/cpu"
	"github.com/shirou/gopsutil/v3/disk"
	"github.com/shirou/gopsutil/v3/mem"
	"github.com/shirou/gopsutil/v3/net"
)

type SystemStats struct {
	Timestamp    time.Time    `json:"timestamp"`
	CPU          CPUStats     `json:"cpu"`
	Memory       MemoryStats  `json:"memory"`
	Disk         []DiskStats  `json:"disk"`
	Network      NetworkStats `json:"network"`
	GoRuntime    RuntimeStats `json:"go_runtime"`
}

type CPUStats struct {
	UsagePercent []float64 `json:"usage_percent"`
	Count        int       `json:"count"`
	ModelName    string    `json:"model_name"`
}

type MemoryStats struct {
	Total       uint64  `json:"total"`
	Available   uint64  `json:"available"`
	Used        uint64  `json:"used"`
	UsedPercent float64 `json:"used_percent"`
	Free        uint64  `json:"free"`
}

type DiskStats struct {
	Device      string  `json:"device"`
	Mountpoint  string  `json:"mountpoint"`
	Fstype      string  `json:"fstype"`
	Total       uint64  `json:"total"`
	Free        uint64  `json:"free"`
	Used        uint64  `json:"used"`
	UsedPercent float64 `json:"used_percent"`
}

type NetworkStats struct {
	BytesSent   uint64 `json:"bytes_sent"`
	BytesRecv   uint64 `json:"bytes_recv"`
	PacketsSent uint64 `json:"packets_sent"`
	PacketsRecv uint64 `json:"packets_recv"`
}

type RuntimeStats struct {
	GoVersion    string `json:"go_version"`
	NumGoroutine int    `json:"num_goroutine"`
	NumCPU       int    `json:"num_cpu"`
	MemStats     struct {
		Alloc        uint64 `json:"alloc"`
		TotalAlloc   uint64 `json:"total_alloc"`
		Sys          uint64 `json:"sys"`
		NumGC        uint32 `json:"num_gc"`
		HeapAlloc    uint64 `json:"heap_alloc"`
		HeapSys      uint64 `json:"heap_sys"`
		HeapInuse    uint64 `json:"heap_inuse"`
		HeapReleased uint64 `json:"heap_released"`
	} `json:"mem_stats"`
}

// GetSystemStats collects comprehensive system statistics
func GetSystemStats() (*SystemStats, error) {
	stats := &SystemStats{
		Timestamp: time.Now(),
	}

	// CPU stats
	cpuPercent, err := cpu.Percent(time.Second, true)
	if err != nil {
		return nil, err
	}
	
	cpuInfo, err := cpu.Info()
	if err != nil {
		return nil, err
	}

	stats.CPU = CPUStats{
		UsagePercent: cpuPercent,
		Count:        len(cpuPercent),
	}
	
	if len(cpuInfo) > 0 {
		stats.CPU.ModelName = cpuInfo[0].ModelName
	}

	// Memory stats
	memInfo, err := mem.VirtualMemory()
	if err != nil {
		return nil, err
	}

	stats.Memory = MemoryStats{
		Total:       memInfo.Total,
		Available:   memInfo.Available,
		Used:        memInfo.Used,
		UsedPercent: memInfo.UsedPercent,
		Free:        memInfo.Free,
	}

	// Disk stats
	diskPartitions, err := disk.Partitions(false)
	if err != nil {
		return nil, err
	}

	for _, partition := range diskPartitions {
		diskUsage, err := disk.Usage(partition.Mountpoint)
		if err != nil {
			continue // Skip partitions we can't access
		}

		stats.Disk = append(stats.Disk, DiskStats{
			Device:      partition.Device,
			Mountpoint:  partition.Mountpoint,
			Fstype:      partition.Fstype,
			Total:       diskUsage.Total,
			Free:        diskUsage.Free,
			Used:        diskUsage.Used,
			UsedPercent: diskUsage.UsedPercent,
		})
	}

	// Network stats
	netStats, err := net.IOCounters(false)
	if err != nil {
		return nil, err
	}

	if len(netStats) > 0 {
		stats.Network = NetworkStats{
			BytesSent:   netStats[0].BytesSent,
			BytesRecv:   netStats[0].BytesRecv,
			PacketsSent: netStats[0].PacketsSent,
			PacketsRecv: netStats[0].PacketsRecv,
		}
	}

	// Go runtime stats
	var memStats runtime.MemStats
	runtime.ReadMemStats(&memStats)

	stats.GoRuntime = RuntimeStats{
		GoVersion:    runtime.Version(),
		NumGoroutine: runtime.NumGoroutine(),
		NumCPU:       runtime.NumCPU(),
	}
	
	stats.GoRuntime.MemStats.Alloc = memStats.Alloc
	stats.GoRuntime.MemStats.TotalAlloc = memStats.TotalAlloc
	stats.GoRuntime.MemStats.Sys = memStats.Sys
	stats.GoRuntime.MemStats.NumGC = memStats.NumGC
	stats.GoRuntime.MemStats.HeapAlloc = memStats.HeapAlloc
	stats.GoRuntime.MemStats.HeapSys = memStats.HeapSys
	stats.GoRuntime.MemStats.HeapInuse = memStats.HeapInuse
	stats.GoRuntime.MemStats.HeapReleased = memStats.HeapReleased

	return stats, nil
}

// MonitorResources continuously monitors system resources
func MonitorResources(interval time.Duration, callback func(*SystemStats)) {
	ticker := time.NewTicker(interval)
	defer ticker.Stop()

	for range ticker.C {
		stats, err := GetSystemStats()
		if err != nil {
			continue
		}
		callback(stats)
	}
}

// GetDiskUsage gets disk usage for a specific path
func GetDiskUsage(path string) (*DiskStats, error) {
	usage, err := disk.Usage(path)
	if err != nil {
		return nil, err
	}

	return &DiskStats{
		Mountpoint:  path,
		Total:       usage.Total,
		Free:        usage.Free,
		Used:        usage.Used,
		UsedPercent: usage.UsedPercent,
	}, nil
}

// GetMemoryUsage gets current memory usage
func GetMemoryUsage() (*MemoryStats, error) {
	memInfo, err := mem.VirtualMemory()
	if err != nil {
		return nil, err
	}

	return &MemoryStats{
		Total:       memInfo.Total,
		Available:   memInfo.Available,
		Used:        memInfo.Used,
		UsedPercent: memInfo.UsedPercent,
		Free:        memInfo.Free,
	}, nil
}

// GetCPUUsage gets current CPU usage
func GetCPUUsage() (*CPUStats, error) {
	cpuPercent, err := cpu.Percent(time.Second, true)
	if err != nil {
		return nil, err
	}

	cpuInfo, err := cpu.Info()
	if err != nil {
		return nil, err
	}

	stats := &CPUStats{
		UsagePercent: cpuPercent,
		Count:        len(cpuPercent),
	}

	if len(cpuInfo) > 0 {
		stats.ModelName = cpuInfo[0].ModelName
	}

	return stats, nil
}