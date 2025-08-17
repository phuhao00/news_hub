package handlers

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"path/filepath"
	"strings"
	"time"

	"github.com/gin-gonic/gin"
	"go.mongodb.org/mongo-driver/bson"
	"go.mongodb.org/mongo-driver/bson/primitive"

	"newshub/config"
	"newshub/models"
)

// GenerateVideo 生成视频（调用智谱 CogVideoX 异步任务）
func GenerateVideo(c *gin.Context) {
	var req struct {
		PostIDs      []string `json:"postIds"`
		Style        string   `json:"style"`
		Duration     int      `json:"duration"`
		Prompt       string   `json:"prompt"`
		EnableSpeech bool     `json:"enableSpeech"`
		Provider     string   `json:"provider"`
	}
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "无效的请求参数"})
		return
	}

	// 简单拼装提示词 + 清洗
	if req.Prompt == "" {
		req.Prompt = fmt.Sprintf("基于%d条社媒内容生成%s风格、时长约%d秒的视频。", len(req.PostIDs), req.Style, req.Duration)
	}
	cleanedPrompt := sanitizePrompt(req.Prompt)

	// 调用第三方创建视频任务（多端点回退）
	provider := strings.ToLower(strings.TrimSpace(req.Provider))
	if provider == "" {
		provider = "zhipu"
	}

	// 选择 API Key
	var apiKey string
	switch provider {
	case "minimax":
		apiKey = os.Getenv("MINIMAX_API_KEY")
	case "runway":
		apiKey = os.Getenv("RUNWAY_API_KEY")
	case "openai":
		apiKey = os.Getenv("OPENAI_API_KEY")
	case "kling":
		apiKey = os.Getenv("KLING_API_KEY")
	case "generic":
		apiKey = os.Getenv("GENERIC_VIDEO_API_KEY")
	default: // zhipu
		apiKey = os.Getenv("ZHIPU_API_KEY")
	}
	if apiKey == "" {
		switch provider {
		case "minimax":
			c.JSON(http.StatusInternalServerError, gin.H{"error": "未配置MINIMAX_API_KEY"})
			return
		case "runway":
			c.JSON(http.StatusInternalServerError, gin.H{"error": "未配置RUNWAY_API_KEY"})
			return
		case "openai":
			c.JSON(http.StatusInternalServerError, gin.H{"error": "未配置OPENAI_API_KEY"})
			return
		case "kling":
			c.JSON(http.StatusInternalServerError, gin.H{"error": "未配置KLING_API_KEY"})
			return
		case "generic":
			// 可选，很多自建网关可能不需要 key
		default:
			c.JSON(http.StatusInternalServerError, gin.H{"error": "未配置ZHIPU_API_KEY"})
			return
		}
	}

	var endpoints []string
	switch provider {
	case "minimax":
		if ep := os.Getenv("MINIMAX_VIDEO_URL"); strings.TrimSpace(ep) != "" {
			endpoints = []string{ep}
		}
	case "runway":
		if ep := os.Getenv("RUNWAY_VIDEO_URL"); strings.TrimSpace(ep) != "" {
			endpoints = []string{ep}
		}
	case "openai":
		if ep := os.Getenv("OPENAI_VIDEO_URL"); strings.TrimSpace(ep) != "" {
			endpoints = []string{ep}
		}
	case "kling":
		if ep := os.Getenv("KLING_VIDEO_URL"); strings.TrimSpace(ep) != "" {
			endpoints = []string{ep}
		}
	case "generic":
		if ep := os.Getenv("GENERIC_VIDEO_URL"); strings.TrimSpace(ep) != "" {
			endpoints = []string{ep}
		}
	default: // zhipu
		if custom := os.Getenv("ZHIPU_VIDEO_URL"); strings.TrimSpace(custom) != "" {
			endpoints = append(endpoints, custom)
		}
		endpoints = append(endpoints,
			"https://open.bigmodel.cn/api/paas/v4/videos/generations",
			"https://open.bigmodel.cn/api/v4/videos/generations",
			"https://open.bigmodel.cn/api/v1/videos/generations",
		)
	}
	// 过滤空端点
	{
		var filtered []string
		for _, ep := range endpoints {
			if strings.TrimSpace(ep) != "" {
				filtered = append(filtered, ep)
			}
		}
		endpoints = filtered
	}
	if len(endpoints) == 0 {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "未配置可用的视频生成端点"})
		return
	}

	var taskID string
	var lastRespCode int
	var lastRespBody string
	for _, ep := range endpoints {
		payload := map[string]interface{}{
			"model":  "cogvideox",
			"prompt": cleanedPrompt,
			"input":  map[string]interface{}{"prompt": cleanedPrompt},
		}
		body, _ := json.Marshal(payload)
		reqHTTP, _ := http.NewRequest("POST", ep, bytes.NewReader(body))
		reqHTTP.Header.Set("Authorization", "Bearer "+apiKey)
		reqHTTP.Header.Set("Content-Type", "application/json")
		client := &http.Client{Timeout: 30 * time.Second}
		resp, err := client.Do(reqHTTP)
		if err != nil {
			lastRespBody = err.Error()
			continue
		}
		respBytes, _ := io.ReadAll(resp.Body)
		_ = resp.Body.Close()
		lastRespCode = resp.StatusCode
		lastRespBody = string(respBytes)
		if resp.StatusCode >= 300 {
			continue
		}
		var raw map[string]interface{}
		_ = json.Unmarshal(respBytes, &raw)
		if v, ok := raw["id"].(string); ok && v != "" {
			taskID = v
		}
		if taskID == "" {
			if v, ok := raw["task_id"].(string); ok && v != "" {
				taskID = v
			}
		}
		if taskID == "" {
			if data, ok := raw["data"].(map[string]interface{}); ok {
				if v, ok2 := data["id"].(string); ok2 && v != "" {
					taskID = v
				}
				if taskID == "" {
					if v, ok2 := data["task_id"].(string); ok2 && v != "" {
						taskID = v
					}
				}
			}
		}
		if taskID != "" {
			break
		}
	}

	if taskID == "" {
		// 返回部分响应用于排障
		snippet := lastRespBody
		if len(snippet) > 300 {
			snippet = snippet[:300] + "..."
		}
		c.JSON(http.StatusBadGateway, gin.H{"error": "未获取到任务ID", "code": lastRespCode, "resp": snippet})
		return
	}

	// 保存视频记录
	video := models.Video{
		ID:        primitive.NewObjectID(),
		PostIDs:   []primitive.ObjectID{},
		Style:     req.Style,
		Duration:  req.Duration,
		Status:    "processing",
		TaskID:    taskID,
		Provider:  provider,
		Prompt:    cleanedPrompt,
		CreatedAt: time.Now(),
	}
	for _, pid := range req.PostIDs {
		if oid, err := primitive.ObjectIDFromHex(pid); err == nil {
			video.PostIDs = append(video.PostIDs, oid)
		}
	}
	// 如果开启语音合成，将清洗后的文案暂存，后续可由前端/发布流转发给TTS
	if req.EnableSpeech {
		video.SpeechText = cleanedPrompt
	}

	coll := config.GetDB().Collection("videos")
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	if _, err := coll.InsertOne(ctx, video); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "保存视频记录失败"})
		return
	}

	c.JSON(http.StatusOK, video)
}

