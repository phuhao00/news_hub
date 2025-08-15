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
	"go.mongodb.org/mongo-driver/mongo/options"
)

// StatusManager 状态管理器
type StatusManager struct {
	redisClient *redis.Client
	db          *mongo.Database
	ctx         context.Context
}

// NewStatusManager 创建状态管理器
func NewStatusManager(redisClient *redis.Client, db *mongo.Database) *StatusManager {
	return &StatusManager{
		redisClient: redisClient,
		db:          db,
		ctx:         context.Background(),
	}
}

// GetTask 获取任务信息
func (sm *StatusManager) GetTask(taskID string) (*CrawlTask, error) {
	// 首先尝试从Redis缓存获取
	cachedTask, err := sm.getTaskFromCache(taskID)
	if err == nil && cachedTask != nil {
		return cachedTask, nil
	}

	// 从MongoDB获取
	collection := sm.db.Collection("crawl_tasks")
	var task CrawlTask
	err = collection.FindOne(sm.ctx, bson.M{"_id": taskID}).Decode(&task)
	if err != nil {
		if err == mongo.ErrNoDocuments {
			return nil, fmt.Errorf("task not found")
		}
		return nil, err
	}

	// 缓存到Redis
	sm.cacheTask(&task)

	return &task, nil
}

// UpdateTaskStatus 更新任务状态
func (sm *StatusManager) UpdateTaskStatus(taskID string, status TaskStatus, workerID string) error {
	now := time.Now()
	update := bson.M{
		"$set": bson.M{
			"status":     status,
			"updated_at": now,
		},
	}

	// 根据状态设置特定字段
	switch status {
	case TaskStatusProcessing:
		update["$set"].(bson.M)["started_at"] = now
		if workerID != "" {
			update["$set"].(bson.M)["worker_id"] = workerID
		}
	case TaskStatusCompleted, TaskStatusFailed:
		update["$set"].(bson.M)["completed_at"] = now
	}

	// 更新数据库
	collection := sm.db.Collection("crawl_tasks")
	_, err := collection.UpdateOne(sm.ctx, bson.M{"_id": taskID}, update)
	if err != nil {
		return err
	}

	// 更新缓存
	sm.updateTaskCache(taskID, status, now)

	return nil
}

// UpdateTaskResult 更新任务结果
func (sm *StatusManager) UpdateTaskResult(taskID string, result *CrawlResult, executionTime float64, workerID string) error {
	now := time.Now()
	update := bson.M{
		"$set": bson.M{
			"status":         TaskStatusCompleted,
			"result":         result,
			"execution_time": executionTime,
			"completed_at":   now,
			"updated_at":     now,
		},
	}

	if workerID != "" {
		update["$set"].(bson.M)["worker_id"] = workerID
	}

	// 更新数据库
	collection := sm.db.Collection("crawl_tasks")
	_, err := collection.UpdateOne(sm.ctx, bson.M{"_id": taskID}, update)
	if err != nil {
		return err
	}

	// 清除缓存，强制下次从数据库读取最新数据
	sm.clearTaskCache(taskID)

	return nil
}

// UpdateTaskError 更新任务错误
func (sm *StatusManager) UpdateTaskError(taskID string, errorMsg string, status TaskStatus) error {
	now := time.Now()
	update := bson.M{
		"$set": bson.M{
			"status":     status,
			"error":      errorMsg,
			"updated_at": now,
		},
	}

	if status == TaskStatusFailed {
		update["$set"].(bson.M)["completed_at"] = now
	}

	// 更新数据库
	collection := sm.db.Collection("crawl_tasks")
	_, err := collection.UpdateOne(sm.ctx, bson.M{"_id": taskID}, update)
	if err != nil {
		return err
	}

	// 清除缓存
	sm.clearTaskCache(taskID)

	return nil
}

// ListTasks 获取任务列表
func (sm *StatusManager) ListTasks(filter bson.M, page, pageSize int) (*TaskListResponse, error) {
	collection := sm.db.Collection("crawl_tasks")

	// 计算总数
	total, err := collection.CountDocuments(sm.ctx, filter)
	if err != nil {
		return nil, err
	}

	// 计算分页
	skip := (page - 1) * pageSize
	totalPages := int((total + int64(pageSize) - 1) / int64(pageSize))

	// 查询选项
	opts := options.Find()
	opts.SetSkip(int64(skip))
	opts.SetLimit(int64(pageSize))
	opts.SetSort(bson.D{{"created_at", -1}}) // 按创建时间倒序

	// 查询任务
	cursor, err := collection.Find(sm.ctx, filter, opts)
	if err != nil {
		return nil, err
	}
	defer cursor.Close(sm.ctx)

	var tasks []CrawlTask
	if err := cursor.All(sm.ctx, &tasks); err != nil {
		return nil, err
	}

	return &TaskListResponse{
		Tasks:      tasks,
		Total:      total,
		Page:       page,
		PageSize:   pageSize,
		TotalPages: totalPages,
	}, nil
}

// GetTasksByStatus 根据状态获取任务
func (sm *StatusManager) GetTasksByStatus(status TaskStatus, limit int) ([]CrawlTask, error) {
	collection := sm.db.Collection("crawl_tasks")
	filter := bson.M{"status": status}

	opts := options.Find()
	if limit > 0 {
		opts.SetLimit(int64(limit))
	}
	opts.SetSort(bson.D{{"created_at", 1}}) // 按创建时间正序

	cursor, err := collection.Find(sm.ctx, filter, opts)
	if err != nil {
		return nil, err
	}
	defer cursor.Close(sm.ctx)

	var tasks []CrawlTask
	if err := cursor.All(sm.ctx, &tasks); err != nil {
		return nil, err
	}

	return tasks, nil
}

// getTaskFromCache 从缓存获取任务
func (sm *StatusManager) getTaskFromCache(taskID string) (*CrawlTask, error) {
	cacheKey := fmt.Sprintf("task:%s", taskID)
	taskJSON, err := sm.redisClient.Get(sm.ctx, cacheKey).Result()
	if err != nil {
		if err == redis.Nil {
			return nil, fmt.Errorf("task not in cache")
		}
		return nil, err
	}

	var task CrawlTask
	if err := json.Unmarshal([]byte(taskJSON), &task); err != nil {
		return nil, err
	}

	return &task, nil
}

// cacheTask 缓存任务
func (sm *StatusManager) cacheTask(task *CrawlTask) {
	cacheKey := fmt.Sprintf("task:%s", task.ID)
	taskJSON, err := json.Marshal(task)
	if err != nil {
		log.Printf("Failed to marshal task for cache: %v", err)
		return
	}

	// 缓存5分钟
	err = sm.redisClient.Set(sm.ctx, cacheKey, taskJSON, 5*time.Minute).Err()
	if err != nil {
		log.Printf("Failed to cache task: %v", err)
	}
}

// updateTaskCache 更新任务缓存
func (sm *StatusManager) updateTaskCache(taskID string, status TaskStatus, updatedAt time.Time) {
	// 获取现有缓存
	task, err := sm.getTaskFromCache(taskID)
	if err != nil {
		return // 缓存不存在，忽略
	}

	// 更新状态和时间
	task.Status = status
	task.UpdatedAt = updatedAt

	// 重新缓存
	sm.cacheTask(task)
}

// clearTaskCache 清除任务缓存
func (sm *StatusManager) clearTaskCache(taskID string) {
	cacheKey := fmt.Sprintf("task:%s", taskID)
	err := sm.redisClient.Del(sm.ctx, cacheKey).Err()
	if err != nil {
		log.Printf("Failed to clear task cache: %v", err)
	}
}