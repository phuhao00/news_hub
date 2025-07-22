package middleware

import (
	"net/http"
	"sync"
	"time"

	"github.com/gin-gonic/gin"
)

type RateLimiter struct {
	rate     int           // 每个时间窗口允许的请求数
	window   time.Duration // 时间窗口大小
	requests map[string]*RequestCount
	mutex    sync.Mutex
}

type RequestCount struct {
	count    int
	start    time.Time
	blockTil time.Time
}

// NewRateLimiter 创建一个新的限速器
func NewRateLimiter(rate int, window time.Duration) *RateLimiter {
	return &RateLimiter{
		rate:     rate,
		window:   window,
		requests: make(map[string]*RequestCount),
	}
}

// RateLimit 中间件用于限制API请求速率
func RateLimit(rate int, window time.Duration) gin.HandlerFunc {
	limiter := NewRateLimiter(rate, window)

	return func(c *gin.Context) {
		clientIP := c.ClientIP()

		limiter.mutex.Lock()
		defer limiter.mutex.Unlock()

		now := time.Now()
		req, exists := limiter.requests[clientIP]

		if !exists {
			// 新的客户端
			limiter.requests[clientIP] = &RequestCount{
				count: 1,
				start: now,
			}
			c.Next()
			return
		}

		// 检查是否在封禁期
		if now.Before(req.blockTil) {
			c.JSON(http.StatusTooManyRequests, gin.H{
				"error": "请求过于频繁，请稍后再试",
				"retry_after": req.blockTil.Sub(now).Seconds(),
			})
			c.Abort()
			return
		}

		// 检查是否需要重置计数器
		if now.Sub(req.start) >= limiter.window {
			req.count = 1
			req.start = now
			req.blockTil = time.Time{}
			c.Next()
			return
		}

		// 增加计数
		req.count++

		// 检查是否超过限制
		if req.count > limiter.rate {
			// 设置封禁时间为一个时间窗口
			req.blockTil = now.Add(limiter.window)
			c.JSON(http.StatusTooManyRequests, gin.H{
				"error": "请求过于频繁，请稍后再试",
				"retry_after": limiter.window.Seconds(),
			})
			c.Abort()
			return
		}

		c.Next()
	}
}