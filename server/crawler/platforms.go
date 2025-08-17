package crawler

import (
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"regexp"
	"strings"
	"time"

	"go.mongodb.org/mongo-driver/bson/primitive"

	"newshub/models"
)

// SearchEngine 搜索引擎配置
type SearchEngine struct {
	Name     string
	BaseURL  string
	Selector string
}

// PlatformConfig 平台配置
type PlatformConfig struct {
	Name          string
	SearchEngines []SearchEngine
	Keywords      []string
}

// 平台配置
var platformConfigs = map[string]PlatformConfig{
	"weibo": {
		Name: "weibo",
		SearchEngines: []SearchEngine{
			{Name: "baidu", BaseURL: "https://www.baidu.com/s?wd=%s+site:weibo.com", Selector: ".result.c-container"},
			{Name: "sogou", BaseURL: "https://www.sogou.com/web?query=%s+微博", Selector: ".result"},
			{Name: "bing", BaseURL: "https://cn.bing.com/search?q=%s+weibo.com", Selector: ".b_algo"},
		},
		Keywords: []string{"微博", "weibo", "社交媒体"},
	},
	"douyin": {
		Name: "douyin",
		SearchEngines: []SearchEngine{
			{Name: "baidu", BaseURL: "https://www.baidu.com/s?wd=%s+抖音+短视频", Selector: ".result.c-container"},
			{Name: "sogou", BaseURL: "https://www.sogou.com/web?query=%s+douyin", Selector: ".result"},
			{Name: "bing", BaseURL: "https://cn.bing.com/search?q=%s+抖音+视频", Selector: ".b_algo"},
		},
		Keywords: []string{"抖音", "douyin", "短视频"},
	},
	"xiaohongshu": {
		Name: "xiaohongshu",
		SearchEngines: []SearchEngine{
			{Name: "baidu", BaseURL: "https://www.baidu.com/s?wd=%s+小红书+笔记", Selector: ".result.c-container"},
			{Name: "sogou", BaseURL: "https://www.sogou.com/web?query=%s+xiaohongshu", Selector: ".result"},
			{Name: "bing", BaseURL: "https://cn.bing.com/search?q=%s+小红书+种草", Selector: ".b_algo"},
		},
		Keywords: []string{"小红书", "xiaohongshu", "笔记", "种草"},
	},
	"bilibili": {
		Name: "bilibili",
		SearchEngines: []SearchEngine{
			{Name: "baidu", BaseURL: "https://www.baidu.com/s?wd=%s+bilibili+视频", Selector: ".result.c-container"},
			{Name: "sogou", BaseURL: "https://www.sogou.com/web?query=%s+B站+UP主", Selector: ".result"},
			{Name: "bing", BaseURL: "https://cn.bing.com/search?q=%s+哔哩哔哩", Selector: ".b_algo"},
		},
		Keywords: []string{"bilibili", "b站", "哔哩哔哩", "up主", "视频"},
	},
	// 新增 X 平台（x.com/Twitter）
	"x": {
		Name: "x",
		SearchEngines: []SearchEngine{
			{Name: "baidu", BaseURL: "https://www.baidu.com/s?wd=%s+site:x.com", Selector: ".result.c-container"},
			{Name: "bing", BaseURL: "https://cn.bing.com/search?q=%s+site:x.com", Selector: ".b_algo"},
			{Name: "sogou", BaseURL: "https://www.sogou.com/web?query=%s+X+推文", Selector: ".result"},
		},
		Keywords: []string{"x.com", "X", "推文", "Twitter"},
	},
}

// SearchResult 搜索结果结构
type SearchResult struct {
	Title       string
	URL         string
	Description string
	Source      string
	Time        string
}

// CrawlWeiboPosts 爬取微博内容
func CrawlWeiboPosts(creator models.Creator) ([]models.Post, error) {
	query := extractQueryFromCreator(creator)
	contents, err := crawlPlatformContent("weibo", query, 10)
	if err != nil {
		return createFallbackPosts("weibo", creator, query, 3), nil
	}

	// 转换为models.Post格式（基础版本）
	var result []models.Post
	for _, content := range contents {
		result = append(result, models.Post{
			ID:        primitive.NewObjectID(),
			CreatorID: creator.ID,
			Platform:  "weibo",
			PostID:    fmt.Sprintf("wb_%d", time.Now().Unix()),
			Content:   content.Title + "\n" + content.Content, // 合并标题和内容
			MediaURLs: content.Images,
			CreatedAt: time.Now(),
		})
	}

	return result, nil
}

