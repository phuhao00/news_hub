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
	if err := c.ShouldBindJSON(&req); err != nil { c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()}); return }
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second); defer cancel()
	var video models.Video
	if err := config.GetDB().Collection("videos").FindOne(ctx, bson.M{"_id": req.VideoID}).Decode(&video); err != nil { c.JSON(http.StatusBadRequest, gin.H{"error": "invalid video"}); return }
	task := models.PublishTask{ID: primitive.NewObjectID(), VideoID: req.VideoID, Platforms: req.Platforms, Description: req.Description, Status: "pending", CreatedAt: time.Now()}
	if _, err := config.GetDB().Collection("publish_tasks").InsertOne(ctx, task); err != nil { c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()}); return }
	// simulate async processing
	go func(id primitive.ObjectID){
		time.Sleep(500 * time.Millisecond)
		ctx2, cancel2 := context.WithTimeout(context.Background(), 5*time.Second); defer cancel2()
		config.GetDB().Collection("publish_tasks").UpdateOne(ctx2, bson.M{"_id": id}, bson.M{"$set": bson.M{"status": "published", "published_at": time.Now()}})
	}(task.ID)
	c.JSON(http.StatusAccepted, task)
}

func GetPublishTasks(c *gin.Context) {
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second); defer cancel()
	cursor, err := config.GetDB().Collection("publish_tasks").Find(ctx, bson.M{})
	if err != nil { c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()}); return }
	var tasks []models.PublishTask
	if err := cursor.All(ctx, &tasks); err != nil { c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()}); return }
	if tasks == nil { tasks = []models.PublishTask{} }
	c.JSON(http.StatusOK, tasks)
}
