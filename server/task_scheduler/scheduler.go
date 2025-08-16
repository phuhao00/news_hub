package task_scheduler

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"sync"
	"time"

	"github.com/go-redis/redis/v8"
	"github.com/google/uuid"
	"go.mongodb.org/mongo-driver/bson"
	"go.mongodb.org/mongo-driver/mongo"
	"go.mongodb.org/mongo-driver/mongo/options"
)

// TaskScheduler 任务调度器
type TaskScheduler struct {
	redisClient   *redis.Client
	mongoClient   *mongo.Client
	db            *mongo.Database
	taskQueue     chan *CrawlTask
	statusManager *StatusManager
	retryManager  *RetryManager
	config        *SchedulerConfig
	ctx           context.Context
	cancel        context.CancelFunc
	wg            sync.WaitGroup
	running       bool
	mu            sync.RWMutex
}

// SchedulerConfig 调度器配置
type SchedulerConfig struct {
	SchedulerWorkers int           `json:"scheduler_workers"`
	QueueSize        int           `json:"queue_size"`
	BatchSize        int           `json:"batch_size"`
	RedisURL         string        `json:"redis_url"`
	MongoURI         string        `json:"mongo_uri"`
	Database         string        `json:"database"`
	MaxRetries       int           `json:"max_retries"`
	InitialDelay     time.Duration `json:"initial_delay"`
	MaxDelay         time.Duration `json:"max_delay"`
	Multiplier       float64       `json:"multiplier"`
	MetricsInterval  time.Duration `json:"metrics_interval"`
	HealthInterval   time.Duration `json:"health_interval"`
}

// DefaultSchedulerConfig 默认配置
func DefaultSchedulerConfig() *SchedulerConfig {
	return &SchedulerConfig{
		SchedulerWorkers: 10,
		QueueSize:        1000,
		BatchSize:        50,
		RedisURL:         "redis://localhost:6379/0",
		MongoURI:         "mongodb://localhost:27017",
		Database:         "newshub",
		MaxRetries:       3,
		InitialDelay:     5 * time.Second,
		MaxDelay:         300 * time.Second,
		Multiplier:       2.0,
		MetricsInterval:  60 * time.Second,
		HealthInterval:   30 * time.Second,
	}
}

// NewTaskScheduler 创建新的任务调度器
func NewTaskScheduler(config *SchedulerConfig) (*TaskScheduler, error) {
	if config == nil {
		config = DefaultSchedulerConfig()
	}

	// 创建Redis客户端
	opt, err := redis.ParseURL(config.RedisURL)
	if err != nil {
		return nil, fmt.Errorf("failed to parse Redis URL: %w", err)
	}
	redisClient := redis.NewClient(opt)

	// 测试Redis连接
	ctx := context.Background()
	if err := redisClient.Ping(ctx).Err(); err != nil {
		return nil, fmt.Errorf("failed to connect to Redis: %w", err)
	}

	// 创建MongoDB客户端
	mongoClient, err := mongo.Connect(ctx, options.Client().ApplyURI(config.MongoURI))
	if err != nil {
		return nil, fmt.Errorf("failed to connect to MongoDB: %w", err)
	}

	// 测试MongoDB连接
	if err := mongoClient.Ping(ctx, nil); err != nil {
		return nil, fmt.Errorf("failed to ping MongoDB: %w", err)
	}

	db := mongoClient.Database(config.Database)

	// 创建上下文
	ctx, cancel := context.WithCancel(context.Background())

	scheduler := &TaskScheduler{
		redisClient: redisClient,
		mongoClient: mongoClient,
		db:          db,
		taskQueue:   make(chan *CrawlTask, config.QueueSize),
		config:      config,
		ctx:         ctx,
		cancel:      cancel,
	}

	// 初始化状态管理器
	scheduler.statusManager = NewStatusManager(redisClient, db)

	// 初始化重试管理器
	retryConfig := RetryConfig{
		MaxRetries:  config.MaxRetries,
		RetryDelay:  config.InitialDelay,
		BackoffRate: config.Multiplier,
	}
	scheduler.retryManager = NewRetryManager(redisClient, db, retryConfig)

	return scheduler, nil
}

