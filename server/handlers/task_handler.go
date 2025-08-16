package handlers

import (
	"net/http"
	"strconv"
	"time"

	"github.com/gin-gonic/gin"
	"go.mongodb.org/mongo-driver/bson"
	"newshub/task_scheduler"
)

// TaskHandler 任务处理器
type TaskHandler struct {
	scheduler *task_scheduler.TaskScheduler
}

// NewTaskHandler 创建任务处理器
func NewTaskHandler(scheduler *task_scheduler.TaskScheduler) *TaskHandler {
	return &TaskHandler{
		scheduler: scheduler,
	}
}

// CreateTask 创建爬取任务
func (h *TaskHandler) CreateTask(c *gin.Context) {
	var req task_scheduler.TaskRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{
			"error": "Invalid request format",
			"details": err.Error(),
		})
		return
	}

	// 验证必填字段
	if req.URL == "" {
		c.JSON(http.StatusBadRequest, gin.H{
			"error": "URL is required",
		})
		return
	}

	// 设置默认值
	if req.Priority == 0 {
		req.Priority = 5 // medium priority
	}
	if req.MaxRetries == 0 {
		req.MaxRetries = 3
	}

	// 创建CrawlTask
	task := &task_scheduler.CrawlTask{
		URL:           req.URL,
		Platform:      req.Platform,
		SessionID:     req.SessionID,
		InstanceID:    req.InstanceID,
		TaskType:      req.TaskType,
		AutoTriggered: req.AutoTriggered,
		TriggerReason: req.TriggerReason,
		Priority:      req.Priority,
		MaxRetries:    req.MaxRetries,
		Metadata:      req.Metadata,
	}

	// 调度任务
	if err := h.scheduler.ScheduleTask(task); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	// 返回任务信息
	c.JSON(http.StatusOK, task_scheduler.TaskResponse{
		ID:        task.ID,
		Status:    task_scheduler.TaskStatusQueued,
		CreatedAt: time.Now(),
		Message:   "Task scheduled successfully",
	})
}

// GetTask 获取任务详情
func (h *TaskHandler) GetTask(c *gin.Context) {
	taskID := c.Param("id")
	if taskID == "" {
		c.JSON(http.StatusBadRequest, gin.H{
			"error": "Task ID is required",
		})
		return
	}

	task, err := h.scheduler.GetTask(taskID)
	if err != nil {
		if err.Error() == "task not found" {
			c.JSON(http.StatusNotFound, gin.H{
				"error": "Task not found",
			})
		} else {
			c.JSON(http.StatusInternalServerError, gin.H{
				"error": "Failed to get task",
				"details": err.Error(),
			})
		}
		return
	}

	c.JSON(http.StatusOK, task)
}

// ListTasks 获取任务列表
func (h *TaskHandler) ListTasks(c *gin.Context) {
	// 解析查询参数
	page, _ := strconv.Atoi(c.DefaultQuery("page", "1"))
	pageSize, _ := strconv.Atoi(c.DefaultQuery("page_size", "20"))
	status := c.Query("status")
	priority := c.Query("priority")
	browserID := c.Query("browser_id")

	// 验证分页参数
	if page < 1 {
		page = 1
	}
	if pageSize < 1 || pageSize > 100 {
		pageSize = 20
	}

	// 构建过滤条件
	filter := bson.M{}
	if status != "" {
		filter["status"] = status
	}
	if priority != "" {
		filter["priority"] = priority
	}
	if browserID != "" {
		filter["browser_id"] = browserID
	}

	// 获取任务列表
	response, err := h.scheduler.ListTasks(filter, page, pageSize)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{
			"error": "Failed to get task list",
			"details": err.Error(),
		})
		return
	}

	c.JSON(http.StatusOK, response)
}

