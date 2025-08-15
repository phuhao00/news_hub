import { NextResponse } from 'next/server';

// Backend API configuration
const BACKEND_API_URL = process.env.BACKEND_API_URL || 'http://localhost:8001/api';

export async function POST(request: Request) {
  try {
    const { platform, username, mode = 'creator', limit = 20 } = await request.json();
    
    // Validate required parameters
    if (!platform || !username) {
      return NextResponse.json(
        { success: false, message: '平台和用户名为必填项' },
        { status: 400 }
      );
    }

    // Validate platform
    const supportedPlatforms = ['weibo', 'bilibili', 'xiaohongshu', 'douyin'];
    if (!supportedPlatforms.includes(platform)) {
      return NextResponse.json(
        { success: false, message: `不支持的平台: ${platform}` },
        { status: 400 }
      );
    }

    // Create crawler task
    const taskResponse = await fetch(`${BACKEND_API_URL}/crawler/tasks`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        platform,
        creator_url: username,
        limit,
        mode
      }),
    });

    if (!taskResponse.ok) {
      const errorText = await taskResponse.text();
      throw new Error(`Backend API error: ${errorText}`);
    }

    const taskData = await taskResponse.json();

    // Trigger the crawler through backend proxy
    const crawlerResponse = await fetch(`${BACKEND_API_URL}/crawler/trigger`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        platform,
        creator_url: username,
        limit
      }),
    });

    if (!crawlerResponse.ok) {
      const errorText = await crawlerResponse.text();
      console.warn(`Crawler trigger warning: ${errorText}`);
      // Don't fail the request if crawler trigger fails, just log it
    }

    return NextResponse.json({
      success: true,
      message: '数据采集任务创建成功',
      data: {
        taskId: taskData.id,
        platform,
        username,
        mode,
        limit,
        status: 'pending',
        timestamp: new Date().toISOString()
      }
    });
  } catch (error) {
    console.error('Crawl API error:', error);
    return NextResponse.json(
      { 
        success: false, 
        message: '数据采集失败', 
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
      // Get specific task status
      const response = await fetch(`${BACKEND_API_URL}/crawler/tasks/${taskId}`);
      if (!response.ok) {
        throw new Error('Failed to fetch task status');
      }
      const taskData = await response.json();
      return NextResponse.json({ success: true, data: taskData });
    } else {
      // Get all tasks
      const response = await fetch(`${BACKEND_API_URL}/crawler/tasks`);
      if (!response.ok) {
        throw new Error('Failed to fetch tasks');
      }
      const tasksData = await response.json();
      return NextResponse.json({ success: true, data: tasksData });
    }
  } catch (error) {
    console.error('Get crawl tasks error:', error);
    return NextResponse.json(
      { 
        success: false, 
        message: '获取任务状态失败', 
        error: error instanceof Error ? error.message : '未知错误' 
      },
      { status: 500 }
    );
  }
}