// CheckVideoStatus 查询并刷新第三方任务状态
func CheckVideoStatus(c *gin.Context) {
	videoID := c.Param("id")
	objID, err := primitive.ObjectIDFromHex(videoID)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "无效的视频ID"})
		return
	}

	coll := config.GetDB().Collection("videos")
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()

	var video models.Video
	if err := coll.FindOne(ctx, bson.M{"_id": objID}).Decode(&video); err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "视频不存在"})
		return
	}
	if video.Status == "completed" && video.URL != "" {
		c.JSON(http.StatusOK, video)
		return
	}

	// 根据 provider 选择状态查询端点与 API Key
	var statusKey string
	switch strings.ToLower(strings.TrimSpace(video.Provider)) {
	case "minimax":
		statusKey = os.Getenv("MINIMAX_API_KEY")
	case "runway":
		statusKey = os.Getenv("RUNWAY_API_KEY")
	case "openai":
		statusKey = os.Getenv("OPENAI_API_KEY")
	case "kling":
		statusKey = os.Getenv("KLING_API_KEY")
	case "generic":
		statusKey = os.Getenv("GENERIC_VIDEO_API_KEY")
	default: // zhipu
		statusKey = os.Getenv("ZHIPU_API_KEY")
	}
	if statusKey == "" {
		switch strings.ToLower(strings.TrimSpace(video.Provider)) {
		case "minimax":
			c.JSON(http.StatusInternalServerError, gin.H{"error": "未配置MINIMAX_API_KEY"})
			return
		case "runway":
			c.JSON(http.StatusInternalServerError, gin.H{"error": "未配置RUNWAY_API_KEY"})
			return
		case "openai":
			c.JSON(http.StatusInternalServerError, gin.H{"error": "未配置OPENAI_API_KEY"})
			return
		case "kling":
			c.JSON(http.StatusInternalServerError, gin.H{"error": "未配置KLING_API_KEY"})
			return
		default:
			c.JSON(http.StatusInternalServerError, gin.H{"error": "未配置ZHIPU_API_KEY"})
			return
		}
	}

	// 调用第三方查询结果（多端点回退）
	var statusEPs []string
	switch strings.ToLower(strings.TrimSpace(video.Provider)) {
	case "minimax":
		if ep := os.Getenv("MINIMAX_VIDEO_STATUS_URL"); strings.TrimSpace(ep) != "" {
			statusEPs = append(statusEPs, fmt.Sprintf(ep, video.TaskID))
		}
	case "runway":
		if ep := os.Getenv("RUNWAY_VIDEO_STATUS_URL"); strings.TrimSpace(ep) != "" {
			statusEPs = append(statusEPs, fmt.Sprintf(ep, video.TaskID))
		}
	case "openai":
		if ep := os.Getenv("OPENAI_VIDEO_STATUS_URL"); strings.TrimSpace(ep) != "" {
			statusEPs = append(statusEPs, fmt.Sprintf(ep, video.TaskID))
		}
	case "kling":
		if ep := os.Getenv("KLING_VIDEO_STATUS_URL"); strings.TrimSpace(ep) != "" {
			statusEPs = append(statusEPs, fmt.Sprintf(ep, video.TaskID))
		}
	case "generic":
		if custom := os.Getenv("GENERIC_VIDEO_STATUS_URL"); strings.TrimSpace(custom) != "" {
			statusEPs = append(statusEPs, fmt.Sprintf(custom, video.TaskID))
		}
		statusEPs = append(statusEPs,
			fmt.Sprintf("https://open.bigmodel.cn/api/paas/v4/videos/tasks/%s", video.TaskID),
			fmt.Sprintf("https://open.bigmodel.cn/api/v4/videos/tasks/%s", video.TaskID),
			fmt.Sprintf("https://open.bigmodel.cn/api/v1/videos/tasks/%s", video.TaskID),
		)
	}
	{
		var filtered []string
		for _, ep := range statusEPs {
			if strings.TrimSpace(ep) != "" {
				filtered = append(filtered, ep)
			}
		}
		statusEPs = filtered
	}

	var resultRaw map[string]interface{}
	var respBody string
	for _, ep := range statusEPs {
		reqHTTP, _ := http.NewRequest("GET", ep, nil)
		reqHTTP.Header.Set("Authorization", "Bearer "+statusKey)
		client := &http.Client{Timeout: 15 * time.Second}
		resp, err := client.Do(reqHTTP)
		if err != nil {
			continue
		}
		b, _ := io.ReadAll(resp.Body)
		_ = resp.Body.Close()
		if resp.StatusCode >= 300 {
			respBody = string(b)
			continue
		}
		_ = json.Unmarshal(b, &resultRaw)
		if len(resultRaw) > 0 {
			respBody = string(b)
			break
		}
	}

	// 解析状态（兼容不同字段）
	taskStatus := ""
	for _, k := range []string{"task_status", "status", "state"} {
		if v, ok := resultRaw[k].(string); ok && v != "" {
			taskStatus = v
			break
		}
	}
	if taskStatus == "" {
		if data, ok := resultRaw["data"].(map[string]interface{}); ok {
			for _, k := range []string{"task_status", "status", "state"} {
				if v, ok2 := data[k].(string); ok2 && v != "" {
					taskStatus = v
					break
				}
			}
		}
	}

	var videoURL string
	// 多种位置与字段兼容提取 URL
	if u, ok := resultRaw["url"].(string); ok && u != "" {
		videoURL = u
	}
	if videoURL == "" {
		if m, ok := resultRaw["result"].(map[string]interface{}); ok {
			if u, ok2 := m["url"].(string); ok2 {
				videoURL = u
			}
		}
	}
	if videoURL == "" {
		if arr, ok := resultRaw["video_result"].([]interface{}); ok && len(arr) > 0 {
			if m, ok2 := arr[0].(map[string]interface{}); ok2 {
				if u, ok3 := m["url"].(string); ok3 {
					videoURL = u
				}
			}
		}
	}
	if videoURL == "" {
		if data, ok := resultRaw["data"].(map[string]interface{}); ok {
			if u, ok2 := data["url"].(string); ok2 {
				videoURL = u
			}
			if videoURL == "" {
				if m, ok2 := data["result"].(map[string]interface{}); ok2 {
					if u, ok3 := m["url"].(string); ok3 {
						videoURL = u
					}
				}
			}
			if videoURL == "" {
				if arr, ok2 := data["video_result"].([]interface{}); ok2 && len(arr) > 0 {
					if m, ok3 := arr[0].(map[string]interface{}); ok3 {
						if u, ok4 := m["url"].(string); ok4 {
							videoURL = u
						}
					}
				}
			}
		}
	}

	update := bson.M{}
	if taskStatus == "SUCCESS" && videoURL != "" {
		update["status"] = "completed"
		update["url"] = videoURL
	} else if taskStatus == "FAIL" {
		update["status"] = "failed"
		if msg, ok := resultRaw["error_msg"].(string); ok {
			update["error"] = msg
		} else {
			update["error"] = respBody
		}
	}
	if len(update) > 0 {
		if _, err := coll.UpdateOne(ctx, bson.M{"_id": objID}, bson.M{"$set": update}); err == nil {
			_ = coll.FindOne(ctx, bson.M{"_id": objID}).Decode(&video)
		}
	}

	c.JSON(http.StatusOK, video)
}

