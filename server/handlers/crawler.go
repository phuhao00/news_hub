package handlers

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"time"

	"github.com/gin-gonic/gin"
	"go.mongodb.org/mongo-driver/bson/primitive"

	"newshub/config"
	"newshub/models"
)

const PYTHON_CRAWLER_URL = "http://localhost:8001"

// CrawlerTriggerRequest 爬虫触发请求
type CrawlerTriggerRequest struct {
	CreatorIDs []string `json:"creatorIds,omitempty"`
	Platforms  []string `json:"platforms,omitempty"`
}

// ProxyCrawlerTrigger 代理爬虫触发请求到Python服务
func ProxyCrawlerTrigger(c *gin.Context) {
	log.Println("收到爬虫触发请求")

	// 解析请求数据
	var triggerReq struct {
		Platform   string `json:"platform"`
		CreatorURL string `json:"creator_url"`
		Limit      int    `json:"limit"`
	}

	if err := c.ShouldBindJSON(&triggerReq); err != nil {
		log.Printf("解析请求数据失败: %v", err)
		c.JSON(http.StatusBadRequest, gin.H{"error": "请求数据格式错误"})
		return
	}

	// 设置默认值
	if triggerReq.Platform == "" {
		triggerReq.Platform = "weibo"
	}
	if triggerReq.CreatorURL == "" {
		// 根据平台设置合适的默认值
		switch triggerReq.Platform {
		case "weibo":
			triggerReq.CreatorURL = "周杰伦中文网JayCn" // 使用知名用户名作为默认值
		case "bilibili":
			triggerReq.CreatorURL = "热门视频"
		case "douyin":
			triggerReq.CreatorURL = "热门短视频"
		case "xiaohongshu":
			triggerReq.CreatorURL = "生活分享"
		default:
			triggerReq.CreatorURL = "热门内容"
		}
	}
	if triggerReq.Limit <= 0 {
		triggerReq.Limit = 10
	}

	// 检查是否已有相同的任务在运行
	db := config.GetDB()
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	existingTaskFilter := map[string]interface{}{
		"platform":    triggerReq.Platform,
		"creator_url": triggerReq.CreatorURL,
		"status":      map[string]interface{}{"$in": []string{"pending", "running"}},
	}

	existingTaskCount, err := db.Collection("crawl_tasks").CountDocuments(ctx, existingTaskFilter)
	if err != nil {
		log.Printf("检查重复任务失败: %v", err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "检查重复任务失败"})
		return
	}

	if existingTaskCount > 0 {
		log.Printf("检测到重复任务: platform=%s, creator_url=%s", triggerReq.Platform, triggerReq.CreatorURL)
		c.JSON(http.StatusConflict, gin.H{
			"error":       "任务已存在",
			"message":     "相同的爬取任务正在进行中，请稍后再试",
			"platform":    triggerReq.Platform,
			"creator_url": triggerReq.CreatorURL,
		})
		return
	}

	// 创建爬取任务记录
	task := models.CrawlerTask{
		ID:         primitive.NewObjectID(),
		Platform:   triggerReq.Platform,
		CreatorURL: triggerReq.CreatorURL,
		Limit:      triggerReq.Limit,
		Status:     "pending",
		CreatedAt:  time.Now(),
		UpdatedAt:  &[]time.Time{time.Now()}[0],
	}

	// 保存任务到数据库
	_, err = db.Collection("crawl_tasks").InsertOne(ctx, task)
	if err != nil {
		log.Printf("创建爬取任务失败: %v", err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "创建爬取任务失败"})
		return
	}

	log.Printf("创建爬取任务成功: %s", task.ID.Hex())

	// 更新任务状态为运行中
	updateTaskStatus(task.ID, "running", "")

	// 构造Python服务请求
	platformRequest := map[string]interface{}{
		"creator_url": triggerReq.CreatorURL,
		"platform":    triggerReq.Platform,
		"limit":       triggerReq.Limit,
	}

	requestBody, err := json.Marshal(platformRequest)
	if err != nil {
		log.Printf("构造请求数据失败: %v", err)
		updateTaskStatus(task.ID, "failed", "构造请求数据失败")
		c.JSON(http.StatusInternalServerError, gin.H{"error": "构造请求失败"})
		return
	}

	// 发送请求到Python服务
	req, err := http.NewRequest("POST", PYTHON_CRAWLER_URL+"/crawl/platform", bytes.NewBuffer(requestBody))
	if err != nil {
		log.Printf("创建HTTP请求失败: %v", err)
		updateTaskStatus(task.ID, "failed", "创建HTTP请求失败")
		c.JSON(http.StatusInternalServerError, gin.H{"error": "创建请求失败"})
		return
	}

	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("User-Agent", "NewsHub-Backend/1.0")

	client := &http.Client{Timeout: 30 * time.Second}
	log.Printf("转发请求到Python服务: %s", req.URL.String())

	resp, err := client.Do(req)
	if err != nil {
		log.Printf("Python爬虫服务请求失败: %v", err)
		updateTaskStatus(task.ID, "failed", "Python爬虫服务不可用: "+err.Error())
		c.JSON(http.StatusServiceUnavailable, gin.H{
			"error":   "Python爬虫服务不可用",
			"details": err.Error(),
		})
		return
	}
	defer resp.Body.Close()

	respBody, err := io.ReadAll(resp.Body)
	if err != nil {
		log.Printf("读取Python服务响应失败: %v", err)
		updateTaskStatus(task.ID, "failed", "读取Python服务响应失败")
		c.JSON(http.StatusInternalServerError, gin.H{"error": "读取响应失败"})
		return
	}

	log.Printf("Python服务响应状态: %d", resp.StatusCode)

	// 处理响应
	if resp.StatusCode == http.StatusOK {
		// 解析爬取结果
		var crawlResult map[string]interface{}
		if err := json.Unmarshal(respBody, &crawlResult); err == nil {
			// 保存爬取内容 - 支持新的响应格式
			var posts []interface{}

			// 检查不同的响应格式
			if postsData, ok := crawlResult["posts"].([]interface{}); ok {
				posts = postsData
			} else if postsData, ok := crawlResult["data"].([]interface{}); ok {
				posts = postsData
			} else if total, ok := crawlResult["total"].(float64); ok && total > 0 {
				// 如果有total字段且大于0，尝试直接使用结果
				posts = []interface{}{crawlResult}
			}

			if len(posts) > 0 {
				if err := SaveCrawlerContent(task.ID, posts); err != nil {
					log.Printf("保存爬取内容失败: %v", err)
					updateTaskStatus(task.ID, "failed", "保存爬取内容失败")
				} else {
					log.Printf("成功保存 %d 条爬取内容", len(posts))
					updateTaskStatus(task.ID, "completed", "")
				}
			} else {
				log.Printf("未找到有效的爬取内容，但任务完成")
				updateTaskStatus(task.ID, "completed", "")
			}
		} else {
			log.Printf("解析爬取结果失败: %v", err)
			updateTaskStatus(task.ID, "failed", "解析爬取结果失败: "+err.Error())
		}
	} else {
		errorMsg := fmt.Sprintf("Python服务返回错误状态: %d", resp.StatusCode)
		log.Printf(errorMsg)
		updateTaskStatus(task.ID, "failed", errorMsg)
	}

	// 返回任务信息和爬取结果
	result := map[string]interface{}{
		"task_id": task.ID.Hex(),
		"status":  task.Status,
		"message": "爬取任务已创建并执行",
	}

	// 如果有爬取结果，也一并返回
	if resp.StatusCode == http.StatusOK {
		var crawlResult map[string]interface{}
		if err := json.Unmarshal(respBody, &crawlResult); err == nil {
			result["crawl_result"] = crawlResult
		}
	}

	c.JSON(http.StatusOK, result)
}

