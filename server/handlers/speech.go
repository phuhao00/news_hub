package handlers

import (
	"bytes"
	"encoding/base64"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"strings"
	"time"

	"github.com/gin-gonic/gin"
)

// TTSRequest 请求体
type TTSRequest struct {
	Text     string  `json:"text" binding:"required"`
	Voice    string  `json:"voice,omitempty"`
	Format   string  `json:"format,omitempty"` // mp3/wav
	Speed    float64 `json:"speed,omitempty"`
	Pitch    float64 `json:"pitch,omitempty"`
	Clean    bool    `json:"clean,omitempty"`    // 是否清洗文本
	Provider string  `json:"provider,omitempty"` // minimax|azure
}

// TTS 文本转语音（Minimax）
func TTS(c *gin.Context) {
	var req TTSRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
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

	provider := strings.ToLower(defaultIfEmpty(req.Provider, "minimax"))
	switch provider {
	case "azure":
		azureKey := os.Getenv("AZURE_SPEECH_KEY")
		region := os.Getenv("AZURE_SPEECH_REGION")
		if azureKey == "" || region == "" {
			c.JSON(http.StatusInternalServerError, gin.H{"error": "未配置azure_speech_key或azure_speech_region"})
			return
		}
		if err := callAzureTTS(c, text, req, azureKey, region); err != nil {
			c.JSON(http.StatusBadGateway, gin.H{"error": err.Error()})
		}
		return
	case "openai":
		key := os.Getenv("OPENAI_API_KEY")
		if key == "" {
			c.JSON(http.StatusInternalServerError, gin.H{"error": "未配置openai_api_key"})
			return
		}
		if err := callOpenAITTS(c, text, req, key); err != nil {
			c.JSON(http.StatusBadGateway, gin.H{"error": err.Error()})
		}
		return
	case "google":
		key := os.Getenv("GOOGLE_TTS_API_KEY")
		if key == "" {
			c.JSON(http.StatusInternalServerError, gin.H{"error": "未配置google_tts_api_key"})
			return
		}
		if err := callGoogleTTS(c, text, req, key); err != nil {
			c.JSON(http.StatusBadGateway, gin.H{"error": err.Error()})
		}
		return
	case "qwen", "dashscope", "tongyi":
		key := os.Getenv("DASHSCOPE_API_KEY")
		if key == "" {
			c.JSON(http.StatusInternalServerError, gin.H{"error": "未配置dashscope_api_key"})
			return
		}
		if err := callDashscopeTTS(c, text, req, key); err != nil {
			c.JSON(http.StatusBadGateway, gin.H{"error": err.Error()})
		}
		return
	case "kimi", "grok", "tiangong":
		// 通用直通模式：需设置 {PROVIDER}_TTS_URL 与 {PROVIDER}_API_KEY（可选）
		up := strings.ToUpper(provider)
		url := os.Getenv(up + "_TTS_URL")
		if url == "" {
			c.JSON(http.StatusInternalServerError, gin.H{"error": up + "_TTS_URL 未配置"})
			return
		}
		key := os.Getenv(up + "_API_KEY")
		if err := callGenericTTS(c, text, req, url, key); err != nil {
			c.JSON(http.StatusBadGateway, gin.H{"error": err.Error()})
		}
		return
	default: // minimax
		apiKey := os.Getenv("MINIMAX_API_KEY")
		if apiKey == "" {
			c.JSON(http.StatusInternalServerError, gin.H{"error": "未配置minimax_api_key"})
			return
		}
		if err := callMinimaxTTS(c, text, req, apiKey); err != nil {
			c.JSON(http.StatusBadGateway, gin.H{"error": err.Error()})
		}
		return
	}
}

func callMinimaxTTS(c *gin.Context, text string, req TTSRequest, apiKey string) error {
	endpoint := os.Getenv("MINIMAX_TTS_URL")
	if endpoint == "" {
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
		return err
	}
	defer resp.Body.Close()
	ct := resp.Header.Get("Content-Type")
	if resp.StatusCode == 200 && (strings.HasPrefix(ct, "audio/") || strings.Contains(ct, "octet-stream")) {
		c.Header("Content-Type", ct)
		io.Copy(c.Writer, resp.Body)
		return nil
	}
	b, _ := io.ReadAll(resp.Body)
	if resp.StatusCode >= 300 {
		return fmt.Errorf("TTS错误(%d): %s", resp.StatusCode, string(b))
	}
	var data map[string]interface{}
	if err := json.Unmarshal(b, &data); err != nil {
		return fmt.Errorf("解析失败: %w", err)
	}
	if audioB64, ok := findString(data, "audio"); ok {
		buf, err := base64.StdEncoding.DecodeString(audioB64)
		if err != nil {
			return err
		}
		c.Header("Content-Type", "audio/mpeg")
		c.Writer.Write(buf)
		return nil
	}
	if url, ok := findString(data, "url"); ok {
		c.JSON(http.StatusOK, gin.H{"url": url})
		return nil
	}
	c.JSON(http.StatusBadGateway, gin.H{"error": "未在响应中找到音频或链接", "resp": data})
	return nil
}

