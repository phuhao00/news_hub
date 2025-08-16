package deduplication

import (
	"context"
	"fmt"
	"log"
	"time"

	"go.mongodb.org/mongo-driver/bson"
	"go.mongodb.org/mongo-driver/bson/primitive"
	"go.mongodb.org/mongo-driver/mongo"
	"go.mongodb.org/mongo-driver/mongo/options"
)

// DeduplicationService Go后端去重服务
type DeduplicationService struct {
	db     *mongo.Database
	enabled bool
}

// DuplicateCheckResult 重复检查结果
type DuplicateCheckResult struct {
	IsDuplicate bool   `json:"is_duplicate"`
	DuplicateType string `json:"duplicate_type,omitempty"`
	ExistingID    string `json:"existing_id,omitempty"`
	Reason        string `json:"reason,omitempty"`
}

// ContentItem 内容项
type ContentItem struct {
	ID          string    `json:"id"`
	Title       string    `json:"title"`
	Content     string    `json:"content"`
	URL         string    `json:"url"`
	Platform    string    `json:"platform"`
	Author      string    `json:"author"`
	PublishedAt *time.Time `json:"published_at,omitempty"`
	ContentHash string    `json:"content_hash"`
}

// NewDeduplicationService 创建去重服务实例
func NewDeduplicationService(db *mongo.Database) *DeduplicationService {
	return &DeduplicationService{
		db:      db,
		enabled: true,
	}
}

// SetEnabled 设置去重服务启用状态
func (ds *DeduplicationService) SetEnabled(enabled bool) {
	ds.enabled = enabled
}

// IsEnabled 检查去重服务是否启用
func (ds *DeduplicationService) IsEnabled() bool {
	return ds.enabled
}

// CheckDuplicate 检查内容是否重复
func (ds *DeduplicationService) CheckDuplicate(ctx context.Context, item *ContentItem) (*DuplicateCheckResult, error) {
	if !ds.enabled {
		return &DuplicateCheckResult{IsDuplicate: false}, nil
	}

	// 1. 检查内容哈希重复
	if item.ContentHash != "" {
		if isDup, existingID, err := ds.checkContentHashDuplicate(ctx, item.ContentHash); err != nil {
			return nil, fmt.Errorf("检查内容哈希重复失败: %w", err)
		} else if isDup {
			return &DuplicateCheckResult{
				IsDuplicate:   true,
				DuplicateType: "content_hash",
				ExistingID:    existingID,
				Reason:        "内容哈希重复",
			}, nil
		}
	}

	// 2. 检查URL重复
	if item.URL != "" {
		if isDup, existingID, err := ds.checkURLDuplicate(ctx, item.URL, item.Platform); err != nil {
			return nil, fmt.Errorf("检查URL重复失败: %w", err)
		} else if isDup {
			return &DuplicateCheckResult{
				IsDuplicate:   true,
				DuplicateType: "url",
				ExistingID:    existingID,
				Reason:        "URL重复",
			}, nil
		}
	}

	// 3. 检查标题和作者组合重复（时间窗口内）
	if item.Title != "" && item.Author != "" {
		if isDup, existingID, err := ds.checkTitleAuthorDuplicate(ctx, item.Title, item.Author, item.Platform); err != nil {
			return nil, fmt.Errorf("检查标题作者重复失败: %w", err)
		} else if isDup {
			return &DuplicateCheckResult{
				IsDuplicate:   true,
				DuplicateType: "title_author",
				ExistingID:    existingID,
				Reason:        "标题和作者组合重复",
			}, nil
		}
	}

	return &DuplicateCheckResult{IsDuplicate: false}, nil
}

// BatchCheckDuplicate 批量检查重复
func (ds *DeduplicationService) BatchCheckDuplicate(ctx context.Context, items []*ContentItem) ([]*DuplicateCheckResult, error) {
	if !ds.enabled {
		results := make([]*DuplicateCheckResult, len(items))
		for i := range results {
			results[i] = &DuplicateCheckResult{IsDuplicate: false}
		}
		return results, nil
	}

	results := make([]*DuplicateCheckResult, len(items))
	for i, item := range items {
		result, err := ds.CheckDuplicate(ctx, item)
		if err != nil {
			return nil, fmt.Errorf("批量检查第%d项失败: %w", i, err)
		}
		results[i] = result
	}

	return results, nil
}

// checkContentHashDuplicate 检查内容哈希重复
func (ds *DeduplicationService) checkContentHashDuplicate(ctx context.Context, contentHash string) (bool, string, error) {
	filter := bson.M{"content_hash": contentHash}
	var result struct {
		ID primitive.ObjectID `bson:"_id"`
	}

	err := ds.db.Collection("crawler_contents").FindOne(ctx, filter).Decode(&result)
	if err != nil {
		if err == mongo.ErrNoDocuments {
			return false, "", nil
		}
		return false, "", err
	}

	return true, result.ID.Hex(), nil
}

