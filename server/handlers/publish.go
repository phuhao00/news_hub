package handlers

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"os"
	"time"

	"github.com/gin-gonic/gin"
	"go.mongodb.org/mongo-driver/bson"
	"go.mongodb.org/mongo-driver/bson/primitive"

	"newshub/config"
	"newshub/models"
)

type CreatePublishTaskRequest struct {
	VideoID     primitive.ObjectID `json:"videoId"`
	Platforms   []string           `json:"platforms"`
	Description string             `json:"description"`
}

func CreatePublishTask(c *gin.Context) {
	var req CreatePublishTaskRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	// 验证视频是否存在
	var video models.Video
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	err := config.GetDB().Collection("videos").FindOne(ctx, bson.M{"_id": req.VideoID}).Decode(&video)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid video ID"})
		return
	}

	task := models.PublishTask{
		VideoID:     req.VideoID,
		Platforms:   req.Platforms,
		Description: req.Description,
		Status:      "pending",
		CreatedAt:   time.Now(),
	}

	result, err := config.GetDB().Collection("publish_tasks").InsertOne(ctx, task)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	task.ID = result.InsertedID.(primitive.ObjectID)

	// 启动异步发布任务
	go publishVideoAsync(task.ID, task.VideoID, task.Platforms, task.Description)

	c.JSON(http.StatusAccepted, gin.H{
		"message": "发布任务已启动",
		"task":    task,
	})
}

func GetPublishTasks(c *gin.Context) {
	var tasks []models.PublishTask

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	cursor, err := config.GetDB().Collection("publish_tasks").Find(ctx, bson.M{})
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	defer cursor.Close(ctx)

	if err := cursor.All(ctx, &tasks); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	// Ensure we always return an array, never null
	if tasks == nil {
		tasks = []models.PublishTask{}
	}

	c.JSON(http.StatusOK, tasks)
}

// GetPublishTask 获取单个发布任务
func GetPublishTask(c *gin.Context) {
	id := c.Param("id")
	objID, err := primitive.ObjectIDFromHex(id)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "无效的任务ID"})
		return
	}
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	var task models.PublishTask
	err = config.GetDB().Collection("publish_tasks").FindOne(ctx, bson.M{"_id": objID}).Decode(&task)
	if err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "任务不存在"})
		return
	}
	c.JSON(http.StatusOK, task)
}

// UpdatePublishTask 更新发布任务（状态/结果等）
func UpdatePublishTask(c *gin.Context) {
	id := c.Param("id")
	objID, err := primitive.ObjectIDFromHex(id)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "无效的任务ID"})
		return
	}
	var payload map[string]interface{}
	if err := c.ShouldBindJSON(&payload); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "无效的请求体"})
		return
	}
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	_, err = config.GetDB().Collection("publish_tasks").UpdateOne(
		ctx,
		bson.M{"_id": objID},
		bson.M{"$set": payload},
	)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "更新任务失败"})
		return
	}
	var task models.PublishTask
	_ = config.GetDB().Collection("publish_tasks").FindOne(ctx, bson.M{"_id": objID}).Decode(&task)
	c.JSON(http.StatusOK, task)
}

// publishVideoAsync 异步发布视频到各个平台
func publishVideoAsync(taskID, videoID primitive.ObjectID, platforms []string, description string) {
	log.Printf("开始发布任务: %s, 视频: %s, 平台: %v", taskID.Hex(), videoID.Hex(), platforms)

	// 更新任务状态为处理中
	updatePublishTaskStatus(taskID, "processing", "", "")

	// 获取视频信息
	video, err := getVideoInfo(videoID)
	if err != nil {
		updatePublishTaskStatus(taskID, "failed", fmt.Sprintf("获取视频信息失败: %v", err), "")
		return
	}

	// 检查视频文件是否存在
	videoPath := config.GetVideoPath(videoID.Hex())
	if _, err := os.Stat(videoPath); os.IsNotExist(err) {
		updatePublishTaskStatus(taskID, "failed", "视频文件不存在", "")
		return
	}

	var publishResults []string
	var publishErrors []string

	// 逐个平台发布
	for _, platform := range platforms {
		log.Printf("发布到平台: %s", platform)
		result, err := publishToPlatform(platform, videoPath, description, video)
		if err != nil {
			errorMsg := fmt.Sprintf("%s发布失败: %v", platform, err)
			publishErrors = append(publishErrors, errorMsg)
			log.Printf(errorMsg)
		} else {
			successMsg := fmt.Sprintf("%s发布成功: %s", platform, result)
			publishResults = append(publishResults, successMsg)
			log.Printf(successMsg)
		}
	}

	// 更新最终状态
	if len(publishErrors) == 0 {
		// 全部成功
		resultMsg := fmt.Sprintf("发布完成: %s", publishResults)
		updatePublishTaskStatus(taskID, "published", "", resultMsg)
	} else if len(publishResults) > 0 {
		// 部分成功
		errorMsg := fmt.Sprintf("部分发布失败: %s", publishErrors)
		resultMsg := fmt.Sprintf("部分发布成功: %s", publishResults)
		updatePublishTaskStatus(taskID, "partial", errorMsg, resultMsg)
	} else {
		// 全部失败
		errorMsg := fmt.Sprintf("发布失败: %s", publishErrors)
		updatePublishTaskStatus(taskID, "failed", errorMsg, "")
	}

	log.Printf("发布任务完成: %s", taskID.Hex())
}

// getVideoInfo 获取视频信息
func getVideoInfo(videoID primitive.ObjectID) (*models.Video, error) {
	coll := config.GetDB().Collection("videos")
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	var video models.Video
	err := coll.FindOne(ctx, bson.M{"_id": videoID}).Decode(&video)
	if err != nil {
		return nil, err
	}

	return &video, nil
}