// ProxyCrawlerStatus 代理爬虫状态请求到Python服务
func ProxyCrawlerStatus(c *gin.Context) {
	log.Println("检查Python爬虫服务状态")

	// 检查Python服务健康状态
	client := &http.Client{Timeout: 5 * time.Second}
	resp, err := client.Get(PYTHON_CRAWLER_URL + "/health")
	if err != nil {
		log.Printf("Python服务健康检查失败: %v", err)
		c.JSON(http.StatusServiceUnavailable, gin.H{
			"status":      "unavailable",
			"message":     "Python爬虫服务不可用",
			"error":       err.Error(),
			"service_url": PYTHON_CRAWLER_URL,
		})
		return
	}
	defer resp.Body.Close()

	if resp.StatusCode == http.StatusOK {
		log.Println("Python爬虫服务运行正常")
		c.JSON(http.StatusOK, gin.H{
			"status":      "active",
			"message":     "Python爬虫服务正在运行",
			"service_url": PYTHON_CRAWLER_URL,
			"api_docs":    PYTHON_CRAWLER_URL + "/docs",
			"last_check":  time.Now().Format(time.RFC3339),
		})
	} else {
		log.Printf("Python服务返回错误状态: %d", resp.StatusCode)
		c.JSON(http.StatusServiceUnavailable, gin.H{
			"status":  "error",
			"message": fmt.Sprintf("Python爬虫服务返回错误状态: %d", resp.StatusCode),
		})
	}
}

// GetCrawlerPlatforms 获取支持的爬虫平台列表
func GetCrawlerPlatforms(c *gin.Context) {
	log.Println("获取支持的爬虫平台列表")

	client := &http.Client{Timeout: 5 * time.Second}
	resp, err := client.Get(PYTHON_CRAWLER_URL + "/platforms")
	if err != nil {
		log.Printf("获取平台列表失败: %v", err)
		c.JSON(http.StatusServiceUnavailable, gin.H{
			"error":   "Python爬虫服务不可用",
			"details": err.Error(),
		})
		return
	}
	defer resp.Body.Close()

	// 读取响应
	respBody, err := io.ReadAll(resp.Body)
	if err != nil {
		log.Printf("读取平台列表响应失败: %v", err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "读取响应失败"})
		return
	}

	// 转发响应
	c.Header("Content-Type", "application/json")
	c.Status(resp.StatusCode)
	c.Writer.Write(respBody)
}

// updateTaskStatus 更新任务状态的辅助函数
func updateTaskStatus(taskID primitive.ObjectID, status string, errorMsg string) {
	db := config.GetDB()
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	update := map[string]interface{}{
		"status":     status,
		"updated_at": &[]time.Time{time.Now()}[0],
	}

	if errorMsg != "" {
		update["error"] = errorMsg
	}

	// 根据状态设置时间字段
	now := time.Now()
	switch status {
	case "running":
		update["started_at"] = now
	case "completed", "failed":
		update["completed_at"] = now
	}

	_, err := db.Collection("crawl_tasks").UpdateOne(
		ctx,
		map[string]interface{}{"_id": taskID},
		map[string]interface{}{"$set": update},
	)

	if err != nil {
		log.Printf("更新任务状态失败: %v", err)
	} else {
		log.Printf("任务状态更新成功: %s -> %s", taskID.Hex(), status)
	}
}
