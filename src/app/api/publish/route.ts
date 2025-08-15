import { NextResponse } from 'next/server';

// Backend API configuration
const BACKEND_API_URL = process.env.BACKEND_API_URL || 'http://localhost:8001/api';

interface PublishRequest {
  videoId: string;
  platforms: string[];
  description: string;
  scheduledAt?: string;
  tags?: string[];
}

export async function POST(request: Request) {
  try {
    const {
      videoId,
      platforms,
      description,
      scheduledAt,
      tags = []
    }: PublishRequest = await request.json();
    
    // Validate required parameters
    if (!videoId) {
      return NextResponse.json(
        { success: false, message: '视频ID为必填项' },
        { status: 400 }
      );
    }

    if (!platforms || !Array.isArray(platforms) || platforms.length === 0) {
      return NextResponse.json(
        { success: false, message: '请选择至少一个发布平台' },
        { status: 400 }
      );
    }

    if (!description || description.trim().length === 0) {
      return NextResponse.json(
        { success: false, message: '发布文案不能为空' },
        { status: 400 }
      );
    }

    // Validate platforms
    const supportedPlatforms = ['weibo', 'douyin', 'xiaohongshu', 'bilibili'];
    const invalidPlatforms = platforms.filter(platform => !supportedPlatforms.includes(platform));
    if (invalidPlatforms.length > 0) {
      return NextResponse.json(
        { success: false, message: `不支持的平台: ${invalidPlatforms.join(', ')}` },
        { status: 400 }
      );
    }

    // Verify video exists and is completed
    const videoResponse = await fetch(`${BACKEND_API_URL}/videos/${videoId}`);
    if (!videoResponse.ok) {
      return NextResponse.json(
        { success: false, message: '视频不存在或无法访问' },
        { status: 404 }
      );
    }

    const videoData = await videoResponse.json();
    if (videoData.status !== 'completed') {
      return NextResponse.json(
        { success: false, message: '视频尚未生成完成，无法发布' },
        { status: 400 }
      );
    }

    // Create publish task
    const publishTaskData = {
      videoId,
      platforms,
      description,
      scheduledAt: scheduledAt || new Date().toISOString(),
      tags,
      status: 'pending',
      createdAt: new Date().toISOString()
    };

    const response = await fetch(`${BACKEND_API_URL}/publish`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(publishTaskData),
    });

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`Backend API error: ${errorText}`);
    }

    const publishData = await response.json();

    // In a real implementation, you would trigger async publishing processes here
    // For now, we'll simulate the publishing process
    setTimeout(async () => {
      try {
        // Simulate platform-specific publishing
        const publishResults = await Promise.allSettled(
          platforms.map(async (platform) => {
            // Simulate platform API calls
            const platformResult = await simulatePlatformPublish(platform, videoData, description);
            return { platform, ...platformResult };
          })
        );

        // Update publish task status
        const successfulPublishes = publishResults
          .filter(result => result.status === 'fulfilled')
          .map(result => result.value);

        const failedPublishes = publishResults
          .filter(result => result.status === 'rejected')
          .map(result => ({ error: result.reason }));

        const finalStatus = failedPublishes.length === 0 ? 'published' : 
                           successfulPublishes.length === 0 ? 'failed' : 'partial';

        await fetch(`${BACKEND_API_URL}/publish/${publishData.id}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            status: finalStatus,
            publishedAt: new Date().toISOString(),
            results: successfulPublishes,
            errors: failedPublishes,
            completedAt: new Date().toISOString()
          }),
        });
      } catch (error) {
        console.error('Failed to update publish status:', error);
      }
    }, 3000); // Simulate 3 second publishing time

    return NextResponse.json({
      success: true,
      message: '发布任务已创建',
      data: {
        id: publishData.id,
        videoId,
        platforms,
        description,
        status: 'pending',
        estimatedCompletionTime: new Date(Date.now() + 10000).toISOString(), // 10 seconds
        timestamp: new Date().toISOString()
      }
    });
  } catch (error) {
    console.error('Publish API error:', error);
    return NextResponse.json(
      { 
        success: false, 
        message: '发布失败', 
        error: error instanceof Error ? error.message : '未知错误' 
      },
      { status: 500 }
    );
  }
}

export async function GET(request: Request) {
  try {
    const { searchParams } = new URL(request.url);
    const taskId = searchParams.get('taskId');

    if (taskId) {
      // Get specific publish task status
      const response = await fetch(`${BACKEND_API_URL}/publish/${taskId}`);
      if (!response.ok) {
        throw new Error('Publish task not found');
      }
      const taskData = await response.json();
      return NextResponse.json({ success: true, data: taskData });
    } else {
      // Get all publish tasks
      const response = await fetch(`${BACKEND_API_URL}/publish/tasks`);
      if (!response.ok) {
        throw new Error('Failed to fetch publish tasks');
      }
      const tasksData = await response.json();
      return NextResponse.json({ success: true, data: tasksData });
    }
  } catch (error) {
    console.error('Get publish tasks error:', error);
    return NextResponse.json(
      { 
        success: false, 
        message: '获取发布任务失败', 
        error: error instanceof Error ? error.message : '未知错误' 
      },
      { status: 500 }
    );
  }
}

// Simulate platform-specific publishing (in real implementation, this would use actual platform APIs)
async function simulatePlatformPublish(platform: string, videoData: any, description: string) {
  // Simulate network delay
  await new Promise(resolve => setTimeout(resolve, Math.random() * 2000 + 1000));

  // Simulate random success/failure for demonstration
  const shouldSucceed = Math.random() > 0.1; // 90% success rate

  if (!shouldSucceed) {
    throw new Error(`Platform ${platform} publishing failed: Simulated error`);
  }

  // Simulate successful publishing
  const platformUrls = {
    weibo: `https://weibo.com/post/${Math.random().toString(36).substr(2, 9)}`,
    douyin: `https://www.douyin.com/video/${Math.random().toString(36).substr(2, 9)}`,
    xiaohongshu: `https://www.xiaohongshu.com/explore/${Math.random().toString(36).substr(2, 9)}`,
    bilibili: `https://www.bilibili.com/video/BV${Math.random().toString(36).substr(2, 9)}`
  };

  return {
    success: true,
    url: platformUrls[platform as keyof typeof platformUrls] || `https://${platform}.com/post/123`,
    publishedAt: new Date().toISOString(),
    metrics: {
      views: Math.floor(Math.random() * 10000),
      likes: Math.floor(Math.random() * 1000),
      shares: Math.floor(Math.random() * 100)
    }
  };
}