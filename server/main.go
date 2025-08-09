package main

import (
	"log"
	"net/http"
	"time"

	"github.com/gin-contrib/cors"
	"github.com/gin-gonic/gin"
	"github.com/joho/godotenv"

	"newshub/config"
	"newshub/crawler"
	"newshub/handlers"
	"newshub/middleware"
	"newshub/utils"
)

func main() {
	if err := godotenv.Load(); err != nil { log.Printf("warn: no .env: %v", err) }
	if err := config.ConnectDB(); err != nil { log.Fatalf("db connect failed: %v", err) }
	if err := config.InitStorage(); err != nil { log.Fatalf("storage init failed: %v", err) }
	crawlerService := crawler.NewScheduledCrawlerService(); crawlerService.Start(); log.Println("scheduled crawler started")
	middleware.RegisterCustomValidators()

	r := gin.New()
	r.Use(middleware.Logger())
	r.Use(gin.Recovery())
	r.Use(middleware.RateLimit(60, time.Minute))
	r.Use(middleware.Monitor())
	r.Use(cors.New(cors.Config{AllowOrigins: []string{"http://localhost:3000", "http://localhost:3001", "http://localhost:3002"}, AllowMethods: []string{"GET","POST","PUT","DELETE","OPTIONS"}, AllowHeaders: []string{"Origin","Content-Type","Accept","Authorization"}, AllowCredentials: true }))

	r.GET("/health", handlers.HealthCheck)
	r.GET("/metrics", middleware.GetMetrics())

	// Auth
	auth := r.Group("/auth")
	auth.POST("/register", handlers.Register)
	auth.POST("/login", handlers.Login)

	api := r.Group("/api")
	// public (read) endpoints
	api.GET("/creators", handlers.GetCreators)
	api.GET("/posts", handlers.GetPosts)
	api.GET("/posts/:id", handlers.GetPost)
	api.GET("/videos", handlers.GetVideos)
	api.GET("/videos/:id", handlers.GetVideo)
	api.GET("/publish/tasks", handlers.GetPublishTasks)
	api.GET("/crawler/tasks", handlers.GetCrawlerTasks)
	api.GET("/crawler/tasks/:id", handlers.GetCrawlerTask)
	api.GET("/crawler/contents", handlers.GetCrawlerContents)
	api.GET("/crawler/platforms", handlers.GetCrawlerPlatforms)
	api.GET("/analytics/overview", handlers.AnalyticsOverview)
	api.GET("/jobs", handlers.ListJobs)

	// protected endpoints
	protected := api.Group("")
	protected.Use(middleware.AuthMiddleware())
	protected.POST("/creators", middleware.RequirePermissions("creators:write"), handlers.CreateCreator)
	protected.DELETE("/creators/:id", middleware.RequirePermissions("creators:write"), handlers.DeleteCreator)
	protected.POST("/videos/generate", middleware.RequirePermissions("videos:generate"), handlers.GenerateVideo)
	protected.POST("/publish", middleware.RequirePermissions("publish:write"), handlers.CreatePublishTask)
	protected.POST("/crawler/trigger", middleware.RequirePermissions("crawler:write"), handlers.ProxyCrawlerTrigger)
	protected.GET("/crawler/status", middleware.RequirePermissions("crawler:read"), handlers.ProxyCrawlerStatus)
	protected.PUT("/crawler/tasks/:id/status", middleware.RequirePermissions("crawler:write"), handlers.UpdateCrawlerTaskStatus)

	if err := config.LoadConfig(); err != nil { log.Printf("warn: load config: %v", err) }
	port := config.GetServerPort(); host := config.GetServerHost(); addr := host + ":" + port
	log.Printf("listening on %s", addr)
	srv := &http.Server{Addr: addr, Handler: r}
	go func(){ if err := srv.ListenAndServe(); err != nil && err != http.ErrServerClosed { log.Fatalf("server error: %v", err) } }()
	utils.GracefulShutdown(srv)
}
