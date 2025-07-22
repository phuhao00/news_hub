package handlers

import (
	"context"
	"net/http"
	"time"

	"github.com/gin-gonic/gin"
	"go.mongodb.org/mongo-driver/mongo/readpref"

	"newshub/config"
)

// HealthCheck 健康检查接口
func HealthCheck(c *gin.Context) {
	// 检查MongoDB连接
	ctx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
	defer cancel()

	mongoStatus := "healthy"
	if err := config.GetDB().Client().Ping(ctx, readpref.Primary()); err != nil {
		mongoStatus = "unhealthy"
	}

	// 检查存储目录
	storageStatus := "healthy"
	if err := config.InitStorage(); err != nil {
		storageStatus = "unhealthy"
	}

	// 返回健康状态
	c.JSON(http.StatusOK, gin.H{
		"status": "running",
		"timestamp": time.Now().Format(time.RFC3339),
		"services": gin.H{
			"mongodb": mongoStatus,
			"storage": storageStatus,
		},
	})
}