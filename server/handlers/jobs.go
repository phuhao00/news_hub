package handlers

import (
	"context"
	"net/http"
	"time"

	"github.com/gin-gonic/gin"
	"go.mongodb.org/mongo-driver/bson"

	"newshub/config"
)

// ListJobs returns recent jobs
func ListJobs(c *gin.Context) {
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	cur, err := config.GetDB().Collection("jobs").Find(ctx, bson.M{}, nil)
	if err != nil { c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()}); return }
	var jobs []bson.M
	if err := cur.All(ctx, &jobs); err != nil { c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()}); return }
	if jobs == nil { jobs = []bson.M{} }
	c.JSON(http.StatusOK, gin.H{"jobs": jobs, "total": len(jobs)})
}
