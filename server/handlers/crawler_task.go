package handlers

import (
	"context"
	"log"
	"net/http"
	"time"

	"github.com/gin-gonic/gin"
	"go.mongodb.org/mongo-driver/bson"
	"go.mongodb.org/mongo-driver/bson/primitive"
	"go.mongodb.org/mongo-driver/mongo/options"

	"newshub/config"
	"newshub/models"
)

// CreateCrawlerTask 创建爬取任务
func CreateCrawlerTask(c *gin.Context) {
	var req struct {
		Platform   string `json:"platform" binding:"required"`
		CreatorURL string `json:"creator_url" binding:"required"`
		Limit      int    `json:"limit"`
	}

	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	if req.Limit <= 0 {
		req.Limit = 10
	}

	task := models.CrawlerTask{
		ID:         primitive.NewObjectID(),
		Platform:   req.Platform,
		CreatorURL: req.CreatorURL,
		Limit:      req.Limit,
		Status:     "pending",
		CreatedAt:  time.Now(),
		UpdatedAt:  time.Now(),
	}

	db := config.GetDB()
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	_, err := db.Collection("crawler_tasks").InsertOne(ctx, task)
	if err != nil {
		log.Printf("创建爬取任务失败: %v", err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "创建爬取任务失败"})
		return
	}

	log.Printf("创建爬取任务成功: %s", task.ID.Hex())
	c.JSON(http.StatusCreated, task)
}

// GetCrawlerTasks 获取爬取任务列表
func GetCrawlerTasks(c *gin.Context) {
	db := config.GetDB()
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()

	// 构建查询选项，按创建时间倒序排列
	opts := options.Find().SetSort(bson.D{{Key: "created_at", Value: -1}}).SetLimit(50)

	cursor, err := db.Collection("crawler_tasks").Find(ctx, bson.M{}, opts)
	if err != nil {
		log.Printf("获取爬取任务列表失败: %v", err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "获取爬取任务列表失败"})
		return
	}
	defer cursor.Close(ctx)

	var tasks []models.CrawlerTask
	if err := cursor.All(ctx, &tasks); err != nil {
		log.Printf("解析爬取任务列表失败: %v", err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "解析爬取任务列表失败"})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"tasks": tasks,
		"total": len(tasks),
	})
}

// GetCrawlerTask 获取单个爬取任务
func GetCrawlerTask(c *gin.Context) {
	taskID := c.Param("id")
	objectID, err := primitive.ObjectIDFromHex(taskID)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "无效的任务ID"})
		return
	}

	db := config.GetDB()
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	var task models.CrawlerTask
	err = db.Collection("crawler_tasks").FindOne(ctx, bson.M{"_id": objectID}).Decode(&task)
	if err != nil {
		log.Printf("获取爬取任务失败: %v", err)
		c.JSON(http.StatusNotFound, gin.H{"error": "任务不存在"})
		return
	}

	c.JSON(http.StatusOK, task)
}

// UpdateCrawlerTaskStatus 更新爬取任务状态
func UpdateCrawlerTaskStatus(c *gin.Context) {
	taskID := c.Param("id")
	objectID, err := primitive.ObjectIDFromHex(taskID)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "无效的任务ID"})
		return
	}

	var req struct {
		Status string `json:"status" binding:"required"`
		Error  string `json:"error,omitempty"`
	}

	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	db := config.GetDB()
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	update := bson.M{
		"status":     req.Status,
		"updated_at": time.Now(),
	}

	if req.Error != "" {
		update["error"] = req.Error
	}

	// 根据状态设置时间字段
	now := time.Now()
	switch req.Status {
	case "running":
		update["started_at"] = now
	case "completed", "failed":
		update["completed_at"] = now
	}

	_, err = db.Collection("crawler_tasks").UpdateOne(
		ctx,
		bson.M{"_id": objectID},
		bson.M{"$set": update},
	)

	if err != nil {
		log.Printf("更新任务状态失败: %v", err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "更新任务状态失败"})
		return
	}

	log.Printf("任务状态更新成功: %s -> %s", taskID, req.Status)
	c.JSON(http.StatusOK, gin.H{"message": "状态更新成功"})
}

// GetCrawlerContents 获取爬取内容列表
func GetCrawlerContents(c *gin.Context) {
	taskID := c.Query("task_id")

	db := config.GetDB()
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()

	filter := bson.M{}
	if taskID != "" {
		objectID, err := primitive.ObjectIDFromHex(taskID)
		if err != nil {
			c.JSON(http.StatusBadRequest, gin.H{"error": "无效的任务ID"})
			return
		}
		filter["task_id"] = objectID
	}

	// 按创建时间倒序排列
	opts := options.Find().SetSort(bson.D{{Key: "created_at", Value: -1}}).SetLimit(100)

	cursor, err := db.Collection("crawler_contents").Find(ctx, filter, opts)
	if err != nil {
		log.Printf("获取爬取内容列表失败: %v", err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "获取爬取内容列表失败"})
		return
	}
	defer cursor.Close(ctx)

	var contents []models.CrawlerContent
	if err := cursor.All(ctx, &contents); err != nil {
		log.Printf("解析爬取内容列表失败: %v", err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "解析爬取内容列表失败"})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"contents": contents,
		"total":    len(contents),
	})
}

// SaveCrawlerContent 保存爬取内容
func SaveCrawlerContent(taskID primitive.ObjectID, posts []interface{}) error {
	if len(posts) == 0 {
		return nil
	}

	db := config.GetDB()
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()

	var contents []interface{}
	for _, post := range posts {
		postMap, ok := post.(map[string]interface{})
		if !ok {
			continue
		}

		content := models.CrawlerContent{
			ID:        primitive.NewObjectID(),
			TaskID:    taskID,
			Title:     getStringValue(postMap, "title"),
			Content:   getStringValue(postMap, "content"),
			Author:    getStringValue(postMap, "author"),
			Platform:  getStringValue(postMap, "platform"),
			URL:       getStringValue(postMap, "url"),
			Tags:      getStringArrayValue(postMap, "tags"),
			Images:    getStringArrayValue(postMap, "images"),
			VideoURL:  getStringValue(postMap, "video_url"),
			CreatedAt: time.Now(),
		}

		// 处理发布时间
		if publishedAt := getStringValue(postMap, "published_at"); publishedAt != "" {
			if t, err := time.Parse(time.RFC3339, publishedAt); err == nil {
				content.PublishedAt = &t
			}
		}

		contents = append(contents, content)
	}

	if len(contents) > 0 {
		_, err := db.Collection("crawler_contents").InsertMany(ctx, contents)
		if err != nil {
			log.Printf("保存爬取内容失败: %v", err)
			return err
		}
		log.Printf("成功保存 %d 条爬取内容", len(contents))
	}

	return nil
}

// 辅助函数
func getStringValue(m map[string]interface{}, key string) string {
	if val, ok := m[key]; ok {
		if str, ok := val.(string); ok {
			return str
		}
	}
	return ""
}

func getStringArrayValue(m map[string]interface{}, key string) []string {
	if val, ok := m[key]; ok {
		if arr, ok := val.([]interface{}); ok {
			var result []string
			for _, item := range arr {
				if str, ok := item.(string); ok {
					result = append(result, str)
				}
			}
			return result
		}
	}
	return []string{}
}
