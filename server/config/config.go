package config

import (
	"encoding/json"
	"log"
	"os"
	"path/filepath"
)

// ServerConfig 服务器配置
type ServerConfig struct {
	Port string `json:"port"`
	Host string `json:"host"`
}

// ServiceConfig 服务配置
type ServiceConfig struct {
	Backend  ServerConfig `json:"backend"`
	Crawler  ServerConfig `json:"crawler"`
	Frontend ServerConfig `json:"frontend"`
}

// DatabaseConfig 数据库配置
type DatabaseConfig struct {
	MongoDB struct {
		URI      string `json:"uri"`
		Database string `json:"database"`
	} `json:"mongodb"`
}

// AppConfig 应用配置
type AppConfig struct {
	Services ServiceConfig  `json:"services"`
	Database DatabaseConfig `json:"database"`
}

var Config *AppConfig

// LoadConfig 加载配置文件
func LoadConfig() error {
	// 查找配置文件 - 先查找项目根目录
	configPath := filepath.Join("..", "config.json")
	if _, err := os.Stat(configPath); os.IsNotExist(err) {
		// 如果根目录没有，查找当前目录
		configPath = "config.json"
		if _, err := os.Stat(configPath); os.IsNotExist(err) {
			log.Printf("警告：配置文件未找到，使用默认配置")
			Config = getDefaultConfig()
			return nil
		}
	}

	file, err := os.Open(configPath)
	if err != nil {
		log.Printf("警告：无法打开配置文件 %s，使用默认配置: %v", configPath, err)
		Config = getDefaultConfig()
		return nil
	}
	defer file.Close()

	decoder := json.NewDecoder(file)
	Config = &AppConfig{}
	if err := decoder.Decode(Config); err != nil {
		log.Printf("警告：配置文件格式错误，使用默认配置: %v", err)
		Config = getDefaultConfig()
		return nil
	}

	log.Printf("配置文件加载成功: %s", configPath)
	return nil
}

// getDefaultConfig 获取默认配置
func getDefaultConfig() *AppConfig {
	return &AppConfig{
		Services: ServiceConfig{
			Backend: ServerConfig{
				Port: "8080",
				Host: "0.0.0.0",
			},
			Crawler: ServerConfig{
				Port: "8001",
				Host: "0.0.0.0",
			},
			Frontend: ServerConfig{
				Port: "3000",
				Host: "0.0.0.0",
			},
		},
		Database: DatabaseConfig{
			MongoDB: struct {
				URI      string `json:"uri"`
				Database string `json:"database"`
			}{
				URI:      "mongodb://localhost:27017",
				Database: "newshub",
			},
		},
	}
}

// GetServerPort 获取服务器端口
func GetServerPort() string {
	if Config == nil {
		LoadConfig()
	}
	return Config.Services.Backend.Port
}

// GetServerHost 获取服务器主机
func GetServerHost() string {
	if Config == nil {
		LoadConfig()
	}
	return Config.Services.Backend.Host
}

// GetMongodbURI 获取MongoDB URI
func GetMongodbURI() string {
	if Config == nil {
		LoadConfig()
	}
	return Config.Database.MongoDB.URI
}

// GetMongodbDatabase 获取MongoDB数据库名
func GetMongodbDatabase() string {
	if Config == nil {
		LoadConfig()
	}
	return Config.Database.MongoDB.Database
}
