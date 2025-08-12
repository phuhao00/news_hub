package handlers

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"log"
	"net/http"
	"strings"
	"time"

	"github.com/gin-gonic/gin"
	"go.mongodb.org/mongo-driver/bson"
	"go.mongodb.org/mongo-driver/bson/primitive"
	"go.mongodb.org/mongo-driver/mongo"
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

	// Ensure we always return an array, never null
	if tasks == nil {
		tasks = []models.CrawlerTask{}
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

// DeleteCrawlerTask 删除爬取任务
func DeleteCrawlerTask(c *gin.Context) {
	taskID := c.Param("id")
	objectID, err := primitive.ObjectIDFromHex(taskID)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "无效的任务ID"})
		return
	}

	db := config.GetDB()
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()

	// 删除相关的爬取内容
	_, err = db.Collection("crawler_contents").DeleteMany(ctx, bson.M{"task_id": objectID})
	if err != nil {
		log.Printf("删除爬取内容失败: %v", err)
		// 继续删除任务，即使内容删除失败
	}

	// 删除爬取任务
	result, err := db.Collection("crawler_tasks").DeleteOne(ctx, bson.M{"_id": objectID})
	if err != nil {
		log.Printf("删除爬取任务失败: %v", err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "删除爬取任务失败"})
		return
	}

	if result.DeletedCount == 0 {
		c.JSON(http.StatusNotFound, gin.H{"error": "任务不存在"})
		return
	}

	log.Printf("成功删除爬取任务: %s", taskID)
	c.JSON(http.StatusOK, gin.H{"message": "任务删除成功"})
}

