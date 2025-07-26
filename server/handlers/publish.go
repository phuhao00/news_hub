package handlers

import (
	"context"
	"net/http"
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

	// TODO: 启动异步发布任务
	// 临时模拟发布成功
	_, err = config.GetDB().Collection("publish_tasks").UpdateOne(
		ctx,
		bson.M{"_id": task.ID},
		bson.M{"$set": bson.M{
			"status":       "published",
			"published_at": time.Now(),
		}},
	)

	c.JSON(http.StatusAccepted, task)
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
