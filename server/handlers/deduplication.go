package handlers

import (
	"context"
	"log"
	"net/http"
	"time"

	"github.com/gin-gonic/gin"

	"newshub/config"
	"newshub/deduplication"
)

// DeduplicationHandler 去重系统处理器
type DeduplicationHandler struct {
	service *deduplication.DeduplicationService
}

// NewDeduplicationHandler 创建去重处理器
func NewDeduplicationHandler() *DeduplicationHandler {
	db := config.GetDB()
	return &DeduplicationHandler{
		service: deduplication.NewDeduplicationService(db),
	}
}

// GetStats 获取去重统计信息
func (h *DeduplicationHandler) GetStats(c *gin.Context) {
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()

	stats, err := h.service.GetStats(ctx)
	if err != nil {
		log.Printf("获取去重统计失败: %v", err)
		c.JSON(http.StatusInternalServerError, gin.H{
			"error": "获取去重统计失败",
			"details": err.Error(),
		})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"status": "success",
		"data":   stats,
	})
}

// HealthCheck 去重系统健康检查
func (h *DeduplicationHandler) HealthCheck(c *gin.Context) {
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	err := h.service.HealthCheck(ctx)
	if err != nil {
		log.Printf("去重系统健康检查失败: %v", err)
		c.JSON(http.StatusServiceUnavailable, gin.H{
			"status": "unhealthy",
			"error":  err.Error(),
		})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"status":  "healthy",
		"message": "去重系统运行正常",
		"enabled": h.service.IsEnabled(),
	})
}

// SetEnabled 设置去重系统启用状态
func (h *DeduplicationHandler) SetEnabled(c *gin.Context) {
	var req struct {
		Enabled bool `json:"enabled"`
	}

	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{
			"error": "无效的请求参数",
			"details": err.Error(),
		})
		return
	}

	h.service.SetEnabled(req.Enabled)

	log.Printf("去重系统状态已更新: enabled=%v", req.Enabled)
	c.JSON(http.StatusOK, gin.H{
		"status":  "success",
		"message": "去重系统状态已更新",
		"enabled": req.Enabled,
	})
}

// CreateIndexes 创建去重系统索引
func (h *DeduplicationHandler) CreateIndexes(c *gin.Context) {
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()

	err := h.service.CreateIndexes(ctx)
	if err != nil {
		log.Printf("创建去重索引失败: %v", err)
		c.JSON(http.StatusInternalServerError, gin.H{
			"error": "创建去重索引失败",
			"details": err.Error(),
		})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"status":  "success",
		"message": "去重索引创建成功",
	})
}

// CheckDuplicate 检查单个内容是否重复
func (h *DeduplicationHandler) CheckDuplicate(c *gin.Context) {
	var req deduplication.ContentItem

	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{
			"error": "无效的请求参数",
			"details": err.Error(),
		})
		return
	}

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	result, err := h.service.CheckDuplicate(ctx, &req)
	if err != nil {
		log.Printf("检查重复失败: %v", err)
		c.JSON(http.StatusInternalServerError, gin.H{
			"error": "检查重复失败",
			"details": err.Error(),
		})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"status": "success",
		"data":   result,
	})
}

// BatchCheckDuplicate 批量检查内容是否重复
func (h *DeduplicationHandler) BatchCheckDuplicate(c *gin.Context) {
	var req struct {
		Items []*deduplication.ContentItem `json:"items"`
	}

	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{
			"error": "无效的请求参数",
			"details": err.Error(),
		})
		return
	}

	if len(req.Items) == 0 {
		c.JSON(http.StatusBadRequest, gin.H{
			"error": "请提供要检查的内容项",
		})
		return
	}

	if len(req.Items) > 100 {
		c.JSON(http.StatusBadRequest, gin.H{
			"error": "批量检查最多支持100个项目",
		})
		return
	}

	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()

	results, err := h.service.BatchCheckDuplicate(ctx, req.Items)
	if err != nil {
		log.Printf("批量检查重复失败: %v", err)
		c.JSON(http.StatusInternalServerError, gin.H{
			"error": "批量检查重复失败",
			"details": err.Error(),
		})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"status": "success",
		"data":   results,
		"total":  len(results),
	})
}