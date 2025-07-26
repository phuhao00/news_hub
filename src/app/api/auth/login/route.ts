import { NextResponse } from 'next/server';
import { AuthResponse, LoginCredentials } from '@/lib/auth';

// Mock user database - in production, use a real database
const MOCK_USERS = [
  {
    id: '1',
    username: 'admin',
    email: 'admin@newshub.com',
    password: 'admin123', // In production, this should be hashed
    role: 'admin' as const,
    permissions: ['admin:all'],
    avatar: null,
    createdAt: '2024-01-01T00:00:00Z',
    lastLogin: null,
  },
  {
    id: '2',
    username: 'user',
    email: 'user@newshub.com',
    password: 'user123',
    role: 'user' as const,
    permissions: [
      'crawler:read', 'crawler:write',
      'content:read', 'content:write',
      'video:read', 'video:generate',
      'publish:read', 'publish:write'
    ],
    avatar: null,
    createdAt: '2024-01-01T00:00:00Z',
    lastLogin: null,
  },
  {
    id: '3',
    username: 'viewer',
    email: 'viewer@newshub.com',
    password: 'viewer123',
    role: 'viewer' as const,
    permissions: [
      'crawler:read',
      'content:read',
      'video:read',
      'publish:read'
    ],
    avatar: null,
    createdAt: '2024-01-01T00:00:00Z',
    lastLogin: null,
  },
];

// Generate a simple JWT-like token (in production, use a proper JWT library)
function generateToken(userId: string): string {
  const payload = {
    userId,
    iat: Math.floor(Date.now() / 1000),
    exp: Math.floor(Date.now() / 1000) + (24 * 60 * 60), // 24 hours
  };
  
  // In production, use proper JWT signing
  return Buffer.from(JSON.stringify(payload)).toString('base64');
}

function generateRefreshToken(userId: string): string {
  const payload = {
    userId,
    type: 'refresh',
    iat: Math.floor(Date.now() / 1000),
    exp: Math.floor(Date.now() / 1000) + (7 * 24 * 60 * 60), // 7 days
  };
  
  return Buffer.from(JSON.stringify(payload)).toString('base64');
}

export async function POST(request: Request) {
  try {
    const credentials: LoginCredentials = await request.json();
    
    // Validate input
    if (!credentials.username || !credentials.password) {
      return NextResponse.json(
        { success: false, message: '用户名和密码不能为空' },
        { status: 400 }
      );
    }

    // Find user
    const user = MOCK_USERS.find(
      u => u.username === credentials.username || u.email === credentials.username
    );

    if (!user) {
      return NextResponse.json(
        { success: false, message: '用户不存在' },
        { status: 401 }
      );
    }

    // Verify password (in production, compare hashed passwords)
    if (user.password !== credentials.password) {
      return NextResponse.json(
        { success: false, message: '密码错误' },
        { status: 401 }
      );
    }

    // Generate tokens
    const token = generateToken(user.id);
    const refreshToken = generateRefreshToken(user.id);

    // Update last login
    user.lastLogin = new Date().toISOString();

    // Prepare response (exclude password)
    const userResponse = {
      id: user.id,
      username: user.username,
      email: user.email,
      role: user.role,
      permissions: user.permissions,
      avatar: user.avatar,
      createdAt: user.createdAt,
      lastLogin: user.lastLogin,
    };

    const authResponse: AuthResponse = {
      user: userResponse,
      token,
      refreshToken,
      expiresIn: 24 * 60 * 60, // 24 hours in seconds
    };

    return NextResponse.json({
      success: true,
      message: '登录成功',
      ...authResponse
    });

  } catch (error) {
    console.error('Login error:', error);
    return NextResponse.json(
      { success: false, message: '登录失败，请重试' },
      { status: 500 }
    );
  }
} 