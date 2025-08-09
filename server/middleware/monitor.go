package middleware

import (
	"runtime"
	"sync"
	"sync/atomic"
	"time"

	"github.com/gin-gonic/gin"
)

type Metrics struct {
	TotalRequests uint64
	TotalErrors   uint64
	ResponseTimes []float64
	PerEndpoint   map[string]uint64
	StatusCodes   map[int]uint64
	QueueDepth    uint64 // external setter
	mutex         sync.RWMutex
}

var (
	metrics = &Metrics{ResponseTimes: make([]float64, 0, 1000), PerEndpoint: map[string]uint64{}, StatusCodes: map[int]uint64{}}
)

// Monitor collects request metrics
func Monitor() gin.HandlerFunc {
	return func(c *gin.Context) {
		start := time.Now()
		c.Next()
		elapsed := time.Since(start).Seconds()
		atomic.AddUint64(&metrics.TotalRequests, 1)
		if c.Writer.Status() >= 400 { atomic.AddUint64(&metrics.TotalErrors, 1) }
		metrics.mutex.Lock()
		if len(metrics.ResponseTimes) >= 1000 { metrics.ResponseTimes = metrics.ResponseTimes[1:] }
		metrics.ResponseTimes = append(metrics.ResponseTimes, elapsed)
		metrics.PerEndpoint[c.FullPath()]++
		metrics.StatusCodes[c.Writer.Status()]++
		metrics.mutex.Unlock()
	}
}

// SetQueueDepth allows queue package to update depth (optional injection)
func SetQueueDepth(depth uint64) { atomic.StoreUint64(&metrics.QueueDepth, depth) }

// GetMetrics exposes runtime stats
func GetMetrics() gin.HandlerFunc {
	return func(c *gin.Context) {
		var mem runtime.MemStats
		runtime.ReadMemStats(&mem)
		metrics.mutex.RLock()
		avg := 0.0
		if n := len(metrics.ResponseTimes); n > 0 {
			sum := 0.0
			for _, v := range metrics.ResponseTimes { sum += v }
			avg = sum / float64(n)
		}
		perEndpoint := make(map[string]uint64, len(metrics.PerEndpoint))
		for k, v := range metrics.PerEndpoint { perEndpoint[k] = v }
		statusCodes := make(map[int]uint64, len(metrics.StatusCodes))
		for k, v := range metrics.StatusCodes { statusCodes[k] = v }
		metrics.mutex.RUnlock()
		c.JSON(200, gin.H{
			"total_requests": atomic.LoadUint64(&metrics.TotalRequests),
			"total_errors": atomic.LoadUint64(&metrics.TotalErrors),
			"avg_response_time": avg,
			"goroutines": runtime.NumGoroutine(),
			"memory": gin.H{"alloc": mem.Alloc, "total_alloc": mem.TotalAlloc, "sys": mem.Sys, "num_gc": mem.NumGC},
			"per_endpoint": perEndpoint,
			"status_codes": statusCodes,
			"queue_depth": atomic.LoadUint64(&metrics.QueueDepth),
		})
	}
}
