package task_scheduler

import (
	"encoding/json"
	"fmt"
	"log"
	"time"
)

// taskDispatcher 任务分发器
func (ts *TaskScheduler) taskDispatcher(workerID int) {
	defer ts.wg.Done()

	log.Printf("Task dispatcher %d started", workerID)

	for {
		select {
		case <-ts.ctx.Done():
			log.Printf("Task dispatcher %d stopped", workerID)
			return
		default:
			// 从优先级队列获取任务
			task, err := ts.dequeueTask()
			if err != nil {
				if err.Error() != "no tasks available" {
					log.Printf("Dispatcher %d error: %v", workerID, err)
				}
				time.Sleep(1 * time.Second)
				continue
			}

			if task != nil {
				// 分发任务到Python爬虫服务
				go ts.dispatchToPython(task, workerID)
			}
		}
	}
}

// dequeueTask 从队列获取任务
func (ts *TaskScheduler) dequeueTask() (*CrawlTask, error) {
	// 按优先级顺序检查队列
	queues := []string{
		"crawl_tasks:high_priority",
		"crawl_tasks:normal_priority",
		"crawl_tasks:low_priority",
	}

	for _, queueName := range queues {
		// 使用BLPOP阻塞获取任务，超时1秒
		result, err := ts.redisClient.BLPop(ts.ctx, 1*time.Second, queueName).Result()
		if err != nil {
			if err.Error() == "redis: nil" {
				continue // 队列为空，检查下一个队列
			}
			return nil, err
		}

		if len(result) < 2 {
			continue
		}

		// 解析任务
		var task CrawlTask
		if err := json.Unmarshal([]byte(result[1]), &task); err != nil {
			log.Printf("Failed to unmarshal task: %v", err)
			continue
		}

		return &task, nil
	}

	return nil, fmt.Errorf("no tasks available")
}

// dispatchToPython 分发任务到Python爬虫服务
func (ts *TaskScheduler) dispatchToPython(task *CrawlTask, dispatcherID int) {
	log.Printf("Dispatcher %d dispatching task %s to Python service", dispatcherID, task.ID)

	// 更新任务状态为处理中
	task.Status = TaskStatusProcessing
	startTime := time.Now()
	task.StartedAt = &startTime
	task.UpdatedAt = startTime

	if err := ts.updateTaskStatus(task.ID, TaskStatusProcessing); err != nil {
		log.Printf("Failed to update task status: %v", err)
	}

	// 将任务推送到Python服务的处理队列
	if err := ts.sendToPythonQueue(task); err != nil {
		log.Printf("Failed to send task to Python queue: %v", err)
		// 任务分发失败，标记为失败状态
		ts.handleTaskFailure(task, fmt.Sprintf("Failed to dispatch to Python: %v", err))
		return
	}

	log.Printf("Task %s successfully dispatched to Python service", task.ID)
}

// sendToPythonQueue 发送任务到Python处理队列
func (ts *TaskScheduler) sendToPythonQueue(task *CrawlTask) error {
	taskJSON, err := json.Marshal(task)
	if err != nil {
		return fmt.Errorf("failed to marshal task: %w", err)
	}

	// 推送到Python服务的任务队列
	err = ts.redisClient.RPush(ts.ctx, "python_crawl_tasks", taskJSON).Err()
	if err != nil {
		return fmt.Errorf("failed to push to Python queue: %w", err)
	}

	return nil
}

// handleTaskFailure 处理任务失败
func (ts *TaskScheduler) handleTaskFailure(task *CrawlTask, errorMsg string) {
	task.Error = errorMsg
	task.UpdatedAt = time.Now()

	// 检查是否需要重试
	if task.RetryCount < task.MaxRetries {
		// 添加到重试队列
		if err := ts.retryManager.ScheduleRetry(task, "Task processing failed"); err != nil {
			log.Printf("Failed to schedule retry for task %s: %v", task.ID, err)
		}
	} else {
		// 标记为最终失败
		task.Status = TaskStatusFailed
		completedTime := time.Now()
		task.CompletedAt = &completedTime

		if err := ts.updateTaskWithResult(task); err != nil {
			log.Printf("Failed to update failed task: %v", err)
		}

		// 添加到死信队列
		ts.addToDeadLetterQueue(task)
	}
}

// addToDeadLetterQueue 添加到死信队列
func (ts *TaskScheduler) addToDeadLetterQueue(task *CrawlTask) {
	taskJSON, err := json.Marshal(task)
	if err != nil {
		log.Printf("Failed to marshal dead letter task: %v", err)
		return
	}

	err = ts.redisClient.RPush(ts.ctx, "dead_letter_tasks", taskJSON).Err()
	if err != nil {
		log.Printf("Failed to add task to dead letter queue: %v", err)
	}
}

// updateTaskWithResult 更新任务结果
func (ts *TaskScheduler) updateTaskWithResult(task *CrawlTask) error {
	collection := ts.db.Collection("crawl_tasks")
	filter := map[string]interface{}{"_id": task.ID}
	update := map[string]interface{}{
		"$set": task,
	}
	_, err := collection.UpdateOne(ts.ctx, filter, update)
	return err
}