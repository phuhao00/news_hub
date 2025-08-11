package main

import (
	"log"
	"net/http"
	"time"

	"github.com/gin-contrib/cors"
	"github.com/gin-gonic/gin"
	"github.com/joho/godotenv"

	"context"
	"newshub/config"
	"newshub/crawler"
	"newshub/handlers"
	"newshub/middleware"
	"newshub/utils"

	"go.mongodb.org/mongo-driver/bson"
	"go.mongodb.org/mongo-driver/bson/primitive"
)

func main() {
	// 加载环境变量
	if err := godotenv.Load(); err != nil {
		log.Printf("警告：未找到.env文件：%v\n", err)
	}

	// 连接数据库
	if err := config.ConnectDB(); err != nil {
		log.Fatalf("连接数据库失败：%v\n", err)
	}

	// 如无数据则写入默认创作者种子数据
	if err := seedCreatorsIfEmpty(); err != nil {
		log.Printf("种子数据写入失败：%v\n", err)
	}

	// 初始化存储目录
	if err := config.InitStorage(); err != nil {
		log.Fatalf("初始化存储目录失败：%v\n", err)
	}

	// 启动定时爬虫服务
	crawlerService := crawler.NewScheduledCrawlerService()
	crawlerService.Start()
	log.Println("✅ 定时爬虫服务已启动")

	// 注册自定义验证器
	middleware.RegisterCustomValidators()

	// Python爬虫服务在独立进程中运行
	log.Println("Python爬虫服务运行在 http://localhost:8001")

	// 创建Gin实例
	r := gin.New() // 使用gin.New()替代gin.Default()以自定义中间件

	// 使用自定义日志中间件
	r.Use(middleware.Logger())
	// 使用Recovery中间件
	r.Use(gin.Recovery())
	// 使用限速中间件：每分钟60个请求
	r.Use(middleware.RateLimit(60, time.Minute))
	// 使用监控中间件
	r.Use(middleware.Monitor())

	// 配置CORS
	r.Use(cors.New(cors.Config{
		AllowOrigins:     []string{"http://localhost:3000", "http://localhost:3001", "http://localhost:3002"},
		AllowMethods:     []string{"GET", "POST", "PUT", "DELETE", "OPTIONS"},
		AllowHeaders:     []string{"Origin", "Content-Type", "Accept", "Authorization"},
		AllowCredentials: true,
	}))

	// 健康检查路由
	r.GET("/health", handlers.HealthCheck)
	// 系统指标路由
	r.GET("/metrics", middleware.GetMetrics())

	// API路由
	api := r.Group("/api")
	{
		// 创作者相关接口
		api.POST("/creators", handlers.CreateCreator)
		api.GET("/creators", handlers.GetCreators)
		api.DELETE("/creators/:id", handlers.DeleteCreator)

		// 视频相关接口
		api.POST("/videos/generate", handlers.GenerateVideo)
		api.GET("/videos", handlers.GetVideos)
		api.GET("/videos/:id", handlers.GetVideo)
		api.PUT("/videos/:id", handlers.UpdateVideo)

		// 发布相关接口
		api.POST("/publish", handlers.CreatePublishTask)
		api.GET("/publish/tasks", handlers.GetPublishTasks)
		api.GET("/publish/:id", handlers.GetPublishTask)
		api.PUT("/publish/:id", handlers.UpdatePublishTask)

		// 帖子相关接口
		api.GET("/posts", handlers.GetPosts)
		api.GET("/posts/:id", handlers.GetPost)
		api.DELETE("/posts/:id", handlers.DeletePost)

		// 爬虫服务代理接口 (转发到Python服务)
		api.POST("/crawler/trigger", handlers.ProxyCrawlerTrigger)
		api.GET("/crawler/status", handlers.ProxyCrawlerStatus)
		api.GET("/crawler/platforms", handlers.GetCrawlerPlatforms)

		// 爬取任务管理接口
		api.POST("/crawler/tasks", handlers.CreateCrawlerTask)
		api.GET("/crawler/tasks", handlers.GetCrawlerTasks)
		api.GET("/crawler/tasks/:id", handlers.GetCrawlerTask)
		api.PUT("/crawler/tasks/:id/status", handlers.UpdateCrawlerTaskStatus)

		// 爬取内容接口
		api.GET("/crawler/contents", handlers.GetCrawlerContents)
	}

	// 加载配置文件
	if err := config.LoadConfig(); err != nil {
		log.Printf("警告：加载配置文件失败：%v", err)
	}

	// 获取端口配置
	port := config.GetServerPort()
	host := config.GetServerHost()

	log.Printf("后端服务配置: host=%s, port=%s", host, port)

	// 创建HTTP服务器
	addr := host + ":" + port
	srv := &http.Server{
		Addr:    addr,
		Handler: r,
	}

	// 在goroutine中启动服务器
	go func() {
		log.Printf("服务器正在监听端口 %s\n", port)
		if err := srv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			log.Fatalf("启动服务器失败：%v\n", err)
		}
	}()

	// 等待中断信号以优雅地关闭服务器
	utils.GracefulShutdown(srv)
}

// seedCreatorsIfEmpty 如果 creators 集合为空，写入示例创作者数据
func seedCreatorsIfEmpty() error {
	db := config.GetDB()
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	count, err := db.Collection("creators").CountDocuments(ctx, bson.M{})
	if err != nil {
		return err
	}
	if count > 0 {
		return nil
	}
	now := time.Now()
	creators := []interface{}{
		bson.M{
			"_id":                primitive.NewObjectID(),
			"username":           "tech_blogger",
			"platform":           "weibo",
			"profile_url":        "https://weibo.com/u/123456",
			"display_name":       "科技博主",
			"auto_crawl_enabled": true,
			"crawl_interval":     60,
			"crawl_status":       "idle",
			"created_at":         now,
			"updated_at":         now,
		},
		bson.M{
			"_id":                primitive.NewObjectID(),
			"username":           "news_reporter",
			"platform":           "douyin",
			"profile_url":        "https://www.douyin.com/user/abcdef",
			"display_name":       "新闻记者",
			"auto_crawl_enabled": true,
			"crawl_interval":     90,
			"crawl_status":       "idle",
			"created_at":         now,
			"updated_at":         now,
		},
		bson.M{
			"_id":                primitive.NewObjectID(),
			"username":           "lifestyle_vlogger",
			"platform":           "xiaohongshu",
			"profile_url":        "https://www.xiaohongshu.com/user/xyz",
			"display_name":       "生活博主",
			"auto_crawl_enabled": true,
			"crawl_interval":     120,
			"crawl_status":       "idle",
			"created_at":         now,
			"updated_at":         now,
		},
	}
	_, err = db.Collection("creators").InsertMany(ctx, creators)
	return err
}
