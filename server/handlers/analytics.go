package handlers

import (
	"context"
	"net/http"
	"time"

	"github.com/gin-gonic/gin"
	"go.mongodb.org/mongo-driver/bson"

	"newshub/config"
)

type overviewResponse struct {
	TotalCreators int `json:"totalCreators"`
	TotalPosts int `json:"totalContent"`
	Videos int `json:"videosGenerated"`
	PendingJobs int `json:"pendingJobs"`
	CrawlIdle int `json:"creatorsIdle"`
	CrawlRunning int `json:"creatorsCrawling"`
}

// AnalyticsOverview basic aggregate counts for dashboard
func AnalyticsOverview(c *gin.Context) {
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	db := config.GetDB()
	countCreatorsIdle, _ := db.Collection("creators").CountDocuments(ctx, bson.M{"crawl_status": "idle"})
	countCreatorsRunning, _ := db.Collection("creators").CountDocuments(ctx, bson.M{"crawl_status": "crawling"})
	countPosts, _ := db.Collection("posts").CountDocuments(ctx, bson.M{})
	countVideos, _ := db.Collection("videos").CountDocuments(ctx, bson.M{})
	countJobsPending, _ := db.Collection("jobs").CountDocuments(ctx, bson.M{"status": "pending"})
	resp := overviewResponse{TotalCreators: int(countCreatorsIdle + countCreatorsRunning), TotalPosts: int(countPosts), Videos: int(countVideos), PendingJobs: int(countJobsPending), CrawlIdle: int(countCreatorsIdle), CrawlRunning: int(countCreatorsRunning)}
	c.JSON(http.StatusOK, resp)
}
