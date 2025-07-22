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
	mutex         sync.RWMutex
}

var (
	metrics = &Metrics{
		ResponseTimes: make([]float64, 0, 1000),
	}
)

// Monitor 中间件用于收集系统指标
func Monitor() gin.HandlerFunc {
	return func(c *gin.Context) {
		start := time.Now()

		// 处理请求
		c.Next()

		// 增加总请求数
		atomic.AddUint64(&metrics.TotalRequests, 1)

		// 如果是错误响应，增加错误计数
		if c.Writer.Status() >= 400 {
			atomic.AddUint64(&metrics.TotalErrors, 1)
		}

		// 记录响应时间
		responseTime := time.Since(start).Seconds()
		metrics.mutex.Lock()
		if len(metrics.ResponseTimes) >= 1000 {
			// 保持最近1000个请求的响应时间
			metrics.ResponseTimes = metrics.ResponseTimes[1:]
		}
		metrics.ResponseTimes = append(metrics.ResponseTimes, responseTime)
		metrics.mutex.Unlock()
	}
}

// GetMetrics 获取系统指标
func GetMetrics() gin.HandlerFunc {
	return func(c *gin.Context) {
		// 获取内存统计
		var memStats runtime.MemStats
		runtime.ReadMemStats(&memStats)

		// 计算平均响应时间
		metrics.mutex.RLock()
		var avgResponseTime float64
		if len(metrics.ResponseTimes) > 0 {
			sum := 0.0
			for _, t := range metrics.ResponseTimes {
				sum += t
			}
			avgResponseTime = sum / float64(len(metrics.ResponseTimes))
		}
		metrics.mutex.RUnlock()

		// 返回指标数据
		c.JSON(200, gin.H{
			"total_requests":     atomic.LoadUint64(&metrics.TotalRequests),
			"total_errors":       atomic.LoadUint64(&metrics.TotalErrors),
			"avg_response_time":  avgResponseTime,
			"goroutines":        runtime.NumGoroutine(),
			"memory": gin.H{
				"alloc":      memStats.Alloc,
				"total_alloc": memStats.TotalAlloc,
				"sys":        memStats.Sys,
				"num_gc":     memStats.NumGC,
			},
		})
	}
}