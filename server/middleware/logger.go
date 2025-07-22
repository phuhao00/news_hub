package middleware

import (
	"fmt"
	"os"
	"path/filepath"
	"time"

	"github.com/gin-gonic/gin"
)

// Logger 中间件用于记录API请求日志
func Logger() gin.HandlerFunc {
	// 确保日志目录存在
	logDir := "logs"
	if err := os.MkdirAll(logDir, 0755); err != nil {
		fmt.Printf("创建日志目录失败：%v\n", err)
		return nil
	}

	// 创建或打开日志文件
	logFile := filepath.Join(logDir, time.Now().Format("2006-01-02")+".log")
	f, err := os.OpenFile(logFile, os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0644)
	if err != nil {
		fmt.Printf("打开日志文件失败：%v\n", err)
		return nil
	}

	return func(c *gin.Context) {
		// 开始时间
		startTime := time.Now()

		// 处理请求
		c.Next()

		// 结束时间
		endTime := time.Now()
		latencyTime := endTime.Sub(startTime)

		// 请求方法
		reqMethod := c.Request.Method
		// 请求路由
		reqUri := c.Request.RequestURI
		// 状态码
		statusCode := c.Writer.Status()
		// 请求IP
		clientIP := c.ClientIP()

		// 日志格式
		logStr := fmt.Sprintf("[%s] %s | %3d | %13v | %15s | %s\n",
			endTime.Format("2006-01-02 15:04:05"),
			reqMethod,
			statusCode,
			latencyTime,
			clientIP,
			reqUri,
		)

		// 写入日志文件
		if _, err := f.WriteString(logStr); err != nil {
			fmt.Printf("写入日志失败：%v\n", err)
		}
	}
}