// CrawlDouyinPosts 爬取抖音内容
func CrawlDouyinPosts(creator models.Creator) ([]models.Post, error) {
	query := extractQueryFromCreator(creator)
	contents, err := crawlPlatformContent("douyin", query, 10)
	if err != nil {
		return createFallbackPosts("douyin", creator, query, 3), nil
	}

	var result []models.Post
	for _, content := range contents {
		mediaURLs := content.Images
		if content.VideoURL != "" {
			mediaURLs = append(mediaURLs, content.VideoURL)
		}

		result = append(result, models.Post{
			ID:        primitive.NewObjectID(),
			CreatorID: creator.ID,
			Platform:  "douyin",
			PostID:    fmt.Sprintf("dy_%d", time.Now().Unix()),
			Content:   content.Title + "\n" + content.Content,
			MediaURLs: mediaURLs,
			CreatedAt: time.Now(),
		})
	}

	return result, nil
}

// CrawlXiaohongshuPosts 爬取小红书内容
func CrawlXiaohongshuPosts(creator models.Creator) ([]models.Post, error) {
	query := extractQueryFromCreator(creator)
	contents, err := crawlPlatformContent("xiaohongshu", query, 10)
	if err != nil {
		return createFallbackPosts("xiaohongshu", creator, query, 3), nil
	}

	var result []models.Post
	for _, content := range contents {
		result = append(result, models.Post{
			ID:        primitive.NewObjectID(),
			CreatorID: creator.ID,
			Platform:  "xiaohongshu",
			PostID:    fmt.Sprintf("xhs_%d", time.Now().Unix()),
			Content:   content.Title + "\n" + content.Content,
			MediaURLs: content.Images,
			CreatedAt: time.Now(),
		})
	}

	return result, nil
}

// CrawlBilibiliPosts 爬取B站内容
func CrawlBilibiliPosts(creator models.Creator) ([]models.Post, error) {
	query := extractQueryFromCreator(creator)
	contents, err := crawlPlatformContent("bilibili", query, 10)
	if err != nil {
		return createFallbackPosts("bilibili", creator, query, 3), nil
	}

	var result []models.Post
	for _, content := range contents {
		mediaURLs := content.Images
		if content.VideoURL != "" {
			mediaURLs = append(mediaURLs, content.VideoURL)
		}

		result = append(result, models.Post{
			ID:        primitive.NewObjectID(),
			CreatorID: creator.ID,
			Platform:  "bilibili",
			PostID:    fmt.Sprintf("bili_%d", time.Now().Unix()),
			Content:   content.Title + "\n" + content.Content,
			MediaURLs: mediaURLs,
			CreatedAt: time.Now(),
		})
	}

	return result, nil
}

// CrawlNewsPosts 爬取新闻内容
func CrawlNewsPosts(query string, limit int) ([]models.Post, error) {
	contents, err := crawlNewsContent(query, limit)
	if err != nil {
		return createFallbackNews(query, limit), nil
	}

	// 转换为Post格式
	var posts []models.Post
	for i, content := range contents {
		if i >= limit {
			break
		}

		post := models.Post{
			ID:        primitive.NewObjectID(),
			CreatorID: primitive.NilObjectID,
			Platform:  "news",
			PostID:    fmt.Sprintf("news_%d", time.Now().Unix()+int64(i)),
			Content:   content.Title + "\n" + content.Content,
			MediaURLs: content.Images,
			CreatedAt: time.Now(),
		}
		posts = append(posts, post)
	}

	return posts, nil
}

// CrawlPlatformContentAdvanced 高级爬取接口，返回详细的CrawlerContent
func CrawlPlatformContentAdvanced(platform, query string, limit int, taskID primitive.ObjectID) ([]models.CrawlerContent, error) {
	contents, err := crawlPlatformContent(platform, query, limit)
	if err != nil {
		return createFallbackContent(platform, query, limit, taskID), nil
	}

	// 设置TaskID
	for i := range contents {
		contents[i].TaskID = taskID
	}

	return contents, nil
}

