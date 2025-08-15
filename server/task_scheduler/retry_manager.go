package task_scheduler

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"time"

	"github.com/go-redis/redis/v8"
	"go.mongodb.org/mongo-driver/bson"
	"go.mongodb.org/mongo-driver/mongo"
)

// RetryManager 重试管理器
type RetryManager struct {
	redisClient *redis.Client
	db          *mongo.Database
	ctx         context.Context
	maxRetries  int
	retryDelay time.Duration
}

// RetryConfig 重试配置
type RetryConfig struct {
	MaxRetries  int           `json:"max_retries"`
	RetryDelay  time.Duration `json:"retry_delay"`
	BackoffRate float64       `json:"backoff_rate"`
}

// DefaultRetryConfig 默认重试配置
func DefaultRetryConfig() RetryConfig {
	return RetryConfig{
		MaxRetries:  3,
		RetryDelay:  30 * time.Second,
		BackoffRate: 2.0,
	}
}

// NewRetryManager 创建重试管理器
func NewRetryManager(redisClient *redis.Client, db *mongo.Database, config RetryConfig) *RetryManager {
	return &RetryManager{
		redisClient: redisClient,
		db:          db,
		ctx:         context.Background(),
		maxRetries:  config.MaxRetries,
		retryDelay:  config.RetryDelay,
	}
}

// ShouldRetry 判断任务是否应该重试
func (rm *RetryManager) ShouldRetry(task *CrawlTask) bool {
	return task.RetryCount < rm.maxRetries
}

// ScheduleRetry 安排任务重试
func (rm *RetryManager) ScheduleRetry(task *CrawlTask, errorMsg string) error {
	if !rm.ShouldRetry(task) {
		// 超过最大重试次数，移到死信队列
		return rm.MoveToDeadLetter(task, errorMsg)
	}

	// 增加重试次数
	task.RetryCount++
	task.Status = TaskStatusPending
	task.Error = errorMsg
	task.UpdatedAt = time.Now()

	// 计算延迟时间（指数退避）
	delay := rm.calculateRetryDelay(task.RetryCount)
	retryAt := time.Now().Add(delay)

	// 更新数据库
	collection := rm.db.Collection("crawl_tasks")
	update := bson.M{
		"$set": bson.M{
			"status":      TaskStatusPending,
			"retry_count": task.RetryCount,
			"error":       errorMsg,
			"retry_at":    retryAt,
			"updated_at":  task.UpdatedAt,
		},
	}

	_, err := collection.UpdateOne(rm.ctx, bson.M{"_id": task.ID}, update)
	if err != nil {
		return fmt.Errorf("failed to update task for retry: %v", err)
	}

	// 安排延迟重试
	return rm.scheduleDelayedRetry(task, delay)
}

// MoveToDeadLetter 移动任务到死信队列
func (rm *RetryManager) MoveToDeadLetter(task *CrawlTask, errorMsg string) error {
	log.Printf("Moving task %s to dead letter queue after %d retries", task.ID, task.RetryCount)

	// 更新任务状态为失败
	task.Status = TaskStatusFailed
	task.Error = fmt.Sprintf("Max retries exceeded: %s", errorMsg)
	task.UpdatedAt = time.Now()
	task.CompletedAt = &task.UpdatedAt

	// 更新数据库
	collection := rm.db.Collection("crawl_tasks")
	update := bson.M{
		"$set": bson.M{
			"status":       TaskStatusFailed,
			"error":        task.Error,
			"updated_at":   task.UpdatedAt,
			"completed_at": task.CompletedAt,
		},
	}

	_, err := collection.UpdateOne(rm.ctx, bson.M{"_id": task.ID}, update)
	if err != nil {
		return fmt.Errorf("failed to update task status to failed: %v", err)
	}

	// 添加到死信队列
	return rm.addToDeadLetterQueue(task)
}

// ProcessRetryQueue 处理重试队列
func (rm *RetryManager) ProcessRetryQueue() error {
	// 获取需要重试的任务
	tasks, err := rm.getRetryableTasks()
	if err != nil {
		return err
	}

	for _, task := range tasks {
		// 重新入队
		err := rm.requeueTask(&task)
		if err != nil {
			log.Printf("Failed to requeue task %s: %v", task.ID, err)
			continue
		}

		log.Printf("Requeued task %s for retry %d", task.ID, task.RetryCount)
	}

	return nil
}

// GetDeadLetterTasks 获取死信队列任务
func (rm *RetryManager) GetDeadLetterTasks(limit int) ([]CrawlTask, error) {
	deadLetterKey := "crawl:dead_letter"
	result, err := rm.redisClient.LRange(rm.ctx, deadLetterKey, 0, int64(limit-1)).Result()
	if err != nil {
		return nil, err
	}

	var tasks []CrawlTask
	for _, taskJSON := range result {
		var task CrawlTask
		if err := json.Unmarshal([]byte(taskJSON), &task); err != nil {
			log.Printf("Failed to unmarshal dead letter task: %v", err)
			continue
		}
		tasks = append(tasks, task)
	}

	return tasks, nil
}