// UpdateTaskStatus 更新任务状态（供爬虫服务调用）
func (h *TaskHandler) UpdateTaskStatus(c *gin.Context) {
	taskID := c.Param("id")
	if taskID == "" {
		c.JSON(http.StatusBadRequest, gin.H{
			"error": "Task ID is required",
		})
		return
	}

	var req struct {
		Status    task_scheduler.TaskStatus `json:"status" binding:"required"`
		WorkerID  string                    `json:"worker_id,omitempty"`
		Error     string                    `json:"error,omitempty"`
		Result    *task_scheduler.CrawlResult `json:"result,omitempty"`
		ExecTime  float64                   `json:"execution_time,omitempty"`
	}

	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{
			"error": "Invalid request format",
			"details": err.Error(),
		})
		return
	}

	// 根据状态更新任务
	var err error
	switch req.Status {
	case task_scheduler.TaskStatusCompleted:
		if req.Result != nil {
			err = h.scheduler.UpdateTaskResult(taskID, req.Result, req.ExecTime, req.WorkerID)
		} else {
			err = h.scheduler.UpdateTaskStatus(taskID, req.Status, req.WorkerID)
		}
	case task_scheduler.TaskStatusFailed:
		if req.Error != "" {
			err = h.scheduler.UpdateTaskError(taskID, req.Error, req.Status)
		} else {
			err = h.scheduler.UpdateTaskStatus(taskID, req.Status, req.WorkerID)
		}
	default:
		err = h.scheduler.UpdateTaskStatus(taskID, req.Status, req.WorkerID)
	}

	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{
			"error": "Failed to update task status",
			"details": err.Error(),
		})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"message": "Task status updated successfully",
	})
}

// GetNextTask 获取下一个待处理任务（供爬虫服务调用）
func (h *TaskHandler) GetNextTask(c *gin.Context) {
	workerID := c.Query("worker_id")
	if workerID == "" {
		c.JSON(http.StatusBadRequest, gin.H{
			"error": "Worker ID is required",
		})
		return
	}

	task, err := h.scheduler.GetNextTask(workerID)
	if err != nil {
		if err.Error() == "no tasks available" {
			c.JSON(http.StatusNoContent, gin.H{
				"message": "No tasks available",
			})
		} else {
			c.JSON(http.StatusInternalServerError, gin.H{
				"error": "Failed to get next task",
				"details": err.Error(),
			})
		}
		return
	}

	c.JSON(http.StatusOK, task)
}

// RetryTask 重试失败任务
func (h *TaskHandler) RetryTask(c *gin.Context) {
	taskID := c.Param("id")
	if taskID == "" {
		c.JSON(http.StatusBadRequest, gin.H{
			"error": "Task ID is required",
		})
		return
	}

	err := h.scheduler.RetryTask(taskID)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{
			"error": "Failed to retry task",
			"details": err.Error(),
		})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"message": "Task scheduled for retry",
	})
}

// GetTaskMetrics 获取任务统计信息
func (h *TaskHandler) GetTaskMetrics(c *gin.Context) {
	// 时间范围参数
	from := c.Query("from")
	to := c.Query("to")

	var fromTime, toTime time.Time
	var err error

	if from != "" {
		fromTime, err = time.Parse(time.RFC3339, from)
		if err != nil {
			c.JSON(http.StatusBadRequest, gin.H{
				"error": "Invalid from time format, use RFC3339",
			})
			return
		}
	} else {
		// 默认24小时前
		fromTime = time.Now().Add(-24 * time.Hour)
	}

	if to != "" {
		toTime, err = time.Parse(time.RFC3339, to)
		if err != nil {
			c.JSON(http.StatusBadRequest, gin.H{
				"error": "Invalid to time format, use RFC3339",
			})
			return
		}
	} else {
		// 默认当前时间
		toTime = time.Now()
	}

	metrics, err := h.scheduler.GetTaskMetrics(fromTime, toTime)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{
			"error": "Failed to get task metrics",
			"details": err.Error(),
		})
		return
	}

	c.JSON(http.StatusOK, metrics)
}

// GetDeadLetterTasks 获取死信队列任务
func (h *TaskHandler) GetDeadLetterTasks(c *gin.Context) {
	limit, _ := strconv.Atoi(c.DefaultQuery("limit", "50"))
	if limit < 1 || limit > 200 {
		limit = 50
	}

	tasks, err := h.scheduler.GetDeadLetterTasks(limit)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{
			"error": "Failed to get dead letter tasks",
			"details": err.Error(),
		})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"tasks": tasks,
		"count": len(tasks),
	})
}

// ReprocessDeadLetterTask 重新处理死信队列任务
func (h *TaskHandler) ReprocessDeadLetterTask(c *gin.Context) {
	taskID := c.Param("id")
	if taskID == "" {
		c.JSON(http.StatusBadRequest, gin.H{
			"error": "Task ID is required",
		})
		return
	}

	err := h.scheduler.ReprocessDeadLetterTask(taskID)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{
			"error": "Failed to reprocess dead letter task",
			"details": err.Error(),
		})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"message": "Dead letter task reprocessed successfully",
	})
}