// GetVideos 获取视频列表
func GetVideos(c *gin.Context) {
	coll := config.GetDB().Collection("videos")

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	// 查询所有视频
	cursor, err := coll.Find(ctx, bson.M{})
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "获取视频列表失败"})
		return
	}
	defer cursor.Close(ctx)

	// 解码结果
	var videos []models.Video
	if err := cursor.All(ctx, &videos); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "解析视频数据失败"})
		return
	}

	// Ensure we always return an array, never null
	if videos == nil {
		videos = []models.Video{}
	}

	c.JSON(http.StatusOK, videos)
}

// GetVideo 获取单个视频
func GetVideo(c *gin.Context) {
	videoID := c.Param("id")

	// 检查视频文件是否存在
	videoPath := config.GetVideoPath(videoID)
	if _, err := os.Stat(videoPath); os.IsNotExist(err) {
		c.JSON(http.StatusNotFound, gin.H{"error": "视频文件不存在"})
		return
	}

	// 获取文件信息
	fileInfo, err := os.Stat(videoPath)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "获取视频文件信息失败"})
		return
	}

	// 打开文件
	file, err := os.Open(videoPath)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "打开视频文件失败"})
		return
	}
	defer file.Close()

	// 设置响应头
	c.Header("Content-Type", "video/mp4")
	c.Header("Content-Length", fmt.Sprintf("%d", fileInfo.Size()))
	c.Header("Content-Disposition", "inline; filename=\""+filepath.Base(videoPath)+"\"")

	// 发送文件内容
	if _, err := io.Copy(c.Writer, file); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "发送视频文件失败"})
		return
	}
}

