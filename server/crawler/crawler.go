package crawler

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"sync"
	"time"

	"go.mongodb.org/mongo-driver/bson"
	"go.mongodb.org/mongo-driver/bson/primitive"
	"go.mongodb.org/mongo-driver/mongo"

	"newshub/config"
	"newshub/models"
)

const PYTHON_CRAWLER_URL = "http://localhost:8001"

// ScheduledCrawlerService 智能定时爬虫服务
type ScheduledCrawlerService struct {
	db        *mongo.Database
	isRunning bool
	stopChan  chan bool
	wg        sync.WaitGroup
}

// CrawlRequest Python爬虫请求结构
type CrawlRequest struct {
	Platform   string `json:"platform"`
	CreatorURL string `json:"creator_url"`
	Limit      int    `json:"limit"`
}

// CrawlResponse Python爬虫响应结构
type CrawlResponse struct {
	Posts []PostData `json:"posts"`
	Total int        `json:"total"`
}

// PostData 爬取到的帖子数据
type PostData struct {
	Title       string    `json:"title"`
	Content     string    `json:"content"`
	Author      string    `json:"author"`
	Platform    string    `json:"platform"`
	URL         string    `json:"url"`
	PublishedAt time.Time `json:"published_at"`
	Tags        []string  `json:"tags"`
	Images      []string  `json:"images"`
	VideoURL    string    `json:"video_url,omitempty"`
	OriginID    string    `json:"origin_id,omitempty"`
}

// NewScheduledCrawlerService 创建新的定时爬虫服务
func NewScheduledCrawlerService() *ScheduledCrawlerService {
	return &ScheduledCrawlerService{
		db:       config.GetDB(),
		stopChan: make(chan bool),
	}
}

// Start 启动定时爬虫服务
func (scs *ScheduledCrawlerService) Start() {
	if scs.isRunning {
		log.Println("定时爬虫服务已在运行中")
		return
	}

	scs.isRunning = true
	log.Println("🚀 启动智能定时爬虫服务...")

	// 立即执行一次初始爬取
	go scs.performScheduledCrawl()

	// 启动主调度循环
	scs.wg.Add(1)
	go scs.schedulerLoop()

	log.Println("✅ 定时爬虫服务启动成功")
}

// Stop 停止定时爬虫服务
func (scs *ScheduledCrawlerService) Stop() {
	if !scs.isRunning {
		return
	}

	log.Println("⏹️ 停止定时爬虫服务...")
	scs.stopChan <- true
	scs.wg.Wait()
	scs.isRunning = false
	log.Println("✅ 定时爬虫服务已停止")
}

// schedulerLoop 主调度循环
func (scs *ScheduledCrawlerService) schedulerLoop() {
	defer scs.wg.Done()

	// 每30秒检查一次是否有需要爬取的创作者
	ticker := time.NewTicker(30 * time.Second)
	defer ticker.Stop()

	for {
		select {
		case <-scs.stopChan:
			log.Println("📝 收到停止信号，退出调度循环")
			return
		case <-ticker.C:
			scs.performScheduledCrawl()
		}
	}
}

// performScheduledCrawl 执行定时爬取
func (scs *ScheduledCrawlerService) performScheduledCrawl() {
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()

	// 查找需要爬取的创作者
	creatorsToProcess, err := scs.getCreatorsReadyForCrawl(ctx)
	if err != nil {
		log.Printf("❌ 获取待爬取创作者失败: %v", err)
		return
	}

	if len(creatorsToProcess) == 0 {
		log.Println("📋 当前没有需要爬取的创作者")
		return
	}

	log.Printf("🎯 找到 %d 个创作者需要爬取", len(creatorsToProcess))

	// 并发处理每个创作者（限制并发数）
	semaphore := make(chan struct{}, 3) // 最多3个并发爬取任务
	var wg sync.WaitGroup

	for _, creator := range creatorsToProcess {
		wg.Add(1)
		go func(c models.Creator) {
			defer wg.Done()
			semaphore <- struct{}{}        // 获取信号量
			defer func() { <-semaphore }() // 释放信号量

			scs.crawlCreatorContent(c)
		}(creator)
	}

	wg.Wait()
	log.Println("✅ 本轮爬取任务完成")
}

// getCreatorsReadyForCrawl 获取准备爬取的创作者
func (scs *ScheduledCrawlerService) getCreatorsReadyForCrawl(ctx context.Context) ([]models.Creator, error) {
	now := time.Now()

	// 查询条件：启用自动爬取 且 (下次爬取时间已到 或 首次爬取)
	filter := bson.M{
		"auto_crawl_enabled": true,
		"crawl_status":       bson.M{"$ne": "crawling"}, // 不是正在爬取状态
		"$or": []bson.M{
			{"next_crawl_at": bson.M{"$lte": now}},      // 下次爬取时间已到
			{"next_crawl_at": bson.M{"$exists": false}}, // 首次爬取
		},
	}

	cursor, err := scs.db.Collection("creators").Find(ctx, filter)
	if err != nil {
		return nil, err
	}
	defer cursor.Close(ctx)

	var creators []models.Creator
	if err := cursor.All(ctx, &creators); err != nil {
		return nil, err
	}

	return creators, nil
}

