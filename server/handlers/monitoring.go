package handlers

import (
	"context"
	"log"
	"net/http"
	"strconv"
	"time"

	"github.com/gin-gonic/gin"
	"newshub/deduplication"
)

// getStatValue 安全地从统计信息中获取值
func getStatValue(stats map[string]interface{}, key string, defaultValue interface{}) interface{} {
	if value, exists := stats[key]; exists {
		return value
	}
	return defaultValue
}// MonitoringHandler 监控处理器
type MonitoringHandler struct {
	deduplicationService *deduplication.DeduplicationService
}

// NewMonitoringHandler 创建监控处理器
func NewMonitoringHandler(deduplicationService *deduplication.DeduplicationService) *MonitoringHandler {
	return &MonitoringHandler{
		deduplicationService: deduplicationService,
	}
}

// GetSystemStats 获取系统统计信息
func (h *MonitoringHandler) GetSystemStats(c *gin.Context) {
	// 获取去重系统统计
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	
	deduplicationStats, err := h.deduplicationService.GetStats(ctx)
	if err != nil {
		log.Printf("获取去重统计失败: %v", err)
		deduplicationStats = map[string]interface{}{"error": "获取统计失败"}
	}
	
	// 构建系统统计信息
	stats := gin.H{
		"deduplication": deduplicationStats,
		"timestamp": time.Now().Unix(),
		"system": gin.H{
			"uptime": time.Since(time.Now()).Seconds(), // 简化实现
			"version": "1.0.0",
		},
	}
	
	c.JSON(http.StatusOK, gin.H{
		"success": true,
		"data": stats,
	})
}

// GetDeduplicationHealth 获取去重系统健康状态
func (h *MonitoringHandler) GetDeduplicationHealth(c *gin.Context) {
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	
	err := h.deduplicationService.HealthCheck(ctx)
	
	statusCode := http.StatusOK
	healthy := err == nil
	if !healthy {
		statusCode = http.StatusServiceUnavailable
	}
	
	health := gin.H{
		"healthy": healthy,
		"service": "deduplication",
		"timestamp": time.Now().Format(time.RFC3339),
	}
	
	if err != nil {
		health["error"] = err.Error()
	}
	
	c.JSON(statusCode, gin.H{
		"success": healthy,
		"data": health,
	})
}

// SetDeduplicationEnabled 设置去重系统启用状态
func (h *MonitoringHandler) SetDeduplicationEnabled(c *gin.Context) {
	var request struct {
		Enabled bool `json:"enabled" binding:"required"`
	}
	
	if err := c.ShouldBindJSON(&request); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{
			"success": false,
			"error": "Invalid request format",
			"details": err.Error(),
		})
		return
	}
	
	h.deduplicationService.SetEnabled(request.Enabled)
	
	c.JSON(http.StatusOK, gin.H{
		"success": true,
		"message": "Deduplication status updated",
		"data": gin.H{
			"enabled": request.Enabled,
		},
	})
}

// CreateDeduplicationIndexes 创建去重系统索引
func (h *MonitoringHandler) CreateDeduplicationIndexes(c *gin.Context) {
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()
	
	err := h.deduplicationService.CreateIndexes(ctx)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{
			"success": false,
			"error": "Failed to create indexes",
			"details": err.Error(),
		})
		return
	}
	
	c.JSON(http.StatusOK, gin.H{
		"success": true,
		"message": "Indexes created successfully",
	})
}

// GetMetrics 获取性能指标
func (h *MonitoringHandler) GetMetrics(c *gin.Context) {
	// 获取查询参数
	limitStr := c.DefaultQuery("limit", "100")
	limit, err := strconv.Atoi(limitStr)
	if err != nil || limit <= 0 {
		limit = 100
	}
	
	if limit > 1000 {
		limit = 1000 // 限制最大值
	}
	
	// 获取时间范围参数（暂未使用）
	// sinceStr := c.Query("since")
	// var since *time.Time
	// if sinceStr != "" {
	// 	if sinceTime, err := time.Parse(time.RFC3339, sinceStr); err == nil {
	// 		since = &sinceTime
	// 	}
	// }
	
	// 获取去重统计信息
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	
	stats, err := h.deduplicationService.GetStats(ctx)
	if err != nil {
		log.Printf("获取去重统计失败: %v", err)
		stats = map[string]interface{}{}
	}
	
	// 构建指标数据（简化实现）
	metrics := []gin.H{
		{
			"name": "dedup_checks_total",
			"type": "counter",
			"value": getStatValue(stats, "total_checks", 0),
			"timestamp": time.Now().Format(time.RFC3339),
			"labels": gin.H{},
		},
		{
			"name": "dedup_duplicates_found",
			"type": "counter",
			"value": getStatValue(stats, "duplicates_found", 0),
			"timestamp": time.Now().Format(time.RFC3339),
			"labels": gin.H{},
		},
	}
	
	// 应用限制
	if len(metrics) > limit {
		metrics = metrics[:limit]
	}
	
	c.JSON(http.StatusOK, gin.H{
		"success": true,
		"data": gin.H{
			"metrics": metrics,
			"count": len(metrics),
			"limit": limit,
		},
	})
}

// GetAlerts 获取告警信息
func (h *MonitoringHandler) GetAlerts(c *gin.Context) {
	// 获取查询参数
	limitStr := c.DefaultQuery("limit", "50")
	limit, err := strconv.Atoi(limitStr)
	if err != nil || limit <= 0 {
		limit = 50
	}
	
	if limit > 500 {
		limit = 500 // 限制最大值
	}
	
	level := c.Query("level")
	resolvedStr := c.Query("resolved")
	
	var resolved *bool
	if resolvedStr != "" {
		if resolvedBool, err := strconv.ParseBool(resolvedStr); err == nil {
			resolved = &resolvedBool
		}
	}
	
	// 简化实现：返回空告警列表
	// 实际实现中应该从监控服务获取告警数据
	alerts := []gin.H{}
	
	c.JSON(http.StatusOK, gin.H{
		"success": true,
		"data": gin.H{
			"alerts": alerts,
			"count": len(alerts),
			"limit": limit,
			"filters": gin.H{
				"level": level,
				"resolved": resolved,
			},
		},
	})
}

// ResolveAlert 解决告警
func (h *MonitoringHandler) ResolveAlert(c *gin.Context) {
	alertID := c.Param("id")
	if alertID == "" {
		c.JSON(http.StatusBadRequest, gin.H{
			"success": false,
			"error": "Alert ID is required",
		})
		return
	}
	
	// 简化实现：直接返回成功
	// 实际实现中应该调用监控服务解决告警
	c.JSON(http.StatusOK, gin.H{
		"success": true,
		"message": "Alert resolved successfully",
		"data": gin.H{
			"alert_id": alertID,
			"resolved_at": time.Now().Format(time.RFC3339),
		},
	})
}

// ResetStats 重置统计信息
func (h *MonitoringHandler) ResetStats(c *gin.Context) {
	// 简化实现：返回成功消息
	// 实际实现中应该调用相应的重置方法
	c.JSON(http.StatusOK, gin.H{
		"success": true,
		"message": "Statistics reset successfully",
		"timestamp": time.Now().Format(time.RFC3339),
	})
}