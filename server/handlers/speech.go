package handlers

import (
	"bytes"
	"encoding/base64"
	"encoding/json"
	"io"
	"net/http"
	"os"
	"strings"
	"time"

	"github.com/gin-gonic/gin"
)

// TTSRequest 请求体
type TTSRequest struct {
	Text   string  `json:"text" binding:"required"`
	Voice  string  `json:"voice,omitempty"`
	Format string  `json:"format,omitempty"` // mp3/wav
	Speed  float64 `json:"speed,omitempty"`
	Pitch  float64 `json:"pitch,omitempty"`
	Clean  bool    `json:"clean,omitempty"` // 是否清洗文本
}

// TTS 文本转语音（Minimax）
func TTS(c *gin.Context) {
	var req TTSRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	apiKey := os.Getenv("MINIMAX_API_KEY")
	if apiKey == "" {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "未配置MINIMAX_API_KEY"})
		return
	}

	text := req.Text
	if req.Clean {
		text = sanitizeForSpeech(text)
	}
	if strings.TrimSpace(text) == "" {
		c.JSON(http.StatusBadRequest, gin.H{"error": "文本内容为空"})
		return
	}

	endpoint := os.Getenv("MINIMAX_TTS_URL")
	if endpoint == "" {
		// 参考官方 QuickStart，可按需调整实际地址
		endpoint = "https://api.minimax.chat/v1/text_to_speech"
	}

	payload := map[string]interface{}{
		"text":   text,
		"voice":  defaultIfEmpty(req.Voice, os.Getenv("MINIMAX_TTS_VOICE")),
		"format": defaultIfEmpty(strings.ToLower(req.Format), "mp3"),
	}
	if req.Speed != 0 {
		payload["speed"] = req.Speed
	}
	if req.Pitch != 0 {
		payload["pitch"] = req.Pitch
	}

	body, _ := json.Marshal(payload)
	httpReq, _ := http.NewRequest("POST", endpoint, bytes.NewReader(body))
	httpReq.Header.Set("Authorization", "Bearer "+apiKey)
	httpReq.Header.Set("Content-Type", "application/json")
	client := &http.Client{Timeout: 60 * time.Second}

	resp, err := client.Do(httpReq)
	if err != nil {
		c.JSON(http.StatusBadGateway, gin.H{"error": "调用TTS失败: " + err.Error()})
		return
	}
	defer resp.Body.Close()

	// 如果直接返回音频流
	ct := resp.Header.Get("Content-Type")
	if resp.StatusCode == 200 && (strings.HasPrefix(ct, "audio/") || strings.Contains(ct, "octet-stream")) {
		c.Header("Content-Type", ct)
		io.Copy(c.Writer, resp.Body)
		return
	}

	// 否则解析JSON返回（可能包含base64或url）
	b, _ := io.ReadAll(resp.Body)
	if resp.StatusCode >= 300 {
		c.JSON(http.StatusBadGateway, gin.H{"error": "TTS返回错误", "status": resp.StatusCode, "resp": string(b)})
		return
	}
	var data map[string]interface{}
	if err := json.Unmarshal(b, &data); err != nil {
		c.JSON(http.StatusBadGateway, gin.H{"error": "解析TTS响应失败", "resp": string(b)})
		return
	}

	// 1) audio(base64)
	if audioB64, ok := findString(data, "audio"); ok {
		buf, err := base64.StdEncoding.DecodeString(audioB64)
		if err != nil {
			c.JSON(http.StatusBadGateway, gin.H{"error": "音频解码失败"})
			return
		}
		c.Header("Content-Type", "audio/mpeg")
		c.Writer.Write(buf)
		return
	}
	// 2) url
	if url, ok := findString(data, "url"); ok {
		c.JSON(http.StatusOK, gin.H{"url": url})
		return
	}

	c.JSON(http.StatusBadGateway, gin.H{"error": "未在响应中找到音频或链接", "resp": data})
}

func defaultIfEmpty(v, d string) string {
	if strings.TrimSpace(v) == "" {
		return d
	}
	return v
}

func findString(m map[string]interface{}, key string) (string, bool) {
	if v, ok := m[key].(string); ok && v != "" {
		return v, true
	}
	if d, ok := m["data"].(map[string]interface{}); ok {
		if v, ok2 := d[key].(string); ok2 && v != "" {
			return v, true
		}
	}
	return "", false
}

// sanitizeForSpeech 去掉备案/版权/导航噪声
func sanitizeForSpeech(s string) string {
	repl := []string{"ICP备", "违法不良信息", "营业执照", "隐私政策", "用户协议", "举报", "温馨提示", "登录", "注册"}
	for _, r := range repl {
		s = strings.ReplaceAll(s, r, "")
	}
	s = strings.Join(strings.Fields(s), " ")
	return strings.TrimSpace(s)
}
