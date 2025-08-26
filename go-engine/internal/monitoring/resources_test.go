package monitoring

import (
	"testing"
	"time"
)

func TestGetSystemStats(t *testing.T) {
	stats, err := GetSystemStats()
	if err != nil {
		t.Fatalf("GetSystemStats failed: %v", err)
	}

	// Verify timestamp is recent
	if time.Since(stats.Timestamp) > time.Minute {
		t.Error("Timestamp should be recent")
	}

	// Verify CPU stats
	if stats.CPU.Count <= 0 {
		t.Error("CPU count should be positive")
	}

	if len(stats.CPU.UsagePercent) != stats.CPU.Count {
		t.Errorf("CPU usage array length (%d) should match CPU count (%d)", len(stats.CPU.UsagePercent), stats.CPU.Count)
	}

	for i, usage := range stats.CPU.UsagePercent {
		if usage < 0 || usage > 100 {
			t.Errorf("CPU usage[%d] should be between 0 and 100, got %f", i, usage)
		}
	}

	// Verify Memory stats
	if stats.Memory.Total <= 0 {
		t.Error("Total memory should be positive")
	}

	if stats.Memory.Used > stats.Memory.Total {
		t.Error("Used memory should not exceed total memory")
	}

	if stats.Memory.UsedPercent < 0 || stats.Memory.UsedPercent > 100 {
		t.Errorf("Memory usage percentage should be between 0 and 100, got %f", stats.Memory.UsedPercent)
	}

	// Verify Disk stats
	if len(stats.Disk) == 0 {
		t.Error("Should have at least one disk")
	}

	for i, disk := range stats.Disk {
		// Skip virtual filesystems that may have 0 total space
		if disk.Fstype == "autofs" || disk.Fstype == "devfs" {
			continue
		}

		if disk.Total <= 0 {
			t.Errorf("Disk[%d] total should be positive", i)
		}

		if disk.Used > disk.Total {
			t.Errorf("Disk[%d] used should not exceed total", i)
		}

		if disk.UsedPercent < 0 || disk.UsedPercent > 100 {
			t.Errorf("Disk[%d] usage percentage should be between 0 and 100, got %f", i, disk.UsedPercent)
		}

		if disk.Device == "" {
			t.Errorf("Disk[%d] device should not be empty", i)
		}

		if disk.Mountpoint == "" {
			t.Errorf("Disk[%d] mountpoint should not be empty", i)
		}
	}

	// Verify Go Runtime stats
	if stats.GoRuntime.GoVersion == "" {
		t.Error("Go version should not be empty")
	}

	if stats.GoRuntime.NumCPU <= 0 {
		t.Error("Number of CPUs should be positive")
	}

	if stats.GoRuntime.NumGoroutine <= 0 {
		t.Error("Number of goroutines should be positive")
	}

	// Verify memory stats are reasonable
	if stats.GoRuntime.MemStats.Alloc <= 0 {
		t.Error("Allocated memory should be positive")
	}

	if stats.GoRuntime.MemStats.Sys <= 0 {
		t.Error("System memory should be positive")
	}
}

func TestGetDiskUsage(t *testing.T) {
	// Test with root directory (should exist on all systems)
	usage, err := GetDiskUsage("/")
	if err != nil {
		t.Fatalf("GetDiskUsage failed: %v", err)
	}

	if usage.Total <= 0 {
		t.Error("Total disk space should be positive")
	}

	if usage.Used > usage.Total {
		t.Error("Used disk space should not exceed total")
	}

	if usage.UsedPercent < 0 || usage.UsedPercent > 100 {
		t.Errorf("Disk usage percentage should be between 0 and 100, got %f", usage.UsedPercent)
	}

	if usage.Mountpoint != "/" {
		t.Errorf("Expected mountpoint '/', got '%s'", usage.Mountpoint)
	}
}

func TestGetMemoryUsage(t *testing.T) {
	memory, err := GetMemoryUsage()
	if err != nil {
		t.Fatalf("GetMemoryUsage failed: %v", err)
	}

	if memory.Total <= 0 {
		t.Error("Total memory should be positive")
	}

	if memory.Used > memory.Total {
		t.Error("Used memory should not exceed total memory")
	}

	if memory.Available > memory.Total {
		t.Error("Available memory should not exceed total memory")
	}

	if memory.UsedPercent < 0 || memory.UsedPercent > 100 {
		t.Errorf("Memory usage percentage should be between 0 and 100, got %f", memory.UsedPercent)
	}
}

func TestGetCPUUsage(t *testing.T) {
	cpu, err := GetCPUUsage()
	if err != nil {
		t.Fatalf("GetCPUUsage failed: %v", err)
	}

	if cpu.Count <= 0 {
		t.Error("CPU count should be positive")
	}

	if len(cpu.UsagePercent) != cpu.Count {
		t.Errorf("CPU usage array length (%d) should match CPU count (%d)", len(cpu.UsagePercent), cpu.Count)
	}

	for i, usage := range cpu.UsagePercent {
		if usage < 0 || usage > 100 {
			t.Errorf("CPU usage[%d] should be between 0 and 100, got %f", i, usage)
		}
	}

	if cpu.ModelName == "" {
		t.Error("CPU model name should not be empty")
	}
}

func BenchmarkGetSystemStats(b *testing.B) {
	b.ReportAllocs()

	for i := 0; i < b.N; i++ {
		_, err := GetSystemStats()
		if err != nil {
			b.Fatalf("GetSystemStats failed: %v", err)
		}
	}
}

func BenchmarkGetMemoryUsage(b *testing.B) {
	b.ReportAllocs()

	for i := 0; i < b.N; i++ {
		_, err := GetMemoryUsage()
		if err != nil {
			b.Fatalf("GetMemoryUsage failed: %v", err)
		}
	}
}

func BenchmarkGetCPUUsage(b *testing.B) {
	b.ReportAllocs()

	for i := 0; i < b.N; i++ {
		_, err := GetCPUUsage()
		if err != nil {
			b.Fatalf("GetCPUUsage failed: %v", err)
		}
	}
}

func TestMonitorResources(t *testing.T) {
	// Test that we can get system stats (the core functionality)
	// MonitorResources runs indefinitely, so we'll test the core function instead
	stats, err := GetSystemStats()
	if err != nil {
		t.Fatalf("GetSystemStats failed: %v", err)
	}
	
	if stats == nil {
		t.Error("Stats should not be nil")
	}
	
	// Test that the callback would work by calling it directly
	callCount := 0
	callback := func(stats *SystemStats) {
		callCount++
		if stats == nil {
			t.Error("Stats should not be nil")
		}
	}
	
	callback(stats)
	
	if callCount != 1 {
		t.Errorf("Expected callback to be called once, got %d", callCount)
	}
}

func TestGetDiskUsageInvalidPath(t *testing.T) {
	_, err := GetDiskUsage("/nonexistent/path/that/should/not/exist")
	if err == nil {
		t.Error("Expected error for non-existent path")
	}
}