// checkURLDuplicate 检查URL重复
func (ds *DeduplicationService) checkURLDuplicate(ctx context.Context, url, platform string) (bool, string, error) {
	filter := bson.M{
		"url":      url,
		"platform": platform,
	}
	var result struct {
		ID primitive.ObjectID `bson:"_id"`
	}

	err := ds.db.Collection("crawler_contents").FindOne(ctx, filter).Decode(&result)
	if err != nil {
		if err == mongo.ErrNoDocuments {
			return false, "", nil
		}
		return false, "", err
	}

	return true, result.ID.Hex(), nil
}

// checkTitleAuthorDuplicate 检查标题和作者组合重复（24小时内）
func (ds *DeduplicationService) checkTitleAuthorDuplicate(ctx context.Context, title, author, platform string) (bool, string, error) {
	// 检查24小时内的重复
	timeWindow := time.Now().Add(-24 * time.Hour)
	filter := bson.M{
		"title":      title,
		"author":     author,
		"platform":   platform,
		"created_at": bson.M{"$gte": timeWindow},
	}

	var result struct {
		ID primitive.ObjectID `bson:"_id"`
	}

	err := ds.db.Collection("crawler_contents").FindOne(ctx, filter).Decode(&result)
	if err != nil {
		if err == mongo.ErrNoDocuments {
			return false, "", nil
		}
		return false, "", err
	}

	return true, result.ID.Hex(), nil
}

// GetStats 获取去重统计信息
func (ds *DeduplicationService) GetStats(ctx context.Context) (map[string]interface{}, error) {
	stats := map[string]interface{}{
		"enabled": ds.enabled,
		"service": "go_backend",
	}

	if !ds.enabled {
		return stats, nil
	}

	// 获取总内容数
	totalCount, err := ds.db.Collection("crawler_contents").CountDocuments(ctx, bson.M{})
	if err != nil {
		return nil, fmt.Errorf("获取总内容数失败: %w", err)
	}
	stats["total_contents"] = totalCount

	// 获取今日新增内容数
	today := time.Now().Truncate(24 * time.Hour)
	todayCount, err := ds.db.Collection("crawler_contents").CountDocuments(ctx, bson.M{
		"created_at": bson.M{"$gte": today},
	})
	if err != nil {
		return nil, fmt.Errorf("获取今日内容数失败: %w", err)
	}
	stats["today_contents"] = todayCount

	// 获取各平台内容分布
	pipeline := []bson.M{
		{"$group": bson.M{
			"_id":   "$platform",
			"count": bson.M{"$sum": 1},
		}},
		{"$sort": bson.M{"count": -1}},
	}

	cursor, err := ds.db.Collection("crawler_contents").Aggregate(ctx, pipeline)
	if err != nil {
		return nil, fmt.Errorf("获取平台分布失败: %w", err)
	}
	defer cursor.Close(ctx)

	var platformStats []map[string]interface{}
	if err := cursor.All(ctx, &platformStats); err != nil {
		return nil, fmt.Errorf("解析平台分布失败: %w", err)
	}
	stats["platform_distribution"] = platformStats

	return stats, nil
}

// HealthCheck 健康检查
func (ds *DeduplicationService) HealthCheck(ctx context.Context) error {
	if !ds.enabled {
		return nil
	}

	// 检查数据库连接
	if err := ds.db.Client().Ping(ctx, nil); err != nil {
		return fmt.Errorf("数据库连接失败: %w", err)
	}

	// 检查集合是否存在
	collections, err := ds.db.ListCollectionNames(ctx, bson.M{"name": "crawler_contents"})
	if err != nil {
		return fmt.Errorf("检查集合失败: %w", err)
	}
	if len(collections) == 0 {
		return fmt.Errorf("crawler_contents集合不存在")
	}

	return nil
}

// CreateIndexes 创建必要的索引
func (ds *DeduplicationService) CreateIndexes(ctx context.Context) error {
	if !ds.enabled {
		return nil
	}

	collection := ds.db.Collection("crawler_contents")

	// 创建内容哈希索引
	contentHashIndex := mongo.IndexModel{
		Keys:    bson.D{{Key: "content_hash", Value: 1}},
		Options: options.Index().SetUnique(true).SetSparse(true),
	}

	// 创建URL和平台组合索引
	urlPlatformIndex := mongo.IndexModel{
		Keys:    bson.D{{Key: "url", Value: 1}, {Key: "platform", Value: 1}},
		Options: options.Index().SetUnique(true).SetSparse(true),
	}

	// 创建标题、作者、平台和时间组合索引
	titleAuthorIndex := mongo.IndexModel{
		Keys: bson.D{
			{Key: "title", Value: 1},
			{Key: "author", Value: 1},
			{Key: "platform", Value: 1},
			{Key: "created_at", Value: -1},
		},
	}

	// 创建时间索引
	timeIndex := mongo.IndexModel{
		Keys: bson.D{{Key: "created_at", Value: -1}},
	}

	indexes := []mongo.IndexModel{
		contentHashIndex,
		urlPlatformIndex,
		titleAuthorIndex,
		timeIndex,
	}

	_, err := collection.Indexes().CreateMany(ctx, indexes)
	if err != nil {
		return fmt.Errorf("创建索引失败: %w", err)
	}

	log.Println("去重系统索引创建成功")
	return nil
}