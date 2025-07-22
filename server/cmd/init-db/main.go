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
	Username  string    `bson:"username" json:"username"`
	Platform  string    `bson:"platform" json:"platform"`
	CreatedAt time.Time `bson:"created_at" json:"created_at"`
	UpdatedAt time.Time `bson:"updated_at" json:"updated_at"`
}

func main() {
	fmt.Println("=== NewsHub 数据库初始化工具 ===")
	fmt.Println()

	// 加载环境变量
	if err := godotenv.Load("../../.env"); err != nil {
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
	fmt.Println()

	// 连接MongoDB
	client, err := connectMongoDB(mongoURI)
	if err != nil {
		log.Fatalf("连接MongoDB失败: %v", err)
	}
	defer client.Disconnect(context.Background())

	db := client.Database(dbName)

	// 初始化数据库
	if err := initializeDatabase(db); err != nil {
		log.Fatalf("初始化数据库失败: %v", err)
	}

	// 插入示例数据
	if err := insertSampleData(db); err != nil {
		log.Fatalf("插入示例数据失败: %v", err)
	}

	// 显示数据库状态
	showDatabaseStatus(db)

	fmt.Println()
	fmt.Println("=== 初始化完成 ===")
	fmt.Printf("MongoDB连接地址: %s\n", mongoURI)
	fmt.Printf("数据库名称: %s\n", dbName)
	fmt.Println()
	fmt.Println("您现在可以启动后端服务了：")
	fmt.Println("cd server && go run main.go")
}

// connectMongoDB 连接MongoDB
func connectMongoDB(uri string) (*mongo.Client, error) {
	fmt.Println("正在连接MongoDB...")

	clientOptions := options.Client().ApplyURI(uri)
	client, err := mongo.Connect(context.Background(), clientOptions)
	if err != nil {
		return nil, fmt.Errorf("连接失败: %w", err)
	}

	// 测试连接
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()

	if err := client.Ping(ctx, nil); err != nil {
		return nil, fmt.Errorf("ping失败: %w", err)
	}

	fmt.Println("✓ MongoDB连接成功")
	return client, nil
}

// initializeDatabase 初始化数据库结构
func initializeDatabase(db *mongo.Database) error {
	fmt.Println("正在初始化数据库结构...")

	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()

	// 创建集合
	collections := []string{"creators", "posts", "videos", "publish_tasks"}
	for _, collName := range collections {
		if err := db.CreateCollection(ctx, collName); err != nil {
			// 忽略集合已存在的错误
			if !mongo.IsDuplicateKeyError(err) && err.Error() != "Collection already exists." {
				fmt.Printf("警告：创建集合 %s 时出错: %v\n", collName, err)
			}
		}
	}

	// 创建索引
	if err := createIndexes(ctx, db); err != nil {
		return fmt.Errorf("创建索引失败: %w", err)
	}

	fmt.Println("✓ 数据库结构初始化完成")
	return nil
}

// createIndexes 创建索引
func createIndexes(ctx context.Context, db *mongo.Database) error {
	fmt.Println("正在创建索引...")

	// 创作者索引
	creatorsIndexes := []mongo.IndexModel{
		{
			Keys:    bson.D{{"platform", 1}, {"username", 1}},
			Options: options.Index().SetUnique(true),
		},
	}
	if _, err := db.Collection("creators").Indexes().CreateMany(ctx, creatorsIndexes); err != nil {
		return fmt.Errorf("创建creators索引失败: %w", err)
	}

	// 帖子索引
	postsIndexes := []mongo.IndexModel{
		{
			Keys:    bson.D{{"creator_id", 1}, {"platform", 1}, {"post_id", 1}},
			Options: options.Index().SetUnique(true),
		},
		{
			Keys:    bson.D{{"created_at", 1}},
			Options: options.Index().SetExpireAfterSeconds(2592000), // 30天
		},
	}
	if _, err := db.Collection("posts").Indexes().CreateMany(ctx, postsIndexes); err != nil {
		return fmt.Errorf("创建posts索引失败: %w", err)
	}

	// 视频索引
	videosIndexes := []mongo.IndexModel{
		{
			Keys:    bson.D{{"created_at", 1}},
			Options: options.Index().SetExpireAfterSeconds(2592000), // 30天
		},
	}
	if _, err := db.Collection("videos").Indexes().CreateMany(ctx, videosIndexes); err != nil {
		return fmt.Errorf("创建videos索引失败: %w", err)
	}

	// 发布任务索引
	publishTasksIndexes := []mongo.IndexModel{
		{
			Keys:    bson.D{{"video_id", 1}, {"platform", 1}},
			Options: options.Index().SetUnique(true),
		},
		{
			Keys:    bson.D{{"created_at", 1}},
			Options: options.Index().SetExpireAfterSeconds(2592000), // 30天
		},
	}
	if _, err := db.Collection("publish_tasks").Indexes().CreateMany(ctx, publishTasksIndexes); err != nil {
		return fmt.Errorf("创建publish_tasks索引失败: %w", err)
	}

	fmt.Println("✓ 索引创建完成")
	return nil
}

// insertSampleData 插入示例数据
func insertSampleData(db *mongo.Database) error {
	fmt.Println("正在插入示例数据...")

	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()

	// 检查是否已有数据
	count, err := db.Collection("creators").CountDocuments(ctx, bson.M{})
	if err != nil {
		return fmt.Errorf("检查现有数据失败: %w", err)
	}

	if count > 0 {
		fmt.Printf("发现已有 %d 个创作者，跳过示例数据插入\n", count)
		return nil
	}

	// 插入示例创作者
	sampleCreators := []interface{}{
		Creator{
			Username:  "tech_blogger",
			Platform:  "微博",
			CreatedAt: time.Now(),
			UpdatedAt: time.Now(),
		},
		Creator{
			Username:  "news_reporter",
			Platform:  "抖音",
			CreatedAt: time.Now(),
			UpdatedAt: time.Now(),
		},
		Creator{
			Username:  "lifestyle_vlogger",
			Platform:  "小红书",
			CreatedAt: time.Now(),
			UpdatedAt: time.Now(),
		},
	}

	result, err := db.Collection("creators").InsertMany(ctx, sampleCreators)
	if err != nil {
		return fmt.Errorf("插入示例数据失败: %w", err)
	}

	fmt.Printf("✓ 成功插入 %d 个示例创作者\n", len(result.InsertedIDs))
	return nil
}

// showDatabaseStatus 显示数据库状态
func showDatabaseStatus(db *mongo.Database) {
	fmt.Println()
	fmt.Println("=== 数据库状态 ===")

	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()

	// 显示集合信息
	collections := []string{"creators", "posts", "videos", "publish_tasks"}
	for _, collName := range collections {
		count, err := db.Collection(collName).CountDocuments(ctx, bson.M{})
		if err != nil {
			fmt.Printf("%s: 获取数量失败 (%v)\n", collName, err)
		} else {
			fmt.Printf("%s: %d 条记录\n", collName, count)
		}
	}

	// 显示示例创作者
	if count, _ := db.Collection("creators").CountDocuments(ctx, bson.M{}); count > 0 {
		fmt.Println("\n示例创作者:")
		cursor, err := db.Collection("creators").Find(ctx, bson.M{}, options.Find().SetLimit(3))
		if err == nil {
			defer cursor.Close(ctx)
			for cursor.Next(ctx) {
				var creator Creator
				if err := cursor.Decode(&creator); err == nil {
					fmt.Printf("  - %s (%s)\n", creator.Username, creator.Platform)
				}
			}
		}
	}
}