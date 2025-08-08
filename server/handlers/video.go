package handlers

import (
	"context"
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

// GenerateVideo enqueues a video generation job instead of immediate generation
func GenerateVideo(c *gin.Context) {
	var req struct { PostIDs []string `json:"post_ids"`; Style string `json:"style"`; Duration int `json:"duration"` }
	if err := c.ShouldBindJSON(&req); err != nil { c.JSON(http.StatusBadRequest, gin.H{"error": "invalid payload"}); return }
	video := models.Video{ID: primitive.NewObjectID(), PostIDs: []primitive.ObjectID{}, Style: req.Style, Duration: req.Duration, Status: "processing", CreatedAt: time.Now()}
	for _, id := range req.PostIDs { if oid, err := primitive.ObjectIDFromHex(id); err == nil { video.PostIDs = append(video.PostIDs, oid) } }
	coll := config.GetDB().Collection("videos")
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second); defer cancel()
	if _, err := coll.InsertOne(ctx, video); err != nil { c.JSON(http.StatusInternalServerError, gin.H{"error": "save failed"}); return }
	// A real implementation would enqueue a job; simplified marking completed quickly
	go func(id primitive.ObjectID){
		time.Sleep(800 * time.Millisecond)
		ctx2, cancel2 := context.WithTimeout(context.Background(), 5*time.Second); defer cancel2()
		coll.UpdateOne(ctx2, bson.M{"_id": id}, bson.M{"$set": bson.M{"status": "completed", "url": "/api/videos/"+id.Hex()}})
	}(video.ID)
	c.JSON(http.StatusAccepted, video)
}

// GetVideos 获取视频列表
func GetVideos(c *gin.Context) {
	coll := config.GetDB().Collection("videos")
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second); defer cancel()
	cursor, err := coll.Find(ctx, bson.M{})
	if err != nil { c.JSON(http.StatusInternalServerError, gin.H{"error": "list failed"}); return }
	var videos []models.Video
	if err := cursor.All(ctx, &videos); err != nil { c.JSON(http.StatusInternalServerError, gin.H{"error": "decode failed"}); return }
	if videos == nil { videos = []models.Video{} }
	c.JSON(http.StatusOK, videos)
}

// GetVideo streaming stored video file (demo placeholder)
func GetVideo(c *gin.Context) {
	videoID := c.Param("id")
	videoPath := config.GetVideoPath(videoID)
	if _, err := os.Stat(videoPath); err != nil { c.JSON(http.StatusNotFound, gin.H{"error": "not found"}); return }
	file, err := os.Open(videoPath); if err != nil { c.JSON(http.StatusInternalServerError, gin.H{"error": "open failed"}); return }
	defer file.Close()
	fi, _ := file.Stat()
	c.Header("Content-Type", "video/mp4")
	c.Header("Content-Length", string(fi.Size()))
	c.Header("Content-Disposition", "inline; filename=\""+filepath.Base(videoPath)+"\"")
	http.ServeContent(c.Writer, c.Request, fi.Name(), fi.ModTime(), file)
}