// UpdateVideo 更新视频信息
func UpdateVideo(c *gin.Context) {
	videoID := c.Param("id")

	// 验证视频ID格式
	objID, err := primitive.ObjectIDFromHex(videoID)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "无效的视频ID"})
		return
	}

	// 获取更新数据
	var updateData bson.M
	if err := c.ShouldBindJSON(&updateData); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "无效的请求参数"})
		return
	}

	// 添加更新时间
	updateData["updated_at"] = time.Now()

	// 更新数据库
	coll := config.GetDB().Collection("videos")
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	filter := bson.M{"_id": objID}
	update := bson.M{"$set": updateData}

	result, err := coll.UpdateOne(ctx, filter, update)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "更新视频失败"})
		return
	}

	if result.MatchedCount == 0 {
		c.JSON(http.StatusNotFound, gin.H{"error": "视频不存在"})
		return
	}

	c.JSON(http.StatusOK, gin.H{"message": "视频更新成功"})
}

// sanitizePrompt 清洗生成文案，去掉站点备案/版权、UI提示等噪声
func sanitizePrompt(s string) string {
	// 中文与英文常见噪声
	repl := []string{
		// 中文
		"沪ICP备", "违法不良信息举报", "营业执照", "ICP备", "隐私政策", "用户协议", "通知我", "温馨提示", "浏览器", "版权", "站点地图",
		// 英文
		"ICP", "beian", "record", "privacy policy", "terms of service", "terms of use", "user agreement", "report", "complaint", "disclaimer", "cookie policy", "cookies", "sign in", "log in", "login", "register", "sign up", "subscribe", "newsletter", "sitemap", "navigation", "menu", "footer", "header", "back to top", "copyright", "all rights reserved", "©", "™", "®",
	}
	lower := strings.ToLower(s)
	for _, r := range repl {
		lower = strings.ReplaceAll(lower, r, "")
	}
	// 移除 URL
	// 注意：Go 标准库无内置正则 here，使用简单切割避免引入额外依赖
	// 这里保持简单：按空白拆分后滤掉以 http/https 开头的词
	var filtered []string
	for _, token := range strings.Fields(lower) {
		if strings.HasPrefix(token, "http://") || strings.HasPrefix(token, "https://") {
			continue
		}
		filtered = append(filtered, token)
	}
	out := strings.Join(filtered, " ")
	out = strings.TrimSpace(out)
	if len(out) > 2000 {
		out = out[:2000] + "..."
	}
	return out
}
