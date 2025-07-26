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

func CreateCreator(c *gin.Context) {
	var creator models.Creator
	if err := c.ShouldBindJSON(&creator); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	// 设置默认值
	if creator.DisplayName == "" {
		creator.DisplayName = creator.Username
	}
	if creator.CrawlInterval == 0 {
		creator.CrawlInterval = 60 // 默认60分钟
	}
	creator.CrawlStatus = "idle"
	creator.AutoCrawlEnabled = true // 默认启用自动爬取
	creator.CreatedAt = time.Now()
	creator.UpdatedAt = time.Now()

	// 计算下次爬取时间
	if creator.AutoCrawlEnabled {
		nextCrawl := time.Now().Add(time.Duration(creator.CrawlInterval) * time.Minute)
		creator.NextCrawlAt = &nextCrawl
	}

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	result, err := config.GetDB().Collection("creators").InsertOne(ctx, creator)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	creator.ID = result.InsertedID.(primitive.ObjectID)
	c.JSON(http.StatusCreated, creator)
}

func GetCreators(c *gin.Context) {
	var creators []models.Creator

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	cursor, err := config.GetDB().Collection("creators").Find(ctx, bson.M{})
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	defer cursor.Close(ctx)

	if err := cursor.All(ctx, &creators); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	// Ensure we always return an array, never null
	if creators == nil {
		creators = []models.Creator{}
	}

	c.JSON(http.StatusOK, creators)
}

func DeleteCreator(c *gin.Context) {
	id, err := primitive.ObjectIDFromHex(c.Param("id"))
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid ID"})
		return
	}

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	result, err := config.GetDB().Collection("creators").DeleteOne(ctx, bson.M{"_id": id})
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	if result.DeletedCount == 0 {
		c.JSON(http.StatusNotFound, gin.H{"error": "Creator not found"})
		return
	}

	c.JSON(http.StatusOK, gin.H{"message": "Creator deleted successfully"})
}
