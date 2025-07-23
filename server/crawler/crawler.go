package crawler

import (
	"context"
	"fmt"
	"log"
	"time"

	"go.mongodb.org/mongo-driver/bson"
	"go.mongodb.org/mongo-driver/bson/primitive"
	"go.mongodb.org/mongo-driver/mongo"

	"newshub/config"
	"newshub/models"
)

// CrawlerService 爬虫服务
type CrawlerService struct {
	db *mongo.Database
}

// NewCrawlerService 创建爬虫服务实例
func NewCrawlerService() *CrawlerService {
	return &CrawlerService{
		db: config.GetDB(),
	}
}

// StartScheduler 启动定时爬虫任务
func (cs *CrawlerService) StartScheduler() {
	log.Println("启动爬虫定时任务...")
	
	// 每5分钟执行一次爬虫任务
	ticker := time.NewTicker(5 * time.Minute)
	go func() {
		for {
			select {
			case <-ticker.C:
				cs.CrawlAllCreators()
			}
		}
	}()
	
	// 启动时立即执行一次
	go cs.CrawlAllCreators()
}

// CrawlAllCreators 爬取所有创作者的最新内容
func (cs *CrawlerService) CrawlAllCreators() {
	log.Println("开始爬取创作者内容...")
	
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()
	
	// 获取所有创作者
	cursor, err := cs.db.Collection("creators").Find(ctx, bson.M{})
	if err != nil {
		log.Printf("获取创作者列表失败: %v", err)
		return
	}
	defer cursor.Close(ctx)
	
	var creators []models.Creator
	if err := cursor.All(ctx, &creators); err != nil {
		log.Printf("解析创作者数据失败: %v", err)
		return
	}
	
	log.Printf("找到 %d 个创作者，开始爬取...", len(creators))
	
	// 为每个创作者爬取内容
	for _, creator := range creators {
		go cs.CrawlCreatorPosts(creator)
	}
}

// CrawlCreatorPosts 爬取指定创作者的帖子
func (cs *CrawlerService) CrawlCreatorPosts(creator models.Creator) {
	log.Printf("爬取创作者 %s (%s) 的内容...", creator.Username, creator.Platform)
	
	var posts []models.Post
	var err error
	
	// 根据平台选择不同的爬虫
	switch creator.Platform {
	case "weibo":
		posts, err = CrawlWeiboPosts(creator)
	case "douyin":
		posts, err = CrawlDouyinPosts(creator)
	case "xiaohongshu":
		posts, err = CrawlXiaohongshuPosts(creator)
	case "bilibili":
		posts, err = CrawlBilibiliPosts(creator)
	default:
		log.Printf("不支持的平台: %s", creator.Platform)
		return
	}
	
	if err != nil {
		log.Printf("爬取 %s 内容失败: %v", creator.Username, err)
		return
	}
	
	// 保存爬取到的帖子
	if len(posts) > 0 {
		cs.savePosts(posts)
		log.Printf("成功爬取 %s 的 %d 条内容", creator.Username, len(posts))
	} else {
		log.Printf("%s 暂无新内容", creator.Username)
	}
}

// savePosts 保存帖子到数据库
func (cs *CrawlerService) savePosts(posts []models.Post) {
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	
	for _, post := range posts {
		// 检查帖子是否已存在
		count, err := cs.db.Collection("posts").CountDocuments(ctx, bson.M{
			"creator_id": post.CreatorID,
			"post_id":    post.PostID,
		})
		if err != nil {
			log.Printf("检查帖子是否存在失败: %v", err)
			continue
		}
		
		// 如果帖子不存在，则插入
		if count == 0 {
			post.CreatedAt = time.Now()
			_, err := cs.db.Collection("posts").InsertOne(ctx, post)
			if err != nil {
				log.Printf("保存帖子失败: %v", err)
			}
		}
	}
}