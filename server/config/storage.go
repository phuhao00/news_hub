package config

import (
	"os"
	"path/filepath"
)

const (
	VideoStoragePath = "storage/videos"
)

// InitStorage 初始化存储目录
func InitStorage() error {
	// 创建视频存储目录
	if err := os.MkdirAll(VideoStoragePath, 0755); err != nil {
		return err
	}

	return nil
}

// GetVideoPath 获取视频文件的完整路径
func GetVideoPath(videoId string) string {
	return filepath.Join(VideoStoragePath, videoId+".mp4")
}