// ReprocessDeadLetterTask 重新处理死信队列任务
func (rm *RetryManager) ReprocessDeadLetterTask(taskID string) error {
	// 从死信队列中移除
	deadLetterKey := "crawl:dead_letter"
	tasks, err := rm.GetDeadLetterTasks(1000) // 获取所有死信任务
	if err != nil {
		return err
	}

	var targetTask *CrawlTask
	for _, task := range tasks {
		if task.ID == taskID {
			targetTask = &task
			break
		}
	}

	if targetTask == nil {
		return fmt.Errorf("task %s not found in dead letter queue", taskID)
	}

	// 重置任务状态
	targetTask.Status = TaskStatusPending
	targetTask.RetryCount = 0
	targetTask.Error = ""
	targetTask.UpdatedAt = time.Now()
	targetTask.CompletedAt = nil

	// 更新数据库
	collection := rm.db.Collection("crawl_tasks")
	update := bson.M{
		"$set": bson.M{
			"status":       TaskStatusPending,
			"retry_count":  0,
			"error":        "",
			"updated_at":   targetTask.UpdatedAt,
		},
		"$unset": bson.M{
			"completed_at": "",
			"retry_at":     "",
		},
	}

	_, err = collection.UpdateOne(rm.ctx, bson.M{"_id": taskID}, update)
	if err != nil {
		return fmt.Errorf("failed to update task for reprocessing: %v", err)
	}

	// 从死信队列移除
	taskJSON, _ := json.Marshal(targetTask)
	err = rm.redisClient.LRem(rm.ctx, deadLetterKey, 1, string(taskJSON)).Err()
	if err != nil {
		log.Printf("Failed to remove task from dead letter queue: %v", err)
	}

	// 重新入队
	return rm.requeueTask(targetTask)
}

// calculateRetryDelay 计算重试延迟时间（指数退避）
func (rm *RetryManager) calculateRetryDelay(retryCount int) time.Duration {
	// 指数退避：delay * (2 ^ (retryCount - 1))
	multiplier := 1
	for i := 1; i < retryCount; i++ {
		multiplier *= 2
	}
	return rm.retryDelay * time.Duration(multiplier)
}

// scheduleDelayedRetry 安排延迟重试
func (rm *RetryManager) scheduleDelayedRetry(task *CrawlTask, delay time.Duration) error {
	// 使用Redis的延迟队列
	retryKey := "crawl:retry_queue"
	taskJSON, err := json.Marshal(task)
	if err != nil {
		return err
	}

	// 使用ZADD添加到有序集合，分数为执行时间戳
	executeAt := time.Now().Add(delay).Unix()
	err = rm.redisClient.ZAdd(rm.ctx, retryKey, &redis.Z{
		Score:  float64(executeAt),
		Member: string(taskJSON),
	}).Err()

	return err
}

// getRetryableTasks 获取可重试的任务
func (rm *RetryManager) getRetryableTasks() ([]CrawlTask, error) {
	retryKey := "crawl:retry_queue"
	now := float64(time.Now().Unix())

	// 获取到期的重试任务
	result, err := rm.redisClient.ZRangeByScore(rm.ctx, retryKey, &redis.ZRangeBy{
		Min: "0",
		Max: fmt.Sprintf("%f", now),
	}).Result()
	if err != nil {
		return nil, err
	}

	var tasks []CrawlTask
	for _, taskJSON := range result {
		var task CrawlTask
		if err := json.Unmarshal([]byte(taskJSON), &task); err != nil {
			log.Printf("Failed to unmarshal retry task: %v", err)
			continue
		}
		tasks = append(tasks, task)

		// 从重试队列中移除
		rm.redisClient.ZRem(rm.ctx, retryKey, taskJSON)
	}

	return tasks, nil
}

// requeueTask 重新入队任务
func (rm *RetryManager) requeueTask(task *CrawlTask) error {
	// 根据优先级选择队列
	queueKey := fmt.Sprintf("crawl:queue:%s", task.Priority)
	taskJSON, err := json.Marshal(task)
	if err != nil {
		return err
	}

	// 添加到队列头部（优先处理重试任务）
	err = rm.redisClient.LPush(rm.ctx, queueKey, string(taskJSON)).Err()
	return err
}

// addToDeadLetterQueue 添加到死信队列
func (rm *RetryManager) addToDeadLetterQueue(task *CrawlTask) error {
	deadLetterKey := "crawl:dead_letter"
	taskJSON, err := json.Marshal(task)
	if err != nil {
		return err
	}

	// 添加到死信队列
	err = rm.redisClient.LPush(rm.ctx, deadLetterKey, string(taskJSON)).Err()
	if err != nil {
		return err
	}

	// 限制死信队列大小（保留最近1000个失败任务）
	err = rm.redisClient.LTrim(rm.ctx, deadLetterKey, 0, 999).Err()
	return err
}