// Start 启动任务调度器
func (ts *TaskScheduler) Start() error {
	ts.mu.Lock()
	defer ts.mu.Unlock()

	if ts.running {
		return fmt.Errorf("scheduler is already running")
	}

	log.Println("Starting task scheduler...")

	// 启动多个goroutine处理任务分发
	for i := 0; i < ts.config.SchedulerWorkers; i++ {
		ts.wg.Add(1)
		go ts.taskDispatcher(i)
	}

	// 启动状态监控goroutine
	// ts.wg.Add(1)
	// go ts.statusMonitor()

	// 启动重试处理goroutine
	// ts.wg.Add(1)
	// go ts.retryHandler()

	// 启动性能指标收集goroutine
	// ts.wg.Add(1)
	// go ts.metricsCollector()

	// 启动重试队列处理器
	ts.wg.Add(1)
	go ts.processRetryQueue()

	ts.running = true
	log.Printf("Task scheduler started with %d workers", ts.config.SchedulerWorkers)

	return nil
}

// Stop 停止任务调度器
func (ts *TaskScheduler) Stop() error {
	ts.mu.Lock()
	defer ts.mu.Unlock()

	if !ts.running {
		return fmt.Errorf("scheduler is not running")
	}

	log.Println("Stopping task scheduler...")

	// 取消上下文
	ts.cancel()

	// 等待所有goroutine结束
	ts.wg.Wait()

	// 关闭Redis连接
	if err := ts.redisClient.Close(); err != nil {
		log.Printf("Error closing Redis client: %v", err)
	}

	// 关闭MongoDB连接
	if err := ts.mongoClient.Disconnect(ts.ctx); err != nil {
		log.Printf("Error closing MongoDB client: %v", err)
	}

	ts.running = false
	log.Println("Task scheduler stopped")

	return nil
}

// ScheduleTask 调度任务
func (ts *TaskScheduler) ScheduleTask(task *CrawlTask) error {
	// 验证任务参数
	if err := ts.validateTask(task); err != nil {
		return fmt.Errorf("task validation failed: %w", err)
	}

	// 生成任务ID
	if task.ID == "" {
		task.ID = uuid.New().String()
	}
	// 设置TaskID字段（与ID保持一致）
	if task.TaskID == "" {
		task.TaskID = task.ID
	}

	// 设置默认值
	ts.setTaskDefaults(task)

	// 保存任务到数据库
	task.Status = TaskStatusPending
	task.CreatedAt = time.Now()
	task.UpdatedAt = task.CreatedAt

	if err := ts.saveTask(task); err != nil {
		return fmt.Errorf("failed to save task: %w", err)
	}

	// 推送到任务队列
	if err := ts.enqueueTask(task); err != nil {
		return fmt.Errorf("failed to enqueue task: %w", err)
	}

	log.Printf("Task %s scheduled successfully", task.ID)
	return nil
}

// validateTask 验证任务参数
func (ts *TaskScheduler) validateTask(task *CrawlTask) error {
	if task == nil {
		return fmt.Errorf("task cannot be nil")
	}
	if task.URL == "" {
		return fmt.Errorf("task URL cannot be empty")
	}
	if task.Platform == "" {
		return fmt.Errorf("task platform cannot be empty")
	}
	if task.SessionID == "" {
		return fmt.Errorf("task session ID cannot be empty")
	}
	return nil
}

// setTaskDefaults 设置任务默认值
func (ts *TaskScheduler) setTaskDefaults(task *CrawlTask) {
	// 优先级0为超高优先级（实时爬取），不设置默认值
	// 只有当优先级未设置（负数或未指定）时才设置默认值
	if task.Priority < 0 {
		task.Priority = 2 // 默认普通优先级
	}
	if task.MaxRetries == 0 {
		task.MaxRetries = ts.config.MaxRetries
	}
	if task.Metadata == nil {
		task.Metadata = make(map[string]interface{})
	}
}

