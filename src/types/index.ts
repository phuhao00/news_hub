// 支持的社交平台类型
export type SocialPlatform = 'weibo' | 'douyin' | 'xiaohongshu' | 'bilibili';

// 内容创作者信息
export interface Creator {
  id: string;
  username: string;
  platform: SocialPlatform;
  displayName: string;
  avatar?: string;
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