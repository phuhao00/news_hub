import { NextResponse } from 'next/server';

// Backend API configuration
const BACKEND_API_URL = process.env.BACKEND_API_URL || 'http://localhost:8080/api';

interface VideoGenerationRequest {
  postIds: string[];
  style: 'news' | 'vlog' | 'story';
  duration: number;
  resolution?: '1080p' | '4K';
  title?: string;
  description?: string;
}

export async function POST(request: Request) {
  try {
    const {
      postIds,
      style,
      duration,
      resolution = '1080p',
      title,
      description
    }: VideoGenerationRequest = await request.json();
    
    // Validate required parameters
    if (!postIds || !Array.isArray(postIds) || postIds.length === 0) {
      return NextResponse.json(
        { success: false, message: '请选择至少一个内容作为素材' },
        { status: 400 }
      );
    }

    if (!style || !['news', 'vlog', 'story'].includes(style)) {
      return NextResponse.json(
        { success: false, message: '无效的视频风格' },
        { status: 400 }
      );
    }

    if (!duration || duration < 30 || duration > 300) {
      return NextResponse.json(
        { success: false, message: '视频时长必须在30-300秒之间' },
        { status: 400 }
      );
    }

    // Fetch the content for the posts to validate they exist
    const postsValidation = await Promise.all(
      postIds.map(async (postId) => {
        try {
          const response = await fetch(`${BACKEND_API_URL}/posts/${postId}`);
          return response.ok;
        } catch {
          return false;
        }
      })
    );

    if (postsValidation.some(valid => !valid)) {
      return NextResponse.json(
        { success: false, message: '部分内容不存在或无法访问' },
        { status: 400 }
      );
    }

    // Generate a unique video ID for this request
    const videoId = `video_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;

    // Prepare video generation request for backend
    const videoGenerationData = {
      id: videoId,
      title: title || `AI生成视频 - ${style}风格`,
      description: description || `基于${postIds.length}条内容生成的${style}风格视频`,
      postIds,
      style,
      duration,
      resolution,
      status: 'processing',
      createdAt: new Date().toISOString()
    };

    // Call backend video generation API
    const response = await fetch(`${BACKEND_API_URL}/videos/generate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(videoGenerationData),
    });

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`Backend API error: ${errorText}`);
    }

    const videoData = await response.json();

    // In a real implementation, you would trigger an async video generation process here
    // For now, we'll simulate the process by updating the status
    setTimeout(async () => {
      try {
        // Simulate video generation completion
        await fetch(`${BACKEND_API_URL}/videos/${videoData.id || videoId}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            status: 'completed',
            url: `/api/videos/${videoData.id || videoId}/download`,
            thumbnailUrl: `/api/videos/${videoData.id || videoId}/thumbnail`,
            completedAt: new Date().toISOString()
          }),
        });
      } catch (error) {
        console.error('Failed to update video status:', error);
      }
    }, 5000); // Simulate 5 second generation time

    return NextResponse.json({
      success: true,
      message: '视频生成任务已启动',
      data: {
        id: videoData.id || videoId,
        status: 'processing',
        style,
        duration,
        resolution,
        postIds,
        estimatedCompletionTime: new Date(Date.now() + duration * 1000 + 10000).toISOString(), // Estimated completion
        progress: 0,
        timestamp: new Date().toISOString()
      }
    });
  } catch (error) {
    console.error('Video generation API error:', error);
    return NextResponse.json(
      { 
        success: false, 
        message: '视频生成失败', 
        error: error instanceof Error ? error.message : '未知错误' 
      },
      { status: 500 }
    );
  }
}

export async function GET(request: Request) {
  try {
    const { searchParams } = new URL(request.url);
    const videoId = searchParams.get('videoId');

    if (videoId) {
      // Get specific video status
      const response = await fetch(`${BACKEND_API_URL}/videos/${videoId}`);
      if (!response.ok) {
        throw new Error('Video not found');
      }
      const videoData = await response.json();
      return NextResponse.json({ success: true, data: videoData });
    } else {
      // Get all videos
      const response = await fetch(`${BACKEND_API_URL}/videos`);
      if (!response.ok) {
        throw new Error('Failed to fetch videos');
      }
      const videosData = await response.json();
      return NextResponse.json({ success: true, data: videosData });
    }
  } catch (error) {
    console.error('Get videos error:', error);
    return NextResponse.json(
      { 
        success: false, 
        message: '获取视频信息失败', 
        error: error instanceof Error ? error.message : '未知错误' 
      },
      { status: 500 }
    );
  }
}