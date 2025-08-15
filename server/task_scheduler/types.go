package task_scheduler

import (
	"time"
)

// TaskStatus 任务状态枚举
type TaskStatus string

const (
	TaskStatusPending    TaskStatus = "pending"
	TaskStatusQueued     TaskStatus = "queued"
	TaskStatusProcessing TaskStatus = "processing"
	TaskStatusCompleted  TaskStatus = "completed"
	TaskStatusFailed     TaskStatus = "failed"
	TaskStatusRetrying   TaskStatus = "retrying"
)

// CrawlTask 爬虫任务结构
type CrawlTask struct {
	ID          string                 `json:"id" bson:"_id"`
	URL         string                 `json:"url" bson:"url"`
	Platform    string                 `json:"platform" bson:"platform"`
	SessionID   string                 `json:"session_id" bson:"session_id"`
	Priority    int                    `json:"priority" bson:"priority"`
	MaxRetries  int                    `json:"max_retries" bson:"max_retries"`
	RetryCount  int                    `json:"retry_count" bson:"retry_count"`
	Status      TaskStatus             `json:"status" bson:"status"`
	CreatedAt   time.Time              `json:"created_at" bson:"created_at"`
	UpdatedAt   time.Time              `json:"updated_at" bson:"updated_at"`
	StartedAt   *time.Time             `json:"started_at,omitempty" bson:"started_at,omitempty"`
	CompletedAt *time.Time             `json:"completed_at,omitempty" bson:"completed_at,omitempty"`
	WorkerID    string                 `json:"worker_id,omitempty" bson:"worker_id,omitempty"`
	ExecutionTime float64              `json:"execution_time,omitempty" bson:"execution_time,omitempty"`
	Result      *CrawlResult           `json:"result,omitempty" bson:"result,omitempty"`
	Error       string                 `json:"error,omitempty" bson:"error,omitempty"`
	Metadata    map[string]interface{} `json:"metadata" bson:"metadata"`
}

// CrawlResult 爬虫结果结构
type CrawlResult struct {
	Title       string    `json:"title" bson:"title"`
	Content     string    `json:"content" bson:"content"`
	Author      string    `json:"author" bson:"author"`
	PublishTime time.Time `json:"publish_time" bson:"publish_time"`
	Tags        []string  `json:"tags" bson:"tags"`
	Images      []string  `json:"images" bson:"images"`
	Links       []string  `json:"links" bson:"links"`
}

// TaskMetrics 任务性能指标
type TaskMetrics struct {
	Date             time.Time `json:"date" bson:"date"`
	Hour             int       `json:"hour" bson:"hour"`
	Platform         string    `json:"platform" bson:"platform"`
	TotalTasks       int       `json:"total_tasks" bson:"total_tasks"`
	CompletedTasks   int       `json:"completed_tasks" bson:"completed_tasks"`
	FailedTasks      int       `json:"failed_tasks" bson:"failed_tasks"`
	RetriedTasks     int       `json:"retried_tasks" bson:"retried_tasks"`
	AvgExecutionTime float64   `json:"avg_execution_time" bson:"avg_execution_time"`
	MaxExecutionTime float64   `json:"max_execution_time" bson:"max_execution_time"`
	MinExecutionTime float64   `json:"min_execution_time" bson:"min_execution_time"`
}

// TaskRequest 任务请求结构
type TaskRequest struct {
	URL        string                 `json:"url" binding:"required"`
	Platform   string                 `json:"platform" binding:"required"`
	SessionID  string                 `json:"session_id" binding:"required"`
	Priority   int                    `json:"priority"`
	MaxRetries int                    `json:"max_retries"`
	Metadata   map[string]interface{} `json:"metadata"`
}

// TaskResponse 任务响应结构
type TaskResponse struct {
	ID        string     `json:"id"`
	Status    TaskStatus `json:"status"`
	CreatedAt time.Time  `json:"created_at"`
	Message   string     `json:"message,omitempty"`
}

// TaskListResponse 任务列表响应结构
type TaskListResponse struct {
	Tasks      []CrawlTask `json:"tasks"`
	Total      int64       `json:"total"`
	Page       int         `json:"page"`
	PageSize   int         `json:"page_size"`
	TotalPages int         `json:"total_pages"`
}