func callAzureTTS(c *gin.Context, text string, req TTSRequest, key, region string) error {
	voice := defaultIfEmpty(req.Voice, os.Getenv("AZURE_SPEECH_VOICE"))
	if voice == "" {
		voice = "zh-CN-XiaoxiaoNeural"
	}
	format := defaultIfEmpty(strings.ToLower(req.Format), "mp3")
	output := "audio-16khz-32kbitrate-mono-mp3"
	if format == "wav" {
		output = "riff-16khz-16bit-mono-pcm"
	}
	ssml := fmt.Sprintf(`<?xml version="1.0"?><speak version="1.0" xml:lang="zh-CN"><voice name="%s">%s</voice></speak>`, voice, text)
	url := "https://" + region + ".tts.speech.microsoft.com/cognitiveservices/v1"
	reqHTTP, _ := http.NewRequest("POST", url, strings.NewReader(ssml))
	reqHTTP.Header.Set("Ocp-Apim-Subscription-Key", key)
	reqHTTP.Header.Set("Content-Type", "application/ssml+xml")
	reqHTTP.Header.Set("X-Microsoft-OutputFormat", output)
	reqHTTP.Header.Set("User-Agent", "newshub-tts")
	client := &http.Client{Timeout: 60 * time.Second}
	resp, err := client.Do(reqHTTP)
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	if resp.StatusCode >= 300 {
		b, _ := io.ReadAll(resp.Body)
		return fmt.Errorf("azure tts错误(%d): %s", resp.StatusCode, string(b))
	}
	c.Header("Content-Type", resp.Header.Get("Content-Type"))
	io.Copy(c.Writer, resp.Body)
	return nil
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
	repl := []string{
		// 中文
		"ICP备", "违法不良信息", "营业执照", "隐私政策", "用户协议", "举报", "温馨提示", "登录", "注册", "版权", "站点地图",
		// 英文
		"ICP", "beian", "record", "privacy policy", "terms of service", "terms of use", "user agreement", "report", "complaint", "disclaimer", "cookie policy", "cookies", "sign in", "log in", "login", "register", "sign up", "subscribe", "newsletter", "sitemap", "navigation", "menu", "footer", "header", "back to top", "copyright", "all rights reserved", "©", "™", "®",
	}
	lower := strings.ToLower(s)
	for _, r := range repl {
		lower = strings.ReplaceAll(lower, r, "")
	}
	// 移除 URL
	tokens := strings.Fields(lower)
	filtered := make([]string, 0, len(tokens))
	for _, t := range tokens {
		if strings.HasPrefix(t, "http://") || strings.HasPrefix(t, "https://") {
			continue
		}
		filtered = append(filtered, t)
	}
	out := strings.Join(filtered, " ")
	out = strings.TrimSpace(out)
	if len(out) > 2000 {
		out = out[:2000] + "..."
	}
	return out
}

func callOpenAITTS(c *gin.Context, text string, req TTSRequest, key string) error {
	url := os.Getenv("OPENAI_TTS_URL")
	if url == "" {
		url = "https://api.openai.com/v1/audio/speech"
	}
	model := os.Getenv("OPENAI_TTS_MODEL")
	if model == "" {
		model = "tts-1"
	}
	voice := defaultIfEmpty(req.Voice, os.Getenv("OPENAI_TTS_VOICE"))
	if voice == "" {
		voice = "alloy"
	}
	payload := map[string]interface{}{
		"model":  model,
		"voice":  voice,
		"input":  text,
		"format": defaultIfEmpty(strings.ToLower(req.Format), "mp3"),
	}
	b, _ := json.Marshal(payload)
	r, _ := http.NewRequest("POST", url, bytes.NewReader(b))
	r.Header.Set("Authorization", "Bearer "+key)
	r.Header.Set("Content-Type", "application/json")
	resp, err := (&http.Client{Timeout: 60 * time.Second}).Do(r)
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	if resp.StatusCode >= 300 {
		bb, _ := io.ReadAll(resp.Body)
		return fmt.Errorf("openai tts错误(%d): %s", resp.StatusCode, string(bb))
	}
	c.Header("Content-Type", resp.Header.Get("Content-Type"))
	io.Copy(c.Writer, resp.Body)
	return nil
}