// crawlPlatformContent 爬取平台内容的通用方法
func crawlPlatformContent(platform, query string, limit int) ([]models.CrawlerContent, error) {
	config, exists := platformConfigs[platform]
	if !exists {
		return nil, fmt.Errorf("不支持的平台: %s", platform)
	}

	var allResults []SearchResult

	for _, engine := range config.SearchEngines {
		if len(allResults) >= limit {
			break
		}

		searchURL := fmt.Sprintf(engine.BaseURL, url.QueryEscape(query))
		results, err := performSearch(searchURL)
		if err != nil {
			continue
		}

		// 过滤平台相关结果
		for _, result := range results {
			if isPlatformRelated(result, config.Keywords, query) {
				allResults = append(allResults, result)
				if len(allResults) >= limit {
					break
				}
			}
		}
	}

	// 转换为CrawlerContent格式
	var contents []models.CrawlerContent
	for i, result := range allResults {
		if i >= limit {
			break
		}

		publishedAt := time.Now().Add(-time.Duration(i+1) * time.Hour)
		content := models.CrawlerContent{
			ID:          primitive.NewObjectID(),
			TaskID:      primitive.NilObjectID, // 由调用方设置
			Title:       result.Title,
			Content:     result.Description,
			Author:      extractAuthor(result, platform),
			Platform:    platform,
			URL:         result.URL,
			PublishedAt: &publishedAt,
			Tags:        extractTags(result, platform, query),
			Images:      []string{},
			VideoURL:    extractVideoURL(result, platform),
			CreatedAt:   time.Now(),
		}
		contents = append(contents, content)
	}

	return contents, nil
}

// crawlNewsContent 爬取新闻内容
func crawlNewsContent(query string, limit int) ([]models.CrawlerContent, error) {
	newsSearchEngines := []SearchEngine{
		{Name: "baidu", BaseURL: "https://www.baidu.com/s?wd=%s+新闻", Selector: ".result.c-container"},
		{Name: "sogou", BaseURL: "https://www.sogou.com/web?query=%s+最新消息", Selector: ".result"},
		{Name: "bing", BaseURL: "https://cn.bing.com/search?q=%s+新闻+资讯", Selector: ".b_algo"},
	}

	var allResults []SearchResult

	for _, engine := range newsSearchEngines {
		if len(allResults) >= limit {
			break
		}

		searchURL := fmt.Sprintf(engine.BaseURL, url.QueryEscape(query))
		results, err := performSearch(searchURL)
		if err != nil {
			continue
		}

		// 过滤新闻相关结果
		for _, result := range results {
			if isNewsRelated(result, query) {
				allResults = append(allResults, result)
				if len(allResults) >= limit {
					break
				}
			}
		}
	}

	// 转换为CrawlerContent格式
	var contents []models.CrawlerContent
	for i, result := range allResults {
		if i >= limit {
			break
		}

		publishedAt := time.Now().Add(-time.Duration(i+1) * time.Hour)
		content := models.CrawlerContent{
			ID:          primitive.NewObjectID(),
			TaskID:      primitive.NilObjectID,
			Title:       result.Title,
			Content:     result.Description,
			Author:      result.Source,
			Platform:    "news",
			URL:         result.URL,
			PublishedAt: &publishedAt,
			Tags:        []string{"新闻", "资讯", query},
			Images:      []string{},
			VideoURL:    "",
			CreatedAt:   time.Now(),
		}
		contents = append(contents, content)
	}

	return contents, nil
}

// performSearch 执行搜索请求（使用标准库HTML解析）
func performSearch(searchURL string) ([]SearchResult, error) {
	client := createHTTPClient()

	req, err := http.NewRequest("GET", searchURL, nil)
	if err != nil {
		return nil, err
	}

	// 设置请求头
	req.Header.Set("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
	req.Header.Set("Accept", "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8")
	req.Header.Set("Accept-Language", "zh-CN,zh;q=0.9,en;q=0.8")
	req.Header.Set("Cache-Control", "no-cache")

	resp, err := client.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("HTTP请求失败，状态码: %d", resp.StatusCode)
	}

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, err
	}

	// 使用正则表达式简单解析HTML内容
	return parseSearchResults(string(body)), nil
}

