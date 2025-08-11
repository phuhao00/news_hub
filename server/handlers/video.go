package handlers

import (
	"context"
	"io"
	"net/http"
	"os"
	"path/filepath"
	"time"

	"github.com/gin-gonic/gin"
	"go.mongodb.org/mongo-driver/bson"
	"go.mongodb.org/mongo-driver/bson/primitive"

	"newshub/config"
	"newshub/models"
)

// GenerateVideo 生成视频
func GenerateVideo(c *gin.Context) {
	// 获取请求参数
	var video models.Video
	if err := c.ShouldBindJSON(&video); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "无效的请求参数"})
		return
	}

	// 设置视频ID和创建时间
	video.ID = primitive.NewObjectID()
	video.CreatedAt = time.Now()
	video.Status = "processing"

	// TODO: 实现实际的视频生成逻辑
	// 这里应该调用视频生成服务
	// 为了演示，我们模拟一个成功的视频生成
	video.Status = "completed"
	video.URL = "/api/videos/" + video.ID.Hex()

	// 保存到数据库
	coll := config.GetDB().Collection("videos")
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	_, err := coll.InsertOne(ctx, video)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "保存视频记录失败"})
		return
	}

	c.JSON(http.StatusOK, video)
}

// GetVideos 获取视频列表
func GetVideos(c *gin.Context) {
	coll := config.GetDB().Collection("videos")

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	// 查询所有视频
	cursor, err := coll.Find(ctx, bson.M{})
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "获取视频列表失败"})
		return
	}
	defer cursor.Close(ctx)

	// 解码结果
	var videos []models.Video
	if err := cursor.All(ctx, &videos); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "解析视频数据失败"})
		return
	}

	// Ensure we always return an array, never null
	if videos == nil {
		videos = []models.Video{}
	}

	c.JSON(http.StatusOK, videos)
}

// GetVideo 获取单个视频
func GetVideo(c *gin.Context) {
	videoID := c.Param("id")

	// 检查视频文件是否存在
	videoPath := config.GetVideoPath(videoID)
	if _, err := os.Stat(videoPath); os.IsNotExist(err) {
		c.JSON(http.StatusNotFound, gin.H{"error": "视频文件不存在"})
		return
	}

	// 获取文件信息
	fileInfo, err := os.Stat(videoPath)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "获取视频文件信息失败"})
		return
	}

	// 打开文件
	file, err := os.Open(videoPath)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "打开视频文件失败"})
		return
	}
	defer file.Close()

	// 设置响应头
	c.Header("Content-Type", "video/mp4")
	c.Header("Content-Length", string(fileInfo.Size()))
	c.Header("Content-Disposition", "inline; filename=\""+filepath.Base(videoPath)+"\"")

	// 发送文件内容
	if _, err := io.Copy(c.Writer, file); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "发送视频文件失败"})
		return
	}
}

// UpdateVideo 更新视频信息
func UpdateVideo(c *gin.Context) {
	videoID := c.Param("id")

	// 验证视频ID格式
	objID, err := primitive.ObjectIDFromHex(videoID)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "无效的视频ID"})
		return
	}

	// 获取更新数据
	var updateData bson.M
	if err := c.ShouldBindJSON(&updateData); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "无效的请求参数"})
		return
	}

	// 添加更新时间
	updateData["updated_at"] = time.Now()

	// 更新数据库
	coll := config.GetDB().Collection("videos")
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	filter := bson.M{"_id": objID}
	update := bson.M{"$set": updateData}

	result, err := coll.UpdateOne(ctx, filter, update)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "更新视频失败"})
		return
	}

	if result.MatchedCount == 0 {
		c.JSON(http.StatusNotFound, gin.H{"error": "视频不存在"})
		return
	}

	c.JSON(http.StatusOK, gin.H{"message": "视频更新成功"})
}
