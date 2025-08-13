// Authentication System Initialization Script
// 认证系统初始化脚本

import { initializeDefaultAdmin, dbManager } from '@/lib/auth-backend';

/**
 * 初始化认证系统
 * - 连接数据库
 * - 创建默认管理员用户
 * - 设置索引
 */
export async function initializeAuthSystem(): Promise<void> {
  try {
    console.log('Initializing authentication system...');
    
    // 连接数据库
    await dbManager.connect();
    console.log('Database connected successfully');
    
    // 创建用户集合索引
    const users = await dbManager.getCollection('users');
    
    // 创建唯一索引
    await users.createIndex({ username: 1 }, { unique: true });
    await users.createIndex({ email: 1 }, { unique: true });
    await users.createIndex({ id: 1 }, { unique: true });
    
    console.log('Database indexes created successfully');
    
    // 初始化默认管理员
    await initializeDefaultAdmin();
    
    console.log('Authentication system initialized successfully');
    
  } catch (error) {
    console.error('Failed to initialize authentication system:', error);
    throw error;
  }
}

// 如果直接运行此脚本
if (require.main === module) {
  initializeAuthSystem()
    .then(() => {
      console.log('Initialization completed');
      process.exit(0);
    })
    .catch((error) => {
      console.error('Initialization failed:', error);
      process.exit(1);
    });
}