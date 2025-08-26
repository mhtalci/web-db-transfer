package network

import (
	"fmt"
	"net"
	"sync"
	"time"
)

type ConnectionPool struct {
	mu          sync.RWMutex
	connections map[string]*pooledConnection
	maxConns    int
	timeout     time.Duration
}

type pooledConnection struct {
	conn      net.Conn
	lastUsed  time.Time
	inUse     bool
}

type ConcurrentOperationResult struct {
	Results     []interface{} `json:"results"`
	Errors      []string      `json:"errors"`
	Duration    time.Duration `json:"duration_ms"`
	Concurrency int           `json:"concurrency"`
	Success     bool          `json:"success"`
}

// NewConnectionPool creates a new connection pool
func NewConnectionPool(maxConns int, timeout time.Duration) *ConnectionPool {
	return &ConnectionPool{
		connections: make(map[string]*pooledConnection),
		maxConns:    maxConns,
		timeout:     timeout,
	}
}

// GetConnection gets a connection from the pool or creates a new one
func (cp *ConnectionPool) GetConnection(address string) (net.Conn, error) {
	cp.mu.Lock()
	defer cp.mu.Unlock()

	// Check if we have an available connection
	if pooled, exists := cp.connections[address]; exists && !pooled.inUse {
		// Check if connection is still valid and not too old
		if time.Since(pooled.lastUsed) < cp.timeout {
			pooled.inUse = true
			pooled.lastUsed = time.Now()
			return pooled.conn, nil
		} else {
			// Connection is too old, close it
			pooled.conn.Close()
			delete(cp.connections, address)
		}
	}

	// Create new connection
	conn, err := net.DialTimeout("tcp", address, cp.timeout)
	if err != nil {
		return nil, fmt.Errorf("failed to connect to %s: %w", address, err)
	}

	// Add to pool if we have space
	if len(cp.connections) < cp.maxConns {
		cp.connections[address] = &pooledConnection{
			conn:     conn,
			lastUsed: time.Now(),
			inUse:    true,
		}
	}

	return conn, nil
}

// ReleaseConnection releases a connection back to the pool
func (cp *ConnectionPool) ReleaseConnection(address string, conn net.Conn) {
	cp.mu.Lock()
	defer cp.mu.Unlock()

	if pooled, exists := cp.connections[address]; exists && pooled.conn == conn {
		pooled.inUse = false
		pooled.lastUsed = time.Now()
	}
}

// Close closes all connections in the pool
func (cp *ConnectionPool) Close() {
	cp.mu.Lock()
	defer cp.mu.Unlock()

	for _, pooled := range cp.connections {
		pooled.conn.Close()
	}
	cp.connections = make(map[string]*pooledConnection)
}

// ConcurrentPing performs concurrent ping operations to multiple hosts
func ConcurrentPing(hosts []string, timeout time.Duration, maxConcurrency int) (*ConcurrentOperationResult, error) {
	startTime := time.Now()
	
	semaphore := make(chan struct{}, maxConcurrency)
	var wg sync.WaitGroup
	var mu sync.Mutex
	
	results := make([]interface{}, len(hosts))
	errors := make([]string, len(hosts))

	for i, host := range hosts {
		wg.Add(1)
		go func(index int, hostname string) {
			defer wg.Done()

			// Acquire semaphore
			semaphore <- struct{}{}
			defer func() { <-semaphore }()

			// Perform ping (TCP connection test)
			result, err := pingHost(hostname, timeout)
			
			mu.Lock()
			if err != nil {
				errors[index] = err.Error()
			} else {
				results[index] = result
			}
			mu.Unlock()
		}(i, host)
	}

	wg.Wait()

	// Count successful operations
	successCount := 0
	for i := range results {
		if results[i] != nil {
			successCount++
		}
	}

	return &ConcurrentOperationResult{
		Results:     results,
		Errors:      errors,
		Duration:    time.Since(startTime),
		Concurrency: maxConcurrency,
		Success:     successCount > 0,
	}, nil
}

type PingResult struct {
	Host         string        `json:"host"`
	Port         int           `json:"port"`
	Connected    bool          `json:"connected"`
	ResponseTime time.Duration `json:"response_time_ms"`
	Error        string        `json:"error,omitempty"`
}

func pingHost(host string, timeout time.Duration) (*PingResult, error) {
	startTime := time.Now()
	
	// Default to port 80 if no port specified
	address := host
	if !containsPort(host) {
		address = net.JoinHostPort(host, "80")
	}

	conn, err := net.DialTimeout("tcp", address, timeout)
	responseTime := time.Since(startTime)
	
	result := &PingResult{
		Host:         host,
		Port:         80,
		ResponseTime: responseTime,
	}

	if err != nil {
		result.Connected = false
		result.Error = err.Error()
		return result, err
	}

	conn.Close()
	result.Connected = true
	return result, nil
}

func containsPort(host string) bool {
	_, _, err := net.SplitHostPort(host)
	return err == nil
}

// ConcurrentPortScan performs concurrent port scanning
func ConcurrentPortScan(host string, ports []int, timeout time.Duration, maxConcurrency int) (*ConcurrentOperationResult, error) {
	startTime := time.Now()
	
	semaphore := make(chan struct{}, maxConcurrency)
	var wg sync.WaitGroup
	var mu sync.Mutex
	
	results := make([]interface{}, len(ports))
	errors := make([]string, len(ports))

	for i, port := range ports {
		wg.Add(1)
		go func(index, portNum int) {
			defer wg.Done()

			// Acquire semaphore
			semaphore <- struct{}{}
			defer func() { <-semaphore }()

			// Scan port
			result, err := scanPort(host, portNum, timeout)
			
			mu.Lock()
			if err != nil {
				errors[index] = err.Error()
			} else {
				results[index] = result
			}
			mu.Unlock()
		}(i, port)
	}

	wg.Wait()

	// Count open ports
	openPorts := 0
	for i := range results {
		if result, ok := results[i].(*PortScanResult); ok && result.Open {
			openPorts++
		}
	}

	return &ConcurrentOperationResult{
		Results:     results,
		Errors:      errors,
		Duration:    time.Since(startTime),
		Concurrency: maxConcurrency,
		Success:     openPorts > 0,
	}, nil
}

