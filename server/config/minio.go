package config

import (
	"context"
	"log"
	"os"

	"github.com/minio/minio-go/v7"
	"github.com/minio/minio-go/v7/pkg/credentials"
)

// MinIOConfig MinIO配置
type MinIOConfig struct {
	Endpoint        string
	AccessKeyID     string
	SecretAccessKey string
	UseSSL          bool
	BucketName      string
}

// MinIOClient MinIO客户端实例
var MinIOClient *minio.Client
var MinIOConf MinIOConfig

// InitMinIO 初始化MinIO客户端
func InitMinIO() error {
	// 从环境变量读取配置
	MinIOConf = MinIOConfig{
		Endpoint:        getEnv("MINIO_ENDPOINT", "localhost:9000"),
		AccessKeyID:     getEnv("MINIO_ACCESS_KEY", "minioadmin"),
		SecretAccessKey: getEnv("MINIO_SECRET_KEY", "minioadmin123"),
		UseSSL:          getEnv("MINIO_USE_SSL", "false") == "true",
		BucketName:      getEnv("MINIO_BUCKET_NAME", "newshub-media"),
	}

	// 初始化MinIO客户端
	client, err := minio.New(MinIOConf.Endpoint, &minio.Options{
		Creds:  credentials.NewStaticV4(MinIOConf.AccessKeyID, MinIOConf.SecretAccessKey, ""),
		Secure: MinIOConf.UseSSL,
	})
	if err != nil {
		return err
	}

	MinIOClient = client

	// 检查bucket是否存在，如果不存在则创建
	ctx := context.Background()
	exists, err := client.BucketExists(ctx, MinIOConf.BucketName)
	if err != nil {
		log.Printf("检查bucket存在性失败: %v", err)
		return err
	}

	if !exists {
		err = client.MakeBucket(ctx, MinIOConf.BucketName, minio.MakeBucketOptions{})
		if err != nil {
			log.Printf("创建bucket失败: %v", err)
			return err
		}
		log.Printf("成功创建bucket: %s", MinIOConf.BucketName)
	}

	log.Printf("MinIO客户端初始化成功，连接到: %s", MinIOConf.Endpoint)
	return nil
}

// getEnv 获取环境变量，如果不存在则返回默认值
func getEnv(key, defaultValue string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return defaultValue
}

// GetMinIOClient 获取MinIO客户端实例
func GetMinIOClient() *minio.Client {
	return MinIOClient
}

// GetMinIOConfig 获取MinIO配置
func GetMinIOConfig() MinIOConfig {
	return MinIOConf
}