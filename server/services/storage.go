package services

import (
	"context"
	"crypto/md5"
	"fmt"
	"io"
	"mime"
	"mime/multipart"
	"net/http"
	"path/filepath"
	"strings"
	"time"

	"bytes"

	"newshub/config"

	"github.com/minio/minio-go/v7"
)

// StorageService 存储服务
type StorageService struct {
	client     *minio.Client
	bucketName string
}

// FileInfo 文件信息
type FileInfo struct {
	FileName    string    `json:"file_name"`
	FileSize    int64     `json:"file_size"`
	ContentType string    `json:"content_type"`
	URL         string    `json:"url"`
	Hash        string    `json:"hash"`
	UploadedAt  time.Time `json:"uploaded_at"`
}

// NewStorageService 创建存储服务实例
func NewStorageService() *StorageService {
	return &StorageService{
		client:     config.GetMinIOClient(),
		bucketName: config.GetMinIOConfig().BucketName,
	}
}

// UploadFile 上传文件
func (s *StorageService) UploadFile(ctx context.Context, file multipart.File, header *multipart.FileHeader, folder string) (*FileInfo, error) {
	// 生成文件哈希
	hash, err := s.calculateFileHash(file)
	if err != nil {
		return nil, fmt.Errorf("计算文件哈希失败: %v", err)
	}

	// 重置文件指针
	file.Seek(0, 0)

	// 生成文件名
	fileExt := filepath.Ext(header.Filename)
	fileName := fmt.Sprintf("%s/%s_%d%s", folder, hash, time.Now().Unix(), fileExt)

	// 检查文件是否已存在（去重）
	existingFile, err := s.GetFileByHash(ctx, hash)
	if err == nil && existingFile != nil {
		return existingFile, nil // 返回已存在的文件
	}

	// 上传文件到MinIO
	info, err := s.client.PutObject(ctx, s.bucketName, fileName, file, header.Size, minio.PutObjectOptions{
		ContentType: header.Header.Get("Content-Type"),
	})
	if err != nil {
		return nil, fmt.Errorf("上传文件失败: %v", err)
	}

	// 生成访问URL
	url := s.generateFileURL(fileName)

	return &FileInfo{
		FileName:    fileName,
		FileSize:    info.Size,
		ContentType: header.Header.Get("Content-Type"),
		URL:         url,
		Hash:        hash,
		UploadedAt:  time.Now(),
	}, nil
}

// UploadFromURL 从URL下载并上传文件
func (s *StorageService) UploadFromURL(ctx context.Context, url, folder string) (*FileInfo, error) {
	// 下载远程文件
	req, err := http.NewRequestWithContext(ctx, "GET", url, nil)
	if err != nil {
		return nil, fmt.Errorf("创建下载请求失败: %v", err)
	}
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("下载失败: %v", err)
	}
	defer resp.Body.Close()
	if resp.StatusCode >= 300 {
		return nil, fmt.Errorf("下载失败，状态码: %d", resp.StatusCode)
	}

	// 读取到内存（也可改为流式到临时文件，这里简化）
	data, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("读取远程内容失败: %v", err)
	}

	// 计算哈希
	sum := md5.Sum(data)
	hash := fmt.Sprintf("%x", sum[:])

	// 文件名与内容类型
	if folder == "" {
		folder = "assets"
	}
	ext := filepath.Ext(url)
	if ext == "" {
		ext = ".bin"
	}
	objectName := fmt.Sprintf("%s/%s_%d%s", folder, hash, time.Now().Unix(), ext)
	contentType := mime.TypeByExtension(ext)
	if contentType == "" {
		contentType = resp.Header.Get("Content-Type")
	}
	if contentType == "" {
		contentType = "application/octet-stream"
	}

	// 上传到 MinIO
	reader := bytes.NewReader(data)
	info, err := s.client.PutObject(ctx, s.bucketName, objectName, reader, int64(len(data)), minio.PutObjectOptions{ContentType: contentType})
	if err != nil {
		return nil, fmt.Errorf("上传到 MinIO 失败: %v", err)
	}

	return &FileInfo{
		FileName:    objectName,
		FileSize:    info.Size,
		ContentType: contentType,
		URL:         s.generateFileURL(objectName),
		Hash:        hash,
		UploadedAt:  time.Now(),
	}, nil
}

// DeleteFile 删除文件
func (s *StorageService) DeleteFile(ctx context.Context, fileName string) error {
	err := s.client.RemoveObject(ctx, s.bucketName, fileName, minio.RemoveObjectOptions{})
	if err != nil {
		return fmt.Errorf("删除文件失败: %v", err)
	}
	return nil
}

// GetFileByHash 根据哈希查找文件
func (s *StorageService) GetFileByHash(ctx context.Context, hash string) (*FileInfo, error) {
	// 遍历bucket中的对象，查找匹配的哈希
	objectCh := s.client.ListObjects(ctx, s.bucketName, minio.ListObjectsOptions{
		Recursive: true,
	})

	for object := range objectCh {
		if object.Err != nil {
			continue
		}

		// 从文件名中提取哈希
		if strings.Contains(object.Key, hash) {
			url := s.generateFileURL(object.Key)
			return &FileInfo{
				FileName:    object.Key,
				FileSize:    object.Size,
				ContentType: "", // 需要额外查询
				URL:         url,
				Hash:        hash,
				UploadedAt:  object.LastModified,
			}, nil
		}
	}

	return nil, fmt.Errorf("文件未找到")
}

// ListFiles 列出文件
func (s *StorageService) ListFiles(ctx context.Context, folder string, limit int) ([]*FileInfo, error) {
	var files []*FileInfo
	count := 0

	objectCh := s.client.ListObjects(ctx, s.bucketName, minio.ListObjectsOptions{
		Prefix:    folder,
		Recursive: true,
	})

	for object := range objectCh {
		if object.Err != nil {
			continue
		}

		if count >= limit {
			break
		}

		url := s.generateFileURL(object.Key)
		files = append(files, &FileInfo{
			FileName:    object.Key,
			FileSize:    object.Size,
			ContentType: "",
			URL:         url,
			Hash:        "", // 需要从文件名解析
			UploadedAt:  object.LastModified,
		})
		count++
	}

	return files, nil
}

// calculateFileHash 计算文件MD5哈希
func (s *StorageService) calculateFileHash(file multipart.File) (string, error) {
	hash := md5.New()
	_, err := io.Copy(hash, file)
	if err != nil {
		return "", err
	}
	return fmt.Sprintf("%x", hash.Sum(nil)), nil
}

// generateFileURL 生成文件访问URL
func (s *StorageService) generateFileURL(fileName string) string {
	minioConfig := config.GetMinIOConfig()
	protocol := "http"
	if minioConfig.UseSSL {
		protocol = "https"
	}
	return fmt.Sprintf("%s://%s/%s/%s", protocol, minioConfig.Endpoint, minioConfig.BucketName, fileName)
}

// GetFileURL 获取文件的预签名URL（用于临时访问）
func (s *StorageService) GetFileURL(ctx context.Context, fileName string, expiry time.Duration) (string, error) {
	url, err := s.client.PresignedGetObject(ctx, s.bucketName, fileName, expiry, nil)
	if err != nil {
		return "", fmt.Errorf("生成预签名URL失败: %v", err)
	}
	return url.String(), nil
}
