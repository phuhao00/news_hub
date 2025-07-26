package models

import (
	"time"

	"go.mongodb.org/mongo-driver/bson/primitive"
)

// Creator 创作者模型
type Creator struct {
	ID        primitive.ObjectID `bson:"_id,omitempty" json:"id,omitempty"`
	Username  string             `bson:"username" json:"username" validate:"required"`
	Platform  string             `bson:"platform" json:"platform" validate:"required"`
	CreatedAt time.Time          `bson:"created_at" json:"created_at"`
	UpdatedAt time.Time          `bson:"updated_at" json:"updated_at"`
}

// Post 帖子模型
type Post struct {
	ID        primitive.ObjectID `bson:"_id" json:"id"`
	CreatorID primitive.ObjectID `bson:"creator_id" json:"creator_id"`
	Platform  string             `bson:"platform" json:"platform"`
	PostID    string             `bson:"post_id" json:"post_id"` // 平台原始ID
	Content   string             `bson:"content" json:"content"`
	MediaURLs []string           `bson:"media_urls" json:"media_urls"`
	CreatedAt time.Time          `bson:"created_at" json:"created_at"`
}

// Video 视频模型
type Video struct {
	ID        primitive.ObjectID   `bson:"_id" json:"id"`
	PostIDs   []primitive.ObjectID `bson:"post_ids" json:"post_ids"`
	Style     string               `bson:"style" json:"style"`
	Duration  int                  `bson:"duration" json:"duration"`
	URL       string               `bson:"url" json:"url"`
	Status    string               `bson:"status" json:"status"` // processing, completed, failed
	Error     string               `bson:"error,omitempty" json:"error,omitempty"`
	CreatedAt time.Time            `bson:"created_at" json:"created_at"`
}

// PublishTask 发布任务模型
type PublishTask struct {
	ID          primitive.ObjectID `bson:"_id" json:"id"`
	VideoID     primitive.ObjectID `bson:"video_id" json:"video_id"`
	Platforms   []string           `bson:"platforms" json:"platforms"`
	Description string             `bson:"description" json:"description"`
	Status      string             `bson:"status" json:"status"` // pending, processing, published, failed
	Error       string             `bson:"error,omitempty" json:"error,omitempty"`
	PublishedAt string             `bson:"published_at,omitempty" json:"published_at,omitempty"` // 发布后的URL
	CreatedAt   time.Time          `bson:"created_at" json:"created_at"`
}

// CrawlerTask 爬取任务模型
type CrawlerTask struct {
	ID          primitive.ObjectID `bson:"_id" json:"id"`
	Platform    string             `bson:"platform" json:"platform"`
	CreatorURL  string             `bson:"creator_url" json:"creator_url"`
	Limit       int                `bson:"limit" json:"limit"`
	Status      string             `bson:"status" json:"status"` // pending, running, completed, failed
	Error       string             `bson:"error,omitempty" json:"error,omitempty"`
	StartedAt   *time.Time         `bson:"started_at,omitempty" json:"started_at,omitempty"`
	CompletedAt *time.Time         `bson:"completed_at,omitempty" json:"completed_at,omitempty"`
	CreatedAt   time.Time          `bson:"created_at" json:"created_at"`
	UpdatedAt   time.Time          `bson:"updated_at" json:"updated_at"`
}

// CrawlerContent 爬取内容模型
type CrawlerContent struct {
	ID          primitive.ObjectID `bson:"_id" json:"id"`
	TaskID      primitive.ObjectID `bson:"task_id" json:"task_id"`
	Title       string             `bson:"title" json:"title"`
	Content     string             `bson:"content" json:"content"`
	Author      string             `bson:"author" json:"author"`
	Platform    string             `bson:"platform" json:"platform"`
	URL         string             `bson:"url" json:"url"`
	PublishedAt *time.Time         `bson:"published_at,omitempty" json:"published_at,omitempty"`
	Tags        []string           `bson:"tags" json:"tags"`
	Images      []string           `bson:"images" json:"images"`
	VideoURL    string             `bson:"video_url,omitempty" json:"video_url,omitempty"`
	CreatedAt   time.Time          `bson:"created_at" json:"created_at"`
}