func callGoogleTTS(c *gin.Context, text string, req TTSRequest, key string) error {
	url := os.Getenv("GOOGLE_TTS_URL")
	if url == "" {
		url = "https://texttospeech.googleapis.com/v1/text:synthesize?key=" + key
	}
	payload := map[string]interface{}{
		"input": map[string]interface{}{"text": text},
		"voice": map[string]interface{}{
			"languageCode": defaultIfEmpty(os.Getenv("GOOGLE_TTS_LANG"), "zh-CN"),
			"name":         defaultIfEmpty(req.Voice, os.Getenv("GOOGLE_TTS_VOICE")),
		},
		"audioConfig": map[string]interface{}{
			"audioEncoding": strings.ToUpper(defaultIfEmpty(req.Format, "mp3")),
		},
	}
	b, _ := json.Marshal(payload)
	r, _ := http.NewRequest("POST", url, bytes.NewReader(b))
	r.Header.Set("Content-Type", "application/json")
	resp, err := (&http.Client{Timeout: 60 * time.Second}).Do(r)
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	bb, _ := io.ReadAll(resp.Body)
	if resp.StatusCode >= 300 {
		return fmt.Errorf("google tts错误(%d): %s", resp.StatusCode, string(bb))
	}
	var data map[string]interface{}
	if err := json.Unmarshal(bb, &data); err != nil {
		return err
	}
	if ac, ok := data["audioContent"].(string); ok && ac != "" {
		buf, err := base64.StdEncoding.DecodeString(ac)
		if err != nil {
			return err
		}
		c.Header("Content-Type", "audio/mpeg")
		c.Writer.Write(buf)
		return nil
	}
	return fmt.Errorf("google tts响应中无audioContent")
}

func callDashscopeTTS(c *gin.Context, text string, req TTSRequest, key string) error {
	url := os.Getenv("DASHSCOPE_TTS_URL")
	if url == "" {
		url = "https://dashscope.aliyuncs.com/api/v1/services/tts_v2/text-to-speech"
	}
	voice := defaultIfEmpty(req.Voice, os.Getenv("DASHSCOPE_TTS_VOICE"))
	if voice == "" {
		voice = "longxia"
	}
	payload := map[string]interface{}{
		"input": map[string]string{"text": text},
		"parameters": map[string]string{
			"voice":  voice,
			"format": defaultIfEmpty(strings.ToLower(req.Format), "mp3"),
		},
	}
	b, _ := json.Marshal(payload)
	r, _ := http.NewRequest("POST", url, bytes.NewReader(b))
	r.Header.Set("Authorization", "Bearer "+key)
	r.Header.Set("Content-Type", "application/json")
	resp, err := (&http.Client{Timeout: 60 * time.Second}).Do(r)
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	ct := resp.Header.Get("Content-Type")
	if resp.StatusCode == 200 && (strings.HasPrefix(ct, "audio/") || strings.Contains(ct, "octet-stream")) {
		c.Header("Content-Type", ct)
		io.Copy(c.Writer, resp.Body)
		return nil
	}
	bb, _ := io.ReadAll(resp.Body)
	if resp.StatusCode >= 300 {
		return fmt.Errorf("dashscope tts错误(%d): %s", resp.StatusCode, string(bb))
	}
	var data map[string]interface{}
	if err := json.Unmarshal(bb, &data); err != nil {
		return err
	}
	if audioB64, ok := findString(data, "audio"); ok {
		buf, err := base64.StdEncoding.DecodeString(audioB64)
		if err != nil {
			return err
		}
		c.Header("Content-Type", "audio/mpeg")
		c.Writer.Write(buf)
		return nil
	}
	if url, ok := findString(data, "url"); ok {
		c.JSON(http.StatusOK, gin.H{"url": url})
		return nil
	}
	return fmt.Errorf("dashscope tts响应无音频")
}

func callGenericTTS(c *gin.Context, text string, req TTSRequest, url, apiKey string) error {
	payload := map[string]interface{}{
		"text":   text,
		"voice":  req.Voice,
		"format": defaultIfEmpty(strings.ToLower(req.Format), "mp3"),
	}
	b, _ := json.Marshal(payload)
	r, _ := http.NewRequest("POST", url, bytes.NewReader(b))
	if apiKey != "" {
		r.Header.Set("Authorization", "Bearer "+apiKey)
	}
	r.Header.Set("Content-Type", "application/json")
	resp, err := (&http.Client{Timeout: 60 * time.Second}).Do(r)
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	ct := resp.Header.Get("Content-Type")
	if resp.StatusCode == 200 && (strings.HasPrefix(ct, "audio/") || strings.Contains(ct, "octet-stream")) {
		c.Header("Content-Type", ct)
		io.Copy(c.Writer, resp.Body)
		return nil
	}
	bb, _ := io.ReadAll(resp.Body)
	if resp.StatusCode >= 300 {
		return fmt.Errorf("generic tts错误(%d): %s", resp.StatusCode, string(bb))
	}
	var data map[string]interface{}
	if err := json.Unmarshal(bb, &data); err != nil {
		return err
	}
	if audioB64, ok := findString(data, "audio"); ok {
		buf, err := base64.StdEncoding.DecodeString(audioB64)
		if err != nil {
			return err
		}
		c.Header("Content-Type", "audio/mpeg")
		c.Writer.Write(buf)
		return nil
	}
	if url2, ok := findString(data, "url"); ok {
		c.JSON(http.StatusOK, gin.H{"url": url2})
		return nil
	}
	return fmt.Errorf("generic tts响应无音频")
}
