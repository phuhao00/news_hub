package handlers

import (
	"context"
	"fmt"
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

	// 先返回视频元信息（数据库中）
	coll := config.GetDB().Collection("videos")
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	var video models.Video
	objID, err := primitive.ObjectIDFromHex(videoID)
	if err == nil {
		_ = coll.FindOne(ctx, bson.M{"_id": objID}).Decode(&video)
	}

	// 同时检查视频文件是否存在并允许下载
	videoPath := config.GetVideoPath(videoID)
	if st, err := os.Stat(videoPath); err == nil {
		// 支持通过查询参数 ?download=1 下载
		if c.Query("download") == "1" {
			file, err := os.Open(videoPath)
			if err != nil {
				c.JSON(http.StatusInternalServerError, gin.H{"error": "打开视频文件失败"})
				return
			}
			defer file.Close()
			c.Header("Content-Type", "video/mp4")
			c.Header("Content-Length", fmt.Sprintf("%d", st.Size()))
			c.Header("Content-Disposition", "attachment; filename=\""+filepath.Base(videoPath)+"\"")
			if _, err := io.Copy(c.Writer, file); err != nil {
				c.JSON(http.StatusInternalServerError, gin.H{"error": "发送视频文件失败"})
			}
			return
		}
		// 文件存在时返回基本元数据
		c.JSON(http.StatusOK, gin.H{
			"id":         videoID,
			"status":     "completed",
			"size":       st.Size(),
			"path":       videoPath,
			"url":        "/api/videos/" + videoID + "?download=1",
			"created_at": video.CreatedAt,
		})
		return
	}

	// 文件不存在，返回数据库记录或404
	if video.ID.IsZero() {
		c.JSON(http.StatusNotFound, gin.H{"error": "视频不存在"})
		return
	}
	c.JSON(http.StatusOK, video)
}

// UpdateVideo 更新视频状态/元数据
func UpdateVideo(c *gin.Context) {
	videoID := c.Param("id")
	objID, err := primitive.ObjectIDFromHex(videoID)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "无效的视频ID"})
		return
	}
	var payload map[string]interface{}
	if err := c.ShouldBindJSON(&payload); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "无效的请求体"})
		return
	}
	coll := config.GetDB().Collection("videos")
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	_, err = coll.UpdateOne(ctx, bson.M{"_id": objID}, bson.M{"$set": payload})
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "更新视频失败"})
		return
	}
	var video models.Video
	_ = coll.FindOne(ctx, bson.M{"_id": objID}).Decode(&video)
	c.JSON(http.StatusOK, video)
}
