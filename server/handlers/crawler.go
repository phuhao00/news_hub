package handlers

import (
	"bytes"
	"fmt"
	"io"
	"net/http"
	"time"

	"github.com/gin-gonic/gin"
)

const PYTHON_CRAWLER_URL = "http://localhost:8001"

// ProxyCrawlerTrigger 代理爬虫触发请求到Python服务
func ProxyCrawlerTrigger(c *gin.Context) {
	// 读取请求体
	body, err := io.ReadAll(c.Request.Body)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "读取请求失败"})
		return
	}

	// 创建到Python服务的请求
	req, err := http.NewRequest("POST", PYTHON_CRAWLER_URL+"/crawl/news", bytes.NewBuffer(body))
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "创建请求失败"})
		return
	}

	// 复制请求头
	req.Header.Set("Content-Type", "application/json")

	// 发送请求
	client := &http.Client{Timeout: 30 * time.Second}
	resp, err := client.Do(req)
	if err != nil {
		c.JSON(http.StatusServiceUnavailable, gin.H{
			"error": "Python爬虫服务不可用",
			"details": err.Error(),
		})
		return
	}
	defer resp.Body.Close()

	// 读取响应
	respBody, err := io.ReadAll(resp.Body)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "读取响应失败"})
		return
	}

	// 转发响应
	c.Header("Content-Type", "application/json")
	c.Status(resp.StatusCode)
	c.Writer.Write(respBody)
}

// ProxyCrawlerStatus 代理爬虫状态请求到Python服务
func ProxyCrawlerStatus(c *gin.Context) {
	// 检查Python服务健康状态
	client := &http.Client{Timeout: 5 * time.Second}
	resp, err := client.Get(PYTHON_CRAWLER_URL + "/health")
	if err != nil {
		c.JSON(http.StatusServiceUnavailable, gin.H{
			"status": "unavailable",
			"message": "Python爬虫服务不可用",
			"error": err.Error(),
		})
		return
	}
	defer resp.Body.Close()

	if resp.StatusCode == http.StatusOK {
		c.JSON(http.StatusOK, gin.H{
			"status": "active",
			"message": "Python爬虫服务正在运行",
			"service_url": PYTHON_CRAWLER_URL,
			"api_docs": PYTHON_CRAWLER_URL + "/docs",
			"last_check": time.Now().Format(time.RFC3339),
		})
	} else {
		c.JSON(http.StatusServiceUnavailable, gin.H{
			"status": "error",
			"message": fmt.Sprintf("Python爬虫服务返回错误状态: %d", resp.StatusCode),
		})
	}
}