// parseSearchResults 使用正则表达式解析搜索结果
func parseSearchResults(html string) []SearchResult {
	var results []SearchResult

	// 使用正则表达式提取标题和链接
	titleRegex := regexp.MustCompile(`<h[2-4][^>]*><a[^>]*href="([^"]*)"[^>]*[^>]*>([^<]+)</a></h[2-4]>`)
	matches := titleRegex.FindAllStringSubmatch(html, -1)

	for _, match := range matches {
		if len(match) >= 3 {
			result := SearchResult{
				URL:   strings.TrimSpace(match[1]),
				Title: strings.TrimSpace(match[2]),
			}

			// 规范化常见搜索引擎跳转链接，提取真实目标URL
			result.URL = normalizeSearchResultURL(result.URL)

			// 简单的描述提取（在标题附近查找文本）
			descRegex := regexp.MustCompile(fmt.Sprintf(`%s.*?<[^>]*>([^<]{20,200})<`, regexp.QuoteMeta(result.Title)))
			descMatches := descRegex.FindStringSubmatch(html)
			if len(descMatches) >= 2 {
				result.Description = strings.TrimSpace(descMatches[1])
			}

			if result.Title != "" && result.URL != "" {
				results = append(results, result)
			}
		}
	}

	// 如果正则表达式没有匹配到结果，使用备用方法
	if len(results) == 0 {
		results = parseWithFallbackMethod(html)
	}

	return results
}

// normalizeSearchResultURL 尝试从搜索引擎中间跳转链接中提取真实目标URL
func normalizeSearchResultURL(raw string) string {
	if raw == "" {
		return raw
	}
	u, err := url.Parse(raw)
	if err != nil || u == nil {
		return raw
	}
	host := strings.ToLower(u.Host)

	// Baidu: https://www.baidu.com/link?url=ENCODED
	if strings.Contains(host, "baidu.com") {
		if v := u.Query().Get("url"); v != "" {
			if unescaped, err := url.QueryUnescape(v); err == nil {
				return unescaped
			}
			return v
		}
	}

	// Sogou: ...?url=TARGET
	if strings.Contains(host, "sogou.com") {
		if v := u.Query().Get("url"); v != "" {
			return v
		}
	}

	// Google: https://www.google.com/url?q=TARGET
	if strings.Contains(host, "google.") && u.Path == "/url" {
		if v := u.Query().Get("q"); v != "" {
			return v
		}
	}

	// Bing: /ck/a?url=TARGET 或 /r?url=TARGET
	if strings.Contains(host, "bing.com") {
		if v := u.Query().Get("url"); v != "" {
			return v
		}
	}

	return raw
}

// parseWithFallbackMethod 备用解析方法
func parseWithFallbackMethod(html string) []SearchResult {
	var results []SearchResult

	// 更宽泛的链接匹配
	linkRegex := regexp.MustCompile(`href="([^"]*)"[^>]*>([^<]{5,100})</a>`)
	matches := linkRegex.FindAllStringSubmatch(html, -1)

	for i, match := range matches {
		if i >= 10 { // 限制结果数量
			break
		}

		if len(match) >= 3 {
			url := strings.TrimSpace(match[1])
			title := strings.TrimSpace(match[2])

			// 过滤掉明显的导航链接
			if len(title) > 5 && len(title) < 100 &&
				!strings.Contains(strings.ToLower(title), "登录") &&
				!strings.Contains(strings.ToLower(title), "注册") &&
				!strings.Contains(strings.ToLower(title), "首页") {

				results = append(results, SearchResult{
					URL:         url,
					Title:       title,
					Description: "相关搜索结果",
				})
			}
		}
	}

	return results
}