// saveTask 保存任务到数据库
func (ts *TaskScheduler) saveTask(task *CrawlTask) error {
	collection := ts.db.Collection("crawl_tasks")
	_, err := collection.InsertOne(ts.ctx, task)
	return err
}

// enqueueTask 将任务推送到队列
func (ts *TaskScheduler) enqueueTask(task *CrawlTask) error {
	taskJSON, err := json.Marshal(task)
	if err != nil {
		return err
	}

	// 根据优先级选择队列
	var queueName string
	switch task.Priority {
	case 0:
		queueName = "crawl_tasks:realtime_priority" // 超高优先级，用于实时爬取
	case 1:
		queueName = "crawl_tasks:high_priority"
	case 2:
		queueName = "crawl_tasks:normal_priority"
	default:
		queueName = "crawl_tasks:low_priority"
	}

	// 推送到Redis队列
	err = ts.redisClient.RPush(ts.ctx, queueName, taskJSON).Err()
	if err != nil {
		return err
	}

	// 更新任务状态为已排队
	task.Status = TaskStatusQueued
	task.UpdatedAt = time.Now()
	return ts.updateTaskStatus(task.ID, TaskStatusQueued)
}

// updateTaskStatus 更新任务状态
func (ts *TaskScheduler) updateTaskStatus(taskID string, status TaskStatus) error {
	collection := ts.db.Collection("crawl_tasks")
	filter := bson.M{"_id": taskID}
	update := bson.M{
		"$set": bson.M{
			"status":     status,
			"updated_at": time.Now(),
		},
	}
	_, err := collection.UpdateOne(ts.ctx, filter, update)
	return err
}

// GetTask 获取任务信息
func (ts *TaskScheduler) GetTask(taskID string) (*CrawlTask, error) {
	return ts.statusManager.GetTask(taskID)
}

// ListTasks 获取任务列表
func (ts *TaskScheduler) ListTasks(filter bson.M, page, pageSize int) (*TaskListResponse, error) {
	return ts.statusManager.ListTasks(filter, page, pageSize)
}

// UpdateTaskStatus 更新任务状态
func (ts *TaskScheduler) UpdateTaskStatus(taskID string, status TaskStatus, workerID string) error {
	return ts.statusManager.UpdateTaskStatus(taskID, status, workerID)
}

// UpdateTaskResult 更新任务结果
func (ts *TaskScheduler) UpdateTaskResult(taskID string, result *CrawlResult, executionTime float64, workerID string) error {
	return ts.statusManager.UpdateTaskResult(taskID, result, executionTime, workerID)
}

// UpdateTaskError 更新任务错误
func (ts *TaskScheduler) UpdateTaskError(taskID string, errorMsg string, status TaskStatus) error {
	return ts.statusManager.UpdateTaskError(taskID, errorMsg, status)
}

// GetNextTask 获取下一个待处理任务
func (ts *TaskScheduler) GetNextTask(workerID string) (*CrawlTask, error) {
	// 从超高优先级队列开始获取任务
	queues := []string{"crawl_tasks:realtime_priority", "crawl_tasks:high_priority", "crawl_tasks:normal_priority", "crawl_tasks:low_priority"}
	
	for _, queue := range queues {
		taskJSON, err := ts.redisClient.LPop(ts.ctx, queue).Result()
		if err == redis.Nil {
			continue // 队列为空，尝试下一个队列
		}
		if err != nil {
			return nil, err
		}
		
		var task CrawlTask
		if err := json.Unmarshal([]byte(taskJSON), &task); err != nil {
			return nil, err
		}
		
		// 更新任务状态为处理中
		task.Status = TaskStatusProcessing
		task.WorkerID = workerID
		task.StartedAt = &[]time.Time{time.Now()}[0]
		task.UpdatedAt = time.Now()
		
		if err := ts.updateTaskStatus(task.ID, TaskStatusProcessing); err != nil {
			return nil, err
		}
		
		return &task, nil
	}
	
	return nil, fmt.Errorf("no tasks available")
}

// RetryTask 重试任务
func (ts *TaskScheduler) RetryTask(taskID string) error {
	task, err := ts.GetTask(taskID)
	if err != nil {
		return err
	}

	return ts.retryManager.ScheduleRetry(task, "Manual retry requested")
}