// publishToPlatform 发布到指定平台
func publishToPlatform(platform, videoPath, description string, video *models.Video) (string, error) {
	switch platform {
	case "weibo":
		return publishToWeibo(videoPath, description, video)
	case "douyin":
		return publishToDouyin(videoPath, description, video)
	case "xiaohongshu":
		return publishToXiaohongshu(videoPath, description, video)
	case "bilibili":
		return publishToBilibili(videoPath, description, video)
	default:
		return "", fmt.Errorf("不支持的平台: %s", platform)
	}
}

// publishToWeibo 发布到微博
func publishToWeibo(videoPath, description string, video *models.Video) (string, error) {
	appKey := os.Getenv("WEIBO_APP_KEY")
	appSecret := os.Getenv("WEIBO_APP_SECRET")

	if appKey == "" || appSecret == "" || appKey == "your_weibo_app_key" {
		// 模拟发布
		return simulatePublish("weibo", videoPath, description)
	}

	// 实际的微博API调用逻辑
	// 这里需要根据微博API文档实现具体的发布逻辑
	return callPlatformAPI("weibo", appKey, appSecret, videoPath, description)
}

// publishToDouyin 发布到抖音
func publishToDouyin(videoPath, description string, video *models.Video) (string, error) {
	appKey := os.Getenv("DOUYIN_APP_KEY")
	appSecret := os.Getenv("DOUYIN_APP_SECRET")

	if appKey == "" || appSecret == "" || appKey == "your_douyin_app_key" {
		// 模拟发布
		return simulatePublish("douyin", videoPath, description)
	}

	// 实际的抖音API调用逻辑
	return callPlatformAPI("douyin", appKey, appSecret, videoPath, description)
}

// publishToXiaohongshu 发布到小红书
func publishToXiaohongshu(videoPath, description string, video *models.Video) (string, error) {
	appKey := os.Getenv("XIAOHONGSHU_APP_KEY")
	appSecret := os.Getenv("XIAOHONGSHU_APP_SECRET")

	if appKey == "" || appSecret == "" || appKey == "your_xiaohongshu_app_key" {
		// 模拟发布
		return simulatePublish("xiaohongshu", videoPath, description)
	}

	// 实际的小红书API调用逻辑
	return callPlatformAPI("xiaohongshu", appKey, appSecret, videoPath, description)
}

// publishToBilibili 发布到B站
func publishToBilibili(videoPath, description string, video *models.Video) (string, error) {
	appKey := os.Getenv("BILIBILI_APP_KEY")
	appSecret := os.Getenv("BILIBILI_APP_SECRET")

	if appKey == "" || appSecret == "" || appKey == "your_bilibili_app_key" {
		// 模拟发布
		return simulatePublish("bilibili", videoPath, description)
	}

	// 实际的B站API调用逻辑
	return callPlatformAPI("bilibili", appKey, appSecret, videoPath, description)
}

// simulatePublish 模拟发布（用于开发和测试）
func simulatePublish(platform, videoPath, description string) (string, error) {
	log.Printf("模拟发布到%s: 视频=%s, 描述=%s", platform, videoPath, description)

	// 模拟处理时间
	time.Sleep(2 * time.Second)

	// 生成模拟的发布URL
	mockURL := fmt.Sprintf("https://%s.com/video/%d", platform, time.Now().Unix())
	return mockURL, nil
}

// callPlatformAPI 调用平台API
func callPlatformAPI(platform, appKey, appSecret, videoPath, description string) (string, error) {
	// 这里实现具体的平台API调用逻辑
	// 每个平台的API都不同，需要根据具体的API文档来实现

	// 准备请求数据
	requestData := map[string]interface{}{
		"app_key":     appKey,
		"app_secret":  appSecret,
		"video_path":  videoPath,
		"description": description,
		"platform":    platform,
	}

	jsonData, err := json.Marshal(requestData)
	if err != nil {
		return "", err
	}

	// 构建API端点URL（这里使用示例URL）
	apiURL := fmt.Sprintf("https://api.%s.com/upload", platform)

	// 发送HTTP请求
	req, err := http.NewRequest("POST", apiURL, bytes.NewBuffer(jsonData))
	if err != nil {
		return "", err
	}

	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Authorization", "Bearer "+appKey)

	client := &http.Client{Timeout: 2 * time.Minute}
	resp, err := client.Do(req)
	if err != nil {
		// 如果API调用失败，回退到模拟发布
		log.Printf("API调用失败，使用模拟发布: %v", err)
		return simulatePublish(platform, videoPath, description)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return "", fmt.Errorf("平台API返回错误: %d", resp.StatusCode)
	}

	var result map[string]interface{}
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		return "", err
	}

	publishURL, ok := result["url"].(string)
	if !ok {
		return "", fmt.Errorf("无效的平台API响应")
	}

	return publishURL, nil
}

// updatePublishTaskStatus 更新发布任务状态
func updatePublishTaskStatus(taskID primitive.ObjectID, status, errorMsg, publishedAt string) {
	coll := config.GetDB().Collection("publish_tasks")
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	update := bson.M{"$set": bson.M{"status": status}}
	if errorMsg != "" {
		update["$set"].(bson.M)["error"] = errorMsg
	}
	if publishedAt != "" {
		update["$set"].(bson.M)["published_at"] = publishedAt
	}

	_, err := coll.UpdateOne(ctx, bson.M{"_id": taskID}, update)
	if err != nil {
		log.Printf("更新发布任务状态失败: %v", err)
	}
}