// isPlatformRelated 检查是否为平台相关内容
func isPlatformRelated(result SearchResult, keywords []string, query string) bool {
	content := strings.ToLower(result.Title + " " + result.Description)

	// 检查是否包含平台关键词或查询词
	for _, keyword := range keywords {
		if strings.Contains(content, strings.ToLower(keyword)) {
			return true
		}
	}

	return strings.Contains(content, strings.ToLower(query))
}

// isNewsRelated 检查是否为新闻相关内容
func isNewsRelated(result SearchResult, query string) bool {
	content := strings.ToLower(result.Title + " " + result.Description)

	// 过滤广告和无关内容
	excludeKeywords := []string{"广告", "ad", "推广", "招聘"}
	for _, keyword := range excludeKeywords {
		if strings.Contains(content, keyword) {
			return false
		}
	}

	// 检查标题长度和相关性
	return len(result.Title) > 10 && len(result.Title) < 200 &&
		strings.Contains(content, strings.ToLower(query))
}

// extractAuthor 提取作者信息
func extractAuthor(result SearchResult, platform string) string {
	content := result.Title + " " + result.Description

	// 查找@用户名
	re := regexp.MustCompile(`@([^@\s]+)`)
	matches := re.FindStringSubmatch(content)
	if len(matches) > 1 {
		return "@" + matches[1]
	}

	// 查找UP主（B站专用）
	if platform == "bilibili" && strings.Contains(content, "UP主") {
		re := regexp.MustCompile(`UP主([^：\s]*)`)
		matches := re.FindStringSubmatch(content)
		if len(matches) > 1 {
			return "UP主" + matches[1]
		}
	}

	// 默认作者名
	defaultAuthors := map[string]string{
		"weibo":       "微博用户",
		"douyin":      "抖音创作者",
		"xiaohongshu": "小红书博主",
		"bilibili":    "B站UP主",
		"x":           "X 用户",
		"news":        "新闻编辑",
	}

	if author, exists := defaultAuthors[platform]; exists {
		return author
	}

	return "创作者"
}

// extractTags 提取标签
func extractTags(result SearchResult, platform, query string) []string {
	var tags []string

	// 添加平台标签
	platformTags := map[string][]string{
		"weibo":       {"微博", "社交媒体"},
		"douyin":      {"抖音", "短视频"},
		"xiaohongshu": {"小红书", "生活分享", "种草"},
		"bilibili":    {"B站", "视频"},
		"x":           {"X", "社交媒体"},
		"news":        {"新闻", "资讯"},
	}

	if platformTag, exists := platformTags[platform]; exists {
		tags = append(tags, platformTag...)
	}

	// 添加查询词作为标签
	tags = append(tags, query)

	// 提取#话题#
	content := result.Title + " " + result.Description
	re := regexp.MustCompile(`#([^#\s]+)#?`)
	matches := re.FindAllStringSubmatch(content, -1)
	for _, match := range matches {
		if len(match) > 1 {
			tags = append(tags, match[1])
		}
	}

	// 去重
	tagMap := make(map[string]bool)
	var uniqueTags []string
	for _, tag := range tags {
		if !tagMap[tag] {
			tagMap[tag] = true
			uniqueTags = append(uniqueTags, tag)
		}
	}

	return uniqueTags
}

// extractVideoURL 提取视频链接
func extractVideoURL(result SearchResult, platform string) string {
	if platform == "douyin" || platform == "bilibili" {
		if strings.Contains(strings.ToLower(result.URL), "video") ||
			strings.Contains(result.URL, "bilibili.com") ||
			strings.Contains(result.URL, "douyin.com") {
			return result.URL
		}
	}
	return ""
}

// extractQueryFromCreator 从创作者信息中提取查询关键词
func extractQueryFromCreator(creator models.Creator) string {
	if creator.Username != "" {
		return creator.Username
	}
	return "热门内容"
}

