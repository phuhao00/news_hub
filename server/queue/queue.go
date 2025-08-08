package queue

import (
	"context"
	"log"
	"sync"
	"time"

	"go.mongodb.org/mongo-driver/bson"
	"go.mongodb.org/mongo-driver/bson/primitive"
	"go.mongodb.org/mongo-driver/mongo"
)

// Job represents a queued unit of work
// Types: video_generate, publish_task
// Status: pending, running, completed, failed
// Result/Error kept minimal

type Job struct {
	ID        primitive.ObjectID `bson:"_id" json:"id"`
	Type      string             `bson:"type" json:"type"`
	Payload   map[string]interface{} `bson:"payload" json:"payload"`
	Status    string             `bson:"status" json:"status"`
	Result    map[string]interface{} `bson:"result,omitempty" json:"result,omitempty"`
	Error     string             `bson:"error,omitempty" json:"error,omitempty"`
	CreatedAt time.Time          `bson:"created_at" json:"created_at"`
	UpdatedAt time.Time          `bson:"updated_at" json:"updated_at"`
	StartedAt *time.Time         `bson:"started_at,omitempty" json:"started_at,omitempty"`
	EndedAt   *time.Time         `bson:"ended_at,omitempty" json:"ended_at,omitempty"`
	Attempts  int                `bson:"attempts" json:"attempts"`
	MaxRetry  int                `bson:"max_retry" json:"max_retry"`
}

type WorkerPool struct {
	db      *mongo.Database
	wg      sync.WaitGroup
	stopCh  chan struct{}
	started bool
}

func NewWorkerPool(db *mongo.Database) *WorkerPool {
	return &WorkerPool{db: db, stopCh: make(chan struct{})}
}

func (wp *WorkerPool) Start(n int) {
	if wp.started { return }
	wp.started = true
	for i := 0; i < n; i++ {
		wp.wg.Add(1)
		go wp.workerLoop(i)
	}
	log.Printf("Queue worker pool started with %d workers", n)
}

func (wp *WorkerPool) Stop() {
	if !wp.started { return }
	close(wp.stopCh)
	wp.wg.Wait()
	log.Println("Queue worker pool stopped")
}

func (wp *WorkerPool) Enqueue(jobType string, payload map[string]interface{}, maxRetry int) (primitive.ObjectID, error) {
	j := Job{ID: primitive.NewObjectID(), Type: jobType, Payload: payload, Status: "pending", CreatedAt: time.Now(), UpdatedAt: time.Now(), MaxRetry: maxRetry}
	_, err := wp.db.Collection("jobs").InsertOne(context.Background(), j)
	return j.ID, err
}

func (wp *WorkerPool) workerLoop(idx int) {
	defer wp.wg.Done()
	coll := wp.db.Collection("jobs")
	for {
		select {
		case <-wp.stopCh:
			return
		default:
		}
		ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
		var job Job
		// atomically claim a pending job
		res := coll.FindOneAndUpdate(ctx, bson.M{"status": "pending"}, bson.M{"$set": bson.M{"status": "running", "started_at": time.Now(), "updated_at": time.Now()}})
		if res.Err() != nil {
			cancel()
			time.Sleep(2 * time.Second)
			continue
		}
		if err := res.Decode(&job); err != nil { cancel(); continue }
		cancel()
		wp.processJob(&job)
	}
}

func (wp *WorkerPool) processJob(job *Job) {
	coll := wp.db.Collection("jobs")
	update := func(fields bson.M) {
		fields["updated_at"] = time.Now()
		coll.UpdateByID(context.Background(), job.ID, bson.M{"$set": fields})
	}
	switch job.Type {
	case "video_generate":
		// simulate processing
		time.Sleep(500 * time.Millisecond)
		update(bson.M{"status": "completed", "ended_at": time.Now(), "result": bson.M{"url": "/api/videos/" + job.ID.Hex()}})
	case "publish_task":
		time.Sleep(300 * time.Millisecond)
		update(bson.M{"status": "completed", "ended_at": time.Now(), "result": bson.M{"platforms": job.Payload["platforms"]}})
	default:
		update(bson.M{"status": "failed", "ended_at": time.Now(), "error": "unknown job type"})
	}
}
