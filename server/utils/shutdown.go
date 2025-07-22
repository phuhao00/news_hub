package utils

import (
	"context"
	"log"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"
)

// GracefulShutdown 优雅关闭服务器
func GracefulShutdown(srv *http.Server) {
	// 创建系统信号接收器
	quit := make(chan os.Signal, 1)
	// 监听 SIGINT 和 SIGTERM 信号
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)

	// 等待信号
	<-quit
	log.Println("正在关闭服务器...")

	// 创建一个带超时的上下文
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()

	// 尝试优雅关闭服务器
	if err := srv.Shutdown(ctx); err != nil {
		log.Printf("服务器关闭出错：%v\n", err)
	}

	// 等待上下文完成
	<-ctx.Done()
	log.Println("服务器已关闭")
}