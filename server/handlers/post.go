package handlers

import (
	"context"
	"net/http"
	"strconv"
	"time"

	"github.com/gin-gonic/gin"
	"go.mongodb.org/mongo-driver/bson"
	"go.mongodb.org/mongo-driver/bson/primitive"
	"go.mongodb.org/mongo-driver/mongo/options"

	"newshub/config"
	"newshub/models"
)

// GetPosts 获取帖子列表（从crawl_tasks和crawler_contents集合获取并转换）
func GetPosts(c *gin.Context) {
	var posts []models.Post

	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()

	// 获取查询参数
	creatorID := c.Query("creator_id")
	platform := c.Query("platform")
	limitStr := c.Query("limit")

	// 设置默认限制
	limit := 50
	if limitStr != "" {
		if parsedLimit, err := strconv.Atoi(limitStr); err == nil && parsedLimit > 0 {
			limit = parsedLimit
		}
	}

	// 首先查询crawl_tasks获取已完成的任务
	taskFilter := bson.M{
		"status": "completed",
	}
	if platform != "" {
		taskFilter["platform"] = platform
	}
	if creatorID != "" {
		taskFilter["creator_url"] = creatorID
	}

	// 查询已完成的爬取任务
	taskOpts := options.Find().SetSort(bson.D{{Key: "completed_at", Value: -1}})
	taskCursor, err := config.GetDB().Collection("crawl_tasks").Find(ctx, taskFilter, taskOpts)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	defer taskCursor.Close(ctx)

	var crawlTasks []models.CrawlerTask
	if err := taskCursor.All(ctx, &crawlTasks); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	// 如果没有已完成的任务，返回空数组
	if len(crawlTasks) == 0 {
		c.JSON(http.StatusOK, []models.Post{})
		return
	}

	// 收集所有任务ID
	var taskIDs []primitive.ObjectID
	for _, task := range crawlTasks {
		taskIDs = append(taskIDs, task.ID)
	}

	// 根据任务ID查询crawler_contents
	contentFilter := bson.M{
		"task_id": bson.M{"$in": taskIDs},
	}

	// 查询crawler_contents，按创建时间倒序
	contentOpts := options.Find().SetSort(bson.D{{Key: "created_at", Value: -1}}).SetLimit(int64(limit))
	contentCursor, err := config.GetDB().Collection("crawler_contents").Find(ctx, contentFilter, contentOpts)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	defer contentCursor.Close(ctx)

	// 获取crawler_contents数据
	var crawlerContents []models.CrawlerContent
	if err := contentCursor.All(ctx, &crawlerContents); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	// 转换crawler_contents为posts格式
	for _, content := range crawlerContents {
		// 创建基础的Post结构
		post := models.Post{
			ID:          content.ID,
			CreatorID:   content.TaskID, // 使用TaskID作为CreatorID的临时方案
			CreatorName: content.Author,
			Platform:    content.Platform,
			PostID:      content.OriginID,
			Title:       content.Title,
			Content:     content.Content,
			MediaURLs:   []string{},
			PublishedAt: content.PublishedAt,
			CreatedAt:   content.CreatedAt,
		}

		// 处理媒体URLs：添加图片
		if len(content.Images) > 0 {
			post.MediaURLs = append(post.MediaURLs, content.Images...)
			// 设置第一张图片作为imageUrl
			post.ImageUrl = content.Images[0]
		}

		// 处理视频URL
		if content.VideoURL != "" {
			post.MediaURLs = append(post.MediaURLs, content.VideoURL)
			post.VideoUrl = content.VideoURL
		}

		posts = append(posts, post)
	}

	// Ensure we always return an array, never null
	if posts == nil {
		posts = []models.Post{}
	}

	c.JSON(http.StatusOK, posts)
}

// GetPost 获取单个帖子详情
func GetPost(c *gin.Context) {
	id, err := primitive.ObjectIDFromHex(c.Param("id"))
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid ID"})
		return
	}

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	var post models.Post
	err = config.GetDB().Collection("posts").FindOne(ctx, bson.M{"_id": id}).Decode(&post)
	if err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "Post not found"})
		return
	}

	c.JSON(http.StatusOK, post)
}

// DeletePost 删除帖子（从crawler_contents集合删除）
func DeletePost(c *gin.Context) {
	id, err := primitive.ObjectIDFromHex(c.Param("id"))
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid ID"})
		return
	}

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	// 删除crawler_contents集合中的内容，因为GetPosts是从这个集合读取的
	result, err := config.GetDB().Collection("crawler_contents").DeleteOne(ctx, bson.M{"_id": id})
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	if result.DeletedCount == 0 {
		c.JSON(http.StatusNotFound, gin.H{"error": "Post not found"})
		return
	}

	c.JSON(http.StatusOK, gin.H{"message": "Post deleted successfully"})
}
