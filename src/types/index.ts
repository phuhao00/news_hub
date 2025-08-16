// 支持的社交平台类型
export type SocialPlatform = 'weibo' | 'douyin' | 'xiaohongshu' | 'bilibili' | 'x';

// 内容创作者信息
export interface Creator {
  id: string;
  username: string;
  platform: SocialPlatform;
  profileUrl: string; // 创作者主页URL，用于爬取
  displayName: string; // 显示名称
  avatar?: string; // 头像URL
  description?: string; // 描述
  followerCount?: number; // 粉丝数
  autoCrawlEnabled: boolean; // 是否启用自动爬取
  crawlInterval: number; // 爬取间隔（分钟）
  lastCrawlAt?: string; // 上次爬取时间
  nextCrawlAt?: string; // 下次爬取时间
  crawlStatus: 'idle' | 'crawling' | 'failed'; // 爬取状态
  crawlError?: string; // 爬取错误信息
  createdAt: string;
  updatedAt: string;
}

// 采集到的动态内容
export interface Post {
  id: string;
  creatorId: string;
  platform: SocialPlatform;
  content: string;
  images?: string[];
  video?: string;
  url: string;
  publishedAt: string;
  collectedAt: string;
}

// 视频生成配置
export interface VideoGenerationConfig {
  style: 'news' | 'vlog' | 'story';
  duration: number;
  bgMusic?: string;
  resolution: '1080p' | '4K';
}

// 发布任务状态
export type PublishStatus = 'pending' | 'processing' | 'published' | 'failed';

// 发布任务
export interface PublishTask {
  id: string;
  videoUrl: string;
  platforms: SocialPlatform[];
  description: string;
  status: PublishStatus;
  createdAt: string;
  publishedAt?: string;
  error?: string;
}