// BatchDeleteCrawlerTasks 批量删除爬取任务
func BatchDeleteCrawlerTasks(c *gin.Context) {
	var req struct {
		TaskIDs []string `json:"task_ids"`
		Filter  struct {
			Platform   string `json:"platform"`
			CreatorURL string `json:"creator_url"`
			Status     string `json:"status"`
		} `json:"filter"`
	}

	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	db := config.GetDB()
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()

	var filter bson.M

	// 如果提供了具体的任务ID列表
	if len(req.TaskIDs) > 0 {
		objectIDs := make([]primitive.ObjectID, 0, len(req.TaskIDs))
		for _, idStr := range req.TaskIDs {
			if objectID, err := primitive.ObjectIDFromHex(idStr); err == nil {
				objectIDs = append(objectIDs, objectID)
			}
		}
		filter = bson.M{"_id": bson.M{"$in": objectIDs}}
	} else {
		// 使用过滤条件
		filter = bson.M{}
		if req.Filter.Platform != "" {
			filter["platform"] = req.Filter.Platform
		}
		if req.Filter.CreatorURL != "" {
			filter["creator_url"] = req.Filter.CreatorURL
		}
		if req.Filter.Status != "" {
			filter["status"] = req.Filter.Status
		}
	}

	// 获取要删除的任务ID列表
	cursor, err := db.Collection("crawler_tasks").Find(ctx, filter)
	if err != nil {
		log.Printf("查询要删除的任务失败: %v", err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "查询任务失败"})
		return
	}
	defer cursor.Close(ctx)

	var taskIDs []primitive.ObjectID
	for cursor.Next(ctx) {
		var task models.CrawlerTask
		if err := cursor.Decode(&task); err == nil {
			taskIDs = append(taskIDs, task.ID)
		}
	}

	if len(taskIDs) == 0 {
		c.JSON(http.StatusOK, gin.H{"message": "没有找到匹配的任务", "deleted_count": 0})
		return
	}

	// 删除相关的爬取内容
	contentResult, err := db.Collection("crawler_contents").DeleteMany(ctx, bson.M{"task_id": bson.M{"$in": taskIDs}})
	if err != nil {
		log.Printf("批量删除爬取内容失败: %v", err)
	}

	// 删除爬取任务
	taskResult, err := db.Collection("crawler_tasks").DeleteMany(ctx, filter)
	if err != nil {
		log.Printf("批量删除爬取任务失败: %v", err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "批量删除任务失败"})
		return
	}

	log.Printf("批量删除完成: 删除了 %d 个任务和 %d 条内容", taskResult.DeletedCount, contentResult.DeletedCount)
	c.JSON(http.StatusOK, gin.H{
		"message":              "批量删除成功",
		"deleted_tasks_count":   taskResult.DeletedCount,
		"deleted_content_count": contentResult.DeletedCount,
	})
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

	// Ensure we always return an array, never null
	if contents == nil {
		contents = []models.CrawlerContent{}
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
	duplicateCount := 0

	for _, post := range posts {
		postMap, ok := post.(map[string]interface{})
		if !ok {
			continue
		}

		// 生成内容哈希
		contentText := getStringValue(postMap, "content")
		title := getStringValue(postMap, "title")
		combinedContent := title + "|" + contentText
		contentHash := generateContentHash(combinedContent)

		// 检查内容是否已存在（基于哈希）
		platform := getStringValue(postMap, "platform")
		author := getStringValue(postMap, "author")
		url := getStringValue(postMap, "url")

		isDuplicate, err := checkContentDuplicate(ctx, db, contentHash, platform, author, url)
		if err != nil {
			log.Printf("检查内容重复失败: %v", err)
			continue
		}

		if isDuplicate {
			duplicateCount++
			log.Printf("跳过重复内容: hash=%s, title=%s", contentHash[:8], title)
			continue
		}

		// 处理origin_id，如果为空则生成唯一值
		originID := getStringValue(postMap, "origin_id")
		if originID == "" {
			// 使用content_hash前8位 + 时间戳生成唯一origin_id
			originID = fmt.Sprintf("%s_%d", contentHash[:8], time.Now().UnixNano())
		}

		content := models.CrawlerContent{
			ID:          primitive.NewObjectID(),
			TaskID:      taskID,
			Title:       title,
			Content:     contentText,
			ContentHash: contentHash,
			Author:      author,
			Platform:    platform,
			URL:         url,
			OriginID:    originID,
			Tags:        getStringArrayValue(postMap, "tags"),
			Images:      getStringArrayValue(postMap, "images"),
			VideoURL:    getStringValue(postMap, "video_url"),
			CreatedAt:   time.Now(),
		}

		// 处理发布时间
		if publishedAt := getStringValue(postMap, "published_at"); publishedAt != "" {
			if t, err := time.Parse(time.RFC3339, publishedAt); err == nil {
				content.PublishedAt = &t
			}
		}

		contents = append(contents, content)
	}

	var savedCount int
	if len(contents) > 0 {
		_, err := db.Collection("crawler_contents").InsertMany(ctx, contents)
		if err != nil {
			log.Printf("保存爬取内容失败: %v", err)
			return err
		}
		savedCount = len(contents)
	}

	log.Printf("内容处理完成: 总数=%d, 保存=%d, 去重=%d", len(posts), savedCount, duplicateCount)
	return nil
}

// generateContentHash 生成内容哈希
func generateContentHash(content string) string {
	// 标准化内容：去除多余空格、换行等
	normalized := strings.TrimSpace(strings.ReplaceAll(content, "\n", " "))
	normalized = strings.ReplaceAll(normalized, "\r", "")

	hash := sha256.Sum256([]byte(normalized))
	return hex.EncodeToString(hash[:])
}

// checkContentDuplicate 检查内容是否重复
func checkContentDuplicate(ctx context.Context, db *mongo.Database, contentHash, platform, author, url string) (bool, error) {
	// 优先检查内容哈希
	filter := bson.M{"content_hash": contentHash}

	count, err := db.Collection("crawler_contents").CountDocuments(ctx, filter)
	if err != nil {
		return false, err
	}

	if count > 0 {
		return true, nil
	}

	// 如果有URL，也检查URL是否重复
	if url != "" {
		urlFilter := bson.M{
			"url":      url,
			"platform": platform,
		}
		urlCount, err := db.Collection("crawler_contents").CountDocuments(ctx, urlFilter)
		if err != nil {
			return false, err
		}
		if urlCount > 0 {
			return true, nil
		}
	}

	return false, nil
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