// crawlCreatorContent 爬取指定创作者的内容
func (scs *ScheduledCrawlerService) crawlCreatorContent(creator models.Creator) {
	log.Printf("🕷️ 开始爬取创作者: %s (%s)", creator.DisplayName, creator.Platform)

	// 更新爬取状态
	scs.updateCreatorCrawlStatus(creator.ID, "crawling", "")

	// 准备爬取请求
	crawlReq := CrawlRequest{
		Platform:   creator.Platform,
		CreatorURL: creator.ProfileURL,
		Limit:      20, // 每次最多爬取20条
	}

	// 调用Python爬虫服务
	posts, err := scs.callPythonCrawler(crawlReq)
	if err != nil {
		log.Printf("❌ 爬取 %s 失败: %v", creator.DisplayName, err)
		scs.updateCreatorCrawlStatus(creator.ID, "failed", err.Error())
		return
	}

	// 保存爬取结果（增量更新）
	savedCount, err := scs.saveIncrementalPosts(creator.ID, posts)
	if err != nil {
		log.Printf("❌ 保存 %s 的内容失败: %v", creator.DisplayName, err)
		scs.updateCreatorCrawlStatus(creator.ID, "failed", err.Error())
		return
	}

	// 更新爬取状态和时间
	now := time.Now()
	nextCrawl := now.Add(time.Duration(creator.CrawlInterval) * time.Minute)

	scs.updateCreatorAfterCrawl(creator.ID, now, nextCrawl, savedCount)

	log.Printf("✅ 完成爬取 %s: 新增 %d 条内容", creator.DisplayName, savedCount)
}

// callPythonCrawler 调用Python爬虫服务
func (scs *ScheduledCrawlerService) callPythonCrawler(req CrawlRequest) ([]PostData, error) {
	reqBody, err := json.Marshal(req)
	if err != nil {
		return nil, fmt.Errorf("序列化请求失败: %v", err)
	}

	resp, err := http.Post(PYTHON_CRAWLER_URL+"/crawl", "application/json", bytes.NewBuffer(reqBody))
	if err != nil {
		return nil, fmt.Errorf("调用Python爬虫服务失败: %v", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(resp.Body)
		return nil, fmt.Errorf("Python爬虫服务返回错误: %d - %s", resp.StatusCode, string(body))
	}

	var crawlResp CrawlResponse
	if err := json.NewDecoder(resp.Body).Decode(&crawlResp); err != nil {
		return nil, fmt.Errorf("解析爬虫响应失败: %v", err)
	}

	return crawlResp.Posts, nil
}

// saveIncrementalPosts 增量保存帖子（避免重复）
func (scs *ScheduledCrawlerService) saveIncrementalPosts(creatorID primitive.ObjectID, posts []PostData) (int, error) {
	if len(posts) == 0 {
		return 0, nil
	}

	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()

	savedCount := 0
	collection := scs.db.Collection("posts")

	for _, post := range posts {
		// 生成内容哈希用于去重
		contentHash := scs.generateContentHash(post.Title + "|" + post.Content)

		// 检查是否已存在
		filter := bson.M{
			"$or": []bson.M{
				{"content_hash": contentHash},
				{"$and": []bson.M{
					{"creator_id": creatorID},
					{"origin_id": post.OriginID},
					{"origin_id": bson.M{"$ne": ""}},
				}},
			},
		}

		count, err := collection.CountDocuments(ctx, filter)
		if err != nil {
			log.Printf("检查重复内容失败: %v", err)
			continue
		}

		if count > 0 {
			continue // 跳过重复内容
		}

		// 创建新帖子
		newPost := models.Post{
			ID:        primitive.NewObjectID(),
			CreatorID: creatorID,
			Platform:  post.Platform,
			PostID:    post.OriginID,
			Content:   post.Title + "\n" + post.Content,
			MediaURLs: append(post.Images, post.VideoURL),
			CreatedAt: time.Now(),
		}

		_, err = collection.InsertOne(ctx, newPost)
		if err != nil {
			log.Printf("保存帖子失败: %v", err)
			continue
		}

		savedCount++
	}

	return savedCount, nil
}

// updateCreatorCrawlStatus 更新创作者爬取状态
func (scs *ScheduledCrawlerService) updateCreatorCrawlStatus(creatorID primitive.ObjectID, status, errorMsg string) {
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	update := bson.M{
		"$set": bson.M{
			"crawl_status": status,
			"updated_at":   time.Now(),
		},
	}

	if errorMsg != "" {
		update["$set"].(bson.M)["crawl_error"] = errorMsg
	} else {
		update["$unset"] = bson.M{"crawl_error": ""}
	}

	scs.db.Collection("creators").UpdateOne(ctx, bson.M{"_id": creatorID}, update)
}

// updateCreatorAfterCrawl 爬取完成后更新创作者信息
func (scs *ScheduledCrawlerService) updateCreatorAfterCrawl(creatorID primitive.ObjectID, lastCrawl, nextCrawl time.Time, savedCount int) {
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	update := bson.M{
		"$set": bson.M{
			"crawl_status":  "idle",
			"last_crawl_at": lastCrawl,
			"next_crawl_at": nextCrawl,
			"updated_at":    time.Now(),
		},
		"$unset": bson.M{"crawl_error": ""},
	}

	scs.db.Collection("creators").UpdateOne(ctx, bson.M{"_id": creatorID}, update)
}

// generateContentHash 生成内容哈希
func (scs *ScheduledCrawlerService) generateContentHash(content string) string {
	// 这里可以使用更复杂的哈希算法
	// 暂时使用简单的长度+前后字符组合
	if len(content) < 10 {
		return content
	}
	return fmt.Sprintf("%d_%s_%s", len(content), content[:5], content[len(content)-5:])
}
