package config

import (
	"context"
	"log"
	"os"
	"time"

	"go.mongodb.org/mongo-driver/mongo"
	"go.mongodb.org/mongo-driver/mongo/options"
)

var DB *mongo.Database

func ConnectDB() error {
	// 直接使用newshub-mongodb容器的端口
	mongoURI := "mongodb://localhost:27015"
	
	log.Printf("尝试连接MongoDB: %s", mongoURI)
	clientOptions := options.Client().ApplyURI(mongoURI)
	client, err := mongo.Connect(context.Background(), clientOptions)
	if err != nil {
		log.Printf("MongoDB连接失败: %v", err)
		return err
	}

	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()

	err = client.Ping(ctx, nil)
	if err != nil {
		return err
	}

	dbName := os.Getenv("DB_NAME")
	if dbName == "" {
		dbName = "newshub"
	}

	DB = client.Database(dbName)
	log.Println("Connected to MongoDB!")
	return nil
}

// GetDB 获取数据库实例
func GetDB() *mongo.Database {
	return DB
}