// createFallbackPosts 创建备用帖子
func createFallbackPosts(platform string, creator models.Creator, query string, limit int) []models.Post {
	var posts []models.Post

	platformNames := map[string]string{
		"weibo":       "微博",
		"douyin":      "抖音",
		"xiaohongshu": "小红书",
		"bilibili":    "B站",
	}

	platformName := platformNames[platform]

	for i := 0; i < limit; i++ {
		post := models.Post{
			ID:        primitive.NewObjectID(),
			CreatorID: creator.ID,
			Platform:  platform,
			PostID:    fmt.Sprintf("%s_%d_%d", platform, time.Now().Unix(), i),
			Content:   fmt.Sprintf("%s热门话题：%s\n%s上关于'%s'的热门内容正在火热讨论中。", platformName, query, platformName, query),
			MediaURLs: []string{},
			CreatedAt: time.Now().Add(-time.Duration(i+1) * time.Hour),
		}
		posts = append(posts, post)
	}

	return posts
}

// createFallbackNews 创建备用新闻
func createFallbackNews(query string, limit int) []models.Post {
	var posts []models.Post
	newsTypes := []string{"突发", "深度", "分析", "评论", "报道"}

	for i := 0; i < limit && i < len(newsTypes); i++ {
		newsType := newsTypes[i]
		post := models.Post{
			ID:        primitive.NewObjectID(),
			CreatorID: primitive.NilObjectID,
			Platform:  "news",
			PostID:    fmt.Sprintf("news_%d_%d", time.Now().Unix(), i),
			Content:   fmt.Sprintf("%s：%s最新进展\n关于'%s'的%s新闻报道，详细分析了相关事件的背景、影响和发展趋势。", newsType, query, query, newsType),
			MediaURLs: []string{},
			CreatedAt: time.Now().Add(-time.Duration(i+1) * time.Hour),
		}
		posts = append(posts, post)
	}

	return posts
}

// createFallbackContent 创建备用内容
func createFallbackContent(platform, query string, limit int, taskID primitive.ObjectID) []models.CrawlerContent {
	var contents []models.CrawlerContent

	platformNames := map[string]string{
		"weibo":       "微博",
		"douyin":      "抖音",
		"xiaohongshu": "小红书",
		"bilibili":    "B站",
		"news":        "新闻",
	}

	platformName := platformNames[platform]

	for i := 0; i < limit; i++ {
		publishedAt := time.Now().Add(-time.Duration(i+1) * time.Hour)
		content := models.CrawlerContent{
			ID:          primitive.NewObjectID(),
			TaskID:      taskID,
			Title:       fmt.Sprintf("%s热门话题：%s", platformName, query),
			Content:     fmt.Sprintf("%s上关于'%s'的热门内容正在火热讨论中。", platformName, query),
			Author:      fmt.Sprintf("%s用户", platformName),
			Platform:    platform,
			URL:         fmt.Sprintf("https://www.baidu.com/s?wd=%s", url.QueryEscape(query)),
			PublishedAt: &publishedAt,
			Tags:        []string{platformName, "热门", query},
			Images:      []string{},
			VideoURL:    "",
			CreatedAt:   time.Now(),
		}
		contents = append(contents, content)
	}

	return contents
}

// HTTPClient 创建HTTP客户端
func createHTTPClient() *http.Client {
	return &http.Client{
		Timeout: 30 * time.Second,
		Transport: &http.Transport{
			MaxIdleConns:        100,
			MaxIdleConnsPerHost: 10,
			IdleConnTimeout:     90 * time.Second,
		},
	}
}

// makeRequest 发送HTTP请求
func makeRequest(url string, headers map[string]string) ([]byte, error) {
	client := createHTTPClient()

	req, err := http.NewRequest("GET", url, nil)
	if err != nil {
		return nil, err
	}

	// 设置请求头
	req.Header.Set("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
	for key, value := range headers {
		req.Header.Set(key, value)
	}

	resp, err := client.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("HTTP请求失败，状态码: %d", resp.StatusCode)
	}

	return io.ReadAll(resp.Body)
}

// parseJSON 解析JSON响应
func parseJSON(data []byte, v interface{}) error {
	return json.Unmarshal(data, v)
}

// extractContent 提取和清理文本内容
func extractContent(rawContent string) string {
	// 移除HTML标签
	content := strings.ReplaceAll(rawContent, "<br>", "\n")
	content = strings.ReplaceAll(content, "<br/>", "\n")

	// 移除多余空白字符
	re := regexp.MustCompile(`\s+`)
	content = re.ReplaceAllString(content, " ")

	return strings.TrimSpace(content)
}
