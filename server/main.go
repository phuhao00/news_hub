package main

import (
	"log"
	"net/http"
	"time"

	"github.com/gin-contrib/cors"
	"github.com/gin-gonic/gin"
	"github.com/joho/godotenv"

	"newshub/config"
	"newshub/handlers"
	"newshub/middleware"
	"newshub/utils"
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

	// 初始化存储目录
	if err := config.InitStorage(); err != nil {
		log.Fatalf("初始化存储目录失败：%v\n", err)
	}

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
		AllowOrigins:     []string{"http://localhost:3000", "http://localhost:3001"},
		AllowMethods:     []string{"GET", "POST", "PUT", "DELETE", "OPTIONS"},
		AllowHeaders:     []string{"Origin", "Content-Type", "Accept"},
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
		api.POST("/videos", handlers.GenerateVideo)
		api.GET("/videos", handlers.GetVideos)
		api.GET("/videos/:id", handlers.GetVideo)

		// 发布相关接口
		api.POST("/publish", handlers.CreatePublishTask)
		api.GET("/publish", handlers.GetPublishTasks)

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