type PortScanResult struct {
	Host         string        `json:"host"`
	Port         int           `json:"port"`
	Open         bool          `json:"open"`
	ResponseTime time.Duration `json:"response_time_ms"`
	Service      string        `json:"service,omitempty"`
}

func scanPort(host string, port int, timeout time.Duration) (*PortScanResult, error) {
	startTime := time.Now()
	address := net.JoinHostPort(host, fmt.Sprintf("%d", port))
	
	conn, err := net.DialTimeout("tcp", address, timeout)
	responseTime := time.Since(startTime)
	
	result := &PortScanResult{
		Host:         host,
		Port:         port,
		ResponseTime: responseTime,
		Service:      getServiceName(port),
	}

	if err != nil {
		result.Open = false
		return result, nil // Not an error, just closed port
	}

	conn.Close()
	result.Open = true
	return result, nil
}

func getServiceName(port int) string {
	services := map[int]string{
		21:   "FTP",
		22:   "SSH",
		23:   "Telnet",
		25:   "SMTP",
		53:   "DNS",
		80:   "HTTP",
		110:  "POP3",
		143:  "IMAP",
		443:  "HTTPS",
		993:  "IMAPS",
		995:  "POP3S",
		3306: "MySQL",
		5432: "PostgreSQL",
		6379: "Redis",
		27017: "MongoDB",
	}
	
	if service, exists := services[port]; exists {
		return service
	}
	return "Unknown"
}

// ConcurrentDNSLookup performs concurrent DNS lookups
func ConcurrentDNSLookup(domains []string, maxConcurrency int) (*ConcurrentOperationResult, error) {
	startTime := time.Now()
	
	semaphore := make(chan struct{}, maxConcurrency)
	var wg sync.WaitGroup
	var mu sync.Mutex
	
	results := make([]interface{}, len(domains))
	errors := make([]string, len(domains))

	for i, domain := range domains {
		wg.Add(1)
		go func(index int, domainName string) {
			defer wg.Done()

			// Acquire semaphore
			semaphore <- struct{}{}
			defer func() { <-semaphore }()

			// Perform DNS lookup
			result, err := lookupDomain(domainName)
			
			mu.Lock()
			if err != nil {
				errors[index] = err.Error()
			} else {
				results[index] = result
			}
			mu.Unlock()
		}(i, domain)
	}

	wg.Wait()

	// Count successful lookups
	successCount := 0
	for i := range results {
		if results[i] != nil {
			successCount++
		}
	}

	return &ConcurrentOperationResult{
		Results:     results,
		Errors:      errors,
		Duration:    time.Since(startTime),
		Concurrency: maxConcurrency,
		Success:     successCount > 0,
	}, nil
}

type DNSLookupResult struct {
	Domain    string   `json:"domain"`
	IPs       []string `json:"ips"`
	CNAME     string   `json:"cname,omitempty"`
	MX        []string `json:"mx,omitempty"`
	TXT       []string `json:"txt,omitempty"`
}

func lookupDomain(domain string) (*DNSLookupResult, error) {
	result := &DNSLookupResult{
		Domain: domain,
	}

	// A record lookup
	ips, err := net.LookupIP(domain)
	if err != nil {
		return nil, fmt.Errorf("failed to lookup IP for %s: %w", domain, err)
	}

	for _, ip := range ips {
		result.IPs = append(result.IPs, ip.String())
	}

	// CNAME lookup
	cname, err := net.LookupCNAME(domain)
	if err == nil && cname != domain+"." {
		result.CNAME = cname
	}

	// MX record lookup
	mxRecords, err := net.LookupMX(domain)
	if err == nil {
		for _, mx := range mxRecords {
			result.MX = append(result.MX, fmt.Sprintf("%s (priority: %d)", mx.Host, mx.Pref))
		}
	}

	// TXT record lookup
	txtRecords, err := net.LookupTXT(domain)
	if err == nil {
		result.TXT = txtRecords
	}

	return result, nil
}

// WorkerPool represents a pool of workers for concurrent operations
type WorkerPool struct {
	workers    int
	jobQueue   chan func()
	quit       chan bool
	wg         sync.WaitGroup
}

// NewWorkerPool creates a new worker pool
func NewWorkerPool(workers int) *WorkerPool {
	return &WorkerPool{
		workers:  workers,
		jobQueue: make(chan func(), workers*2),
		quit:     make(chan bool),
	}
}

// Start starts the worker pool
func (wp *WorkerPool) Start() {
	for i := 0; i < wp.workers; i++ {
		wp.wg.Add(1)
		go wp.worker()
	}
}

// Stop stops the worker pool
func (wp *WorkerPool) Stop() {
	close(wp.quit)
	wp.wg.Wait()
}

// Submit submits a job to the worker pool
func (wp *WorkerPool) Submit(job func()) {
	select {
	case wp.jobQueue <- job:
	case <-wp.quit:
		return
	}
}

func (wp *WorkerPool) worker() {
	defer wp.wg.Done()
	
	for {
		select {
		case job := <-wp.jobQueue:
			job()
		case <-wp.quit:
			return
		}
	}
}