// GetTaskMetrics 获取任务统计信息
func (ts *TaskScheduler) GetTaskMetrics(from, to time.Time) (*TaskMetrics, error) {
	db := ts.db
	collection := db.Collection("crawl_tasks")
	ctx := context.Background()

	// 时间过滤条件
	timeFilter := bson.M{
		"created_at": bson.M{
			"$gte": from,
			"$lte": to,
		},
	}

	// 统计各状态任务数量
	pipeline := []bson.M{
		{"$match": timeFilter},
		{"$group": bson.M{
			"_id":   "$status",
			"count": bson.M{"$sum": 1},
		}},
	}

	cursor, err := collection.Aggregate(ctx, pipeline)
	if err != nil {
		return nil, err
	}
	defer cursor.Close(ctx)

	statusCount := make(map[string]int64)
	for cursor.Next(ctx) {
		var result struct {
			ID    string `bson:"_id"`
			Count int64  `bson:"count"`
		}
		if err := cursor.Decode(&result); err != nil {
			continue
		}
		statusCount[result.ID] = result.Count
	}

	// 计算平均执行时间
	avgExecPipeline := []bson.M{
		{"$match": bson.M{
			"created_at": timeFilter["created_at"],
			"status":     TaskStatusCompleted,
			"execution_time": bson.M{"$exists": true, "$ne": nil},
		}},
		{"$group": bson.M{
			"_id":              nil,
			"avg_exec_time":    bson.M{"$avg": "$execution_time"},
			"min_exec_time":    bson.M{"$min": "$execution_time"},
			"max_exec_time":    bson.M{"$max": "$execution_time"},
		}},
	}

	avgCursor, err := collection.Aggregate(ctx, avgExecPipeline)
	if err != nil {
		return nil, err
	}
	defer avgCursor.Close(ctx)

	var avgExecTime, minExecTime, maxExecTime float64
	if avgCursor.Next(ctx) {
		var result struct {
			AvgExecTime float64 `bson:"avg_exec_time"`
			MinExecTime float64 `bson:"min_exec_time"`
			MaxExecTime float64 `bson:"max_exec_time"`
		}
		if err := avgCursor.Decode(&result); err == nil {
			avgExecTime = result.AvgExecTime
			minExecTime = result.MinExecTime
			maxExecTime = result.MaxExecTime
		}
	}

	return &TaskMetrics{
		Date:             time.Now(),
		Hour:             time.Now().Hour(),
		Platform:         "all",
		TotalTasks:       int(statusCount[string(TaskStatusPending)] + statusCount[string(TaskStatusProcessing)] + statusCount[string(TaskStatusCompleted)] + statusCount[string(TaskStatusFailed)]),
		CompletedTasks:   int(statusCount[string(TaskStatusCompleted)]),
		FailedTasks:      int(statusCount[string(TaskStatusFailed)]),
		RetriedTasks:     int(statusCount[string(TaskStatusRetrying)]),
		AvgExecutionTime: avgExecTime,
		MaxExecutionTime: maxExecTime,
		MinExecutionTime: minExecTime,
	}, nil
}

// GetDeadLetterTasks 获取死信队列任务
func (ts *TaskScheduler) GetDeadLetterTasks(limit int) ([]CrawlTask, error) {
	return ts.retryManager.GetDeadLetterTasks(limit)
}

// ReprocessDeadLetterTask 重新处理死信队列任务
func (ts *TaskScheduler) ReprocessDeadLetterTask(taskID string) error {
	return ts.retryManager.ReprocessDeadLetterTask(taskID)
}

// processRetryQueue 处理重试队列
func (ts *TaskScheduler) processRetryQueue() {
	ticker := time.NewTicker(30 * time.Second) // 每30秒检查一次重试队列
	defer ticker.Stop()

	for {
		select {
		case <-ticker.C:
			if err := ts.retryManager.ProcessRetryQueue(); err != nil {
				log.Printf("Failed to process retry queue: %v", err)
			}
		case <-ts.ctx.Done():
			return
		}
	}
}