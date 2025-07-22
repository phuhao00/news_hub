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
	Platforms   []string          `bson:"platforms" json:"platforms"`
	Description string            `bson:"description" json:"description"`
	Status      string            `bson:"status" json:"status"` // pending, processing, published, failed
	Error       string            `bson:"error,omitempty" json:"error,omitempty"`
	PublishedAt string            `bson:"published_at,omitempty" json:"published_at,omitempty"` // 发布后的URL
	CreatedAt   time.Time         `bson:"created_at" json:"created_at"`
}