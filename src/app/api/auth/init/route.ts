import { NextResponse } from 'next/server';
import { initializeDefaultAdmin, dbManager } from '@/lib/auth-backend';

export async function POST(request: Request) {
  try {
    console.log('Initializing authentication system...');
    
    // 连接数据库
    await dbManager.connect();
    console.log('Database connected successfully');
    
    // 创建用户集合索引
    const users = await dbManager.getCollection('users');
    
    try {
      // 创建唯一索引（如果已存在会忽略错误）
      await users.createIndex({ username: 1 }, { unique: true });
      await users.createIndex({ email: 1 }, { unique: true });
      await users.createIndex({ id: 1 }, { unique: true });
      console.log('Database indexes created successfully');
    } catch (indexError) {
      console.log('Database indexes already exist or creation failed:', indexError);
    }
    
    // 初始化默认管理员
    await initializeDefaultAdmin();
    
    return NextResponse.json({
      success: true,
      message: 'Authentication system initialized successfully'
    });
    
  } catch (error) {
    console.error('Failed to initialize authentication system:', error);
    return NextResponse.json(
      {
        success: false,
        message: 'Failed to initialize authentication system',
        error: error instanceof Error ? error.message : 'Unknown error'
      },
      { status: 500 }
    );
  }
}