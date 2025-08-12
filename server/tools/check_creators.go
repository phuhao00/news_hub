package main

import (
	"context"
	"fmt"
	"log"
	"os"
	"time"

	"github.com/joho/godotenv"
	"go.mongodb.org/mongo-driver/bson"
	"go.mongodb.org/mongo-driver/mongo"
	"go.mongodb.org/mongo-driver/mongo/options"
)

// Creator 创作者模型
type Creator struct {
	ID               string     `bson:"_id,omitempty" json:"id"`
	DisplayName      string     `bson:"display_name" json:"display_name"`
	Platform         string     `bson:"platform" json:"platform"`
	CreatorURL       string     `bson:"creator_url" json:"creator_url"`
	AutoCrawlEnabled bool       `bson:"auto_crawl_enabled" json:"auto_crawl_enabled"`
	CrawlStatus      string     `bson:"crawl_status" json:"crawl_status"`
	NextCrawlAt      *time.Time `bson:"next_crawl_at,omitempty" json:"next_crawl_at,omitempty"`
	CreatedAt        time.Time  `bson:"created_at" json:"created_at"`
	UpdatedAt        time.Time  `bson:"updated_at" json:"updated_at"`
}

func main() {
	fmt.Println("=== 检查数据库中的创作者记录 ===")

	// 加载环境变量
	if err := godotenv.Load(".env"); err != nil {
		log.Printf("警告：未找到.env文件，使用默认配置\n")
	}

	// 获取MongoDB连接配置
	mongoURI := os.Getenv("MONGODB_URI")
	if mongoURI == "" {
		mongoURI = "mongodb://localhost:27017"
	}

	dbName := os.Getenv("DB_NAME")
	if dbName == "" {
		dbName = "newshub"
	}

	fmt.Printf("连接到MongoDB: %s\n", mongoURI)
	fmt.Printf("数据库名称: %s\n", dbName)

	// 连接MongoDB
	clientOptions := options.Client().ApplyURI(mongoURI)
	client, err := mongo.Connect(context.Background(), clientOptions)
	if err != nil {
		log.Fatalf("连接MongoDB失败: %v", err)
	}
	defer client.Disconnect(context.Background())

	// 测试连接
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()

	if err := client.Ping(ctx, nil); err != nil {
		log.Fatalf("ping失败: %v", err)
	}

	db := client.Database(dbName)

	// 查询所有创作者
	fmt.Println("\n=== 所有创作者记录 ===")
	cursor, err := db.Collection("creators").Find(ctx, bson.M{})
	if err != nil {
		log.Fatalf("查询创作者失败: %v", err)
	}
	defer cursor.Close(ctx)

	var creators []Creator
	if err = cursor.All(ctx, &creators); err != nil {
		log.Fatalf("解析创作者数据失败: %v", err)
	}

	fmt.Printf("总共找到 %d 个创作者:\n", len(creators))
	for i, creator := range creators {
		fmt.Printf("%d. ID: %s\n", i+1, creator.ID)
		fmt.Printf("   显示名称: %s\n", creator.DisplayName)
		fmt.Printf("   平台: %s\n", creator.Platform)
		fmt.Printf("   创作者URL: %s\n", creator.CreatorURL)
		fmt.Printf("   自动爬取: %t\n", creator.AutoCrawlEnabled)
		fmt.Printf("   爬取状态: %s\n", creator.CrawlStatus)
		if creator.NextCrawlAt != nil {
			fmt.Printf("   下次爬取时间: %s\n", creator.NextCrawlAt.Format("2006-01-02 15:04:05"))
		}
		fmt.Printf("   创建时间: %s\n", creator.CreatedAt.Format("2006-01-02 15:04:05"))
		fmt.Printf("   更新时间: %s\n", creator.UpdatedAt.Format("2006-01-02 15:04:05"))
		fmt.Println("   ---")
	}

	// 特别检查包含example.com的记录
	fmt.Println("\n=== 检查包含'example.com'的记录 ===")
	filter := bson.M{"creator_url": bson.M{"$regex": "example.com", "$options": "i"}}
	cursor2, err := db.Collection("creators").Find(ctx, filter)
	if err != nil {
		log.Fatalf("查询包含example.com的创作者失败: %v", err)
	}
	defer cursor2.Close(ctx)

	var fakeCreators []Creator
	if err = cursor2.All(ctx, &fakeCreators); err != nil {
		log.Fatalf("解析假创作者数据失败: %v", err)
	}

	if len(fakeCreators) > 0 {
		fmt.Printf("⚠️  发现 %d 个包含'example.com'的假记录:\n", len(fakeCreators))
		for i, creator := range fakeCreators {
			fmt.Printf("%d. ID: %s, URL: %s, 平台: %s\n", i+1, creator.ID, creator.CreatorURL, creator.Platform)
		}

		// 删除这些假记录
		fmt.Println("\n正在删除这些假记录...")
		deleteResult, err := db.Collection("creators").DeleteMany(ctx, filter)
		if err != nil {
			log.Fatalf("删除假记录失败: %v", err)
		}
		fmt.Printf("✅ 成功删除 %d 个假记录\n", deleteResult.DeletedCount)
	} else {
		fmt.Println("✅ 没有发现包含'example.com'的记录")
	}

	fmt.Println("\n=== 检查完成 ===")
}
