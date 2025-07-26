import { NextResponse } from 'next/server';
import { AuthResponse } from '@/lib/auth';

// Mock user database
const MOCK_USERS = [
  {
    id: '1',
    username: 'admin',
    email: 'admin@newshub.com',
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

function generateToken(userId: string): string {
  const payload = {
    userId,
    iat: Math.floor(Date.now() / 1000),
    exp: Math.floor(Date.now() / 1000) + (24 * 60 * 60),
  };
  return Buffer.from(JSON.stringify(payload)).toString('base64');
}

function generateRefreshToken(userId: string): string {
  const payload = {
    userId,
    type: 'refresh',
    iat: Math.floor(Date.now() / 1000),
    exp: Math.floor(Date.now() / 1000) + (7 * 24 * 60 * 60),
  };
  return Buffer.from(JSON.stringify(payload)).toString('base64');
}

function verifyRefreshToken(token: string): { userId: string } | null {
  try {
    const payload = JSON.parse(Buffer.from(token, 'base64').toString());
    
    // Check if it's a refresh token
    if (payload.type !== 'refresh') {
      return null;
    }
    
    // Check if token is expired
    if (payload.exp && payload.exp < Math.floor(Date.now() / 1000)) {
      return null;
    }
    
    return { userId: payload.userId };
  } catch (error) {
    return null;
  }
}

export async function POST(request: Request) {
  try {
    const { refreshToken } = await request.json();
    
    if (!refreshToken) {
      return NextResponse.json(
        { success: false, message: '缺少刷新令牌' },
        { status: 400 }
      );
    }

    const payload = verifyRefreshToken(refreshToken);

    if (!payload) {
      return NextResponse.json(
        { success: false, message: '无效或已过期的刷新令牌' },
        { status: 401 }
      );
    }

    // Find user
    const user = MOCK_USERS.find(u => u.id === payload.userId);

    if (!user) {
      return NextResponse.json(
        { success: false, message: '用户不存在' },
        { status: 401 }
      );
    }

    // Generate new tokens
    const newToken = generateToken(user.id);
    const newRefreshToken = generateRefreshToken(user.id);

    // Prepare response
    const userResponse = {
      id: user.id,
      username: user.username,
      email: user.email,
      role: user.role,
      permissions: user.permissions,
      avatar: user.avatar,
      createdAt: user.createdAt,
      lastLogin: new Date().toISOString(),
    };

    const authResponse: AuthResponse = {
      user: userResponse,
      token: newToken,
      refreshToken: newRefreshToken,
      expiresIn: 24 * 60 * 60,
    };

    return NextResponse.json({
      success: true,
      message: '令牌刷新成功',
      ...authResponse
    });

  } catch (error) {
    console.error('Token refresh error:', error);
    return NextResponse.json(
      { success: false, message: '刷新令牌失败' },
      { status: 500 }
    );
  }
} 