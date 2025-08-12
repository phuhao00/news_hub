package handlers

import (
	"net/http"
	"strconv"
	"time"

	"github.com/gin-gonic/gin"
	"newshub/services"
)

// StorageHandler 存储处理器
type StorageHandler struct {
	storageService *services.StorageService
}

// NewStorageHandler 创建存储处理器
func NewStorageHandler() *StorageHandler {
	return &StorageHandler{
		storageService: services.NewStorageService(),
	}
}

// UploadImageRequest 上传图片请求
type UploadImageRequest struct {
	Folder string `form:"folder" json:"folder"` // 可选的文件夹路径
}

// UploadImage 上传图片
func (h *StorageHandler) UploadImage(c *gin.Context) {
	// 解析表单数据
	var req UploadImageRequest
	if err := c.ShouldBind(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "无效的请求参数"})
		return
	}

	// 获取上传的文件
	file, header, err := c.Request.FormFile("file")
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "获取文件失败"})
		return
	}
	defer file.Close()

	// 验证文件类型
	contentType := header.Header.Get("Content-Type")
	if !isImageType(contentType) {
		c.JSON(http.StatusBadRequest, gin.H{"error": "只支持图片文件"})
		return
	}

	// 设置默认文件夹
	folder := req.Folder
	if folder == "" {
		folder = "images"
	}

	// 上传文件
	fileInfo, err := h.storageService.UploadFile(c.Request.Context(), file, header, folder)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"message": "文件上传成功",
		"data":    fileInfo,
	})
}

// UploadVideo 上传视频
func (h *StorageHandler) UploadVideo(c *gin.Context) {
	// 解析表单数据
	var req UploadImageRequest
	if err := c.ShouldBind(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "无效的请求参数"})
		return
	}

	// 获取上传的文件
	file, header, err := c.Request.FormFile("file")
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "获取文件失败"})
		return
	}
	defer file.Close()

	// 验证文件类型
	contentType := header.Header.Get("Content-Type")
	if !isVideoType(contentType) {
		c.JSON(http.StatusBadRequest, gin.H{"error": "只支持视频文件"})
		return
	}

	// 设置默认文件夹
	folder := req.Folder
	if folder == "" {
		folder = "videos"
	}

	// 上传文件
	fileInfo, err := h.storageService.UploadFile(c.Request.Context(), file, header, folder)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"message": "文件上传成功",
		"data":    fileInfo,
	})
}

// ListFiles 列出文件
func (h *StorageHandler) ListFiles(c *gin.Context) {
	folder := c.Query("folder")
	limitStr := c.DefaultQuery("limit", "20")
	limit, err := strconv.Atoi(limitStr)
	if err != nil {
		limit = 20
	}

	files, err := h.storageService.ListFiles(c.Request.Context(), folder, limit)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"message": "获取文件列表成功",
		"data":    files,
	})
}

// DeleteFile 删除文件
func (h *StorageHandler) DeleteFile(c *gin.Context) {
	fileName := c.Param("filename")
	if fileName == "" {
		c.JSON(http.StatusBadRequest, gin.H{"error": "文件名不能为空"})
		return
	}

	err := h.storageService.DeleteFile(c.Request.Context(), fileName)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, gin.H{"message": "文件删除成功"})
}

// GetFileURL 获取文件临时访问URL
func (h *StorageHandler) GetFileURL(c *gin.Context) {
	fileName := c.Param("filename")
	if fileName == "" {
		c.JSON(http.StatusBadRequest, gin.H{"error": "文件名不能为空"})
		return
	}

	// 默认1小时过期
	expiry := time.Hour
	if expiryStr := c.Query("expiry"); expiryStr != "" {
		if duration, err := time.ParseDuration(expiryStr); err == nil {
			expiry = duration
		}
	}

	url, err := h.storageService.GetFileURL(c.Request.Context(), fileName, expiry)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"message": "获取文件URL成功",
		"data": gin.H{
			"url":    url,
			"expiry": expiry.String(),
		},
	})
}

// isImageType 检查是否为图片类型
func isImageType(contentType string) bool {
	imageTypes := []string{
		"image/jpeg",
		"image/jpg",
		"image/png",
		"image/gif",
		"image/webp",
		"image/bmp",
		"image/svg+xml",
	}

	for _, imageType := range imageTypes {
		if contentType == imageType {
			return true
		}
	}
	return false
}

// isVideoType 检查是否为视频类型
func isVideoType(contentType string) bool {
	videoTypes := []string{
		"video/mp4",
		"video/avi",
		"video/mov",
		"video/wmv",
		"video/flv",
		"video/webm",
		"video/mkv",
		"video/3gp",
	}

	for _, videoType := range videoTypes {
		if contentType == videoType {
			return true
		}
	}
	return false
}