import { NextResponse } from 'next/server';

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

function verifyToken(token: string): { userId: string } | null {
  try {
    // In production, use proper JWT verification
    const payload = JSON.parse(Buffer.from(token, 'base64').toString());
    
    // Check if token is expired
    if (payload.exp && payload.exp < Math.floor(Date.now() / 1000)) {
      return null;
    }
    
    return { userId: payload.userId };
  } catch (error) {
    return null;
  }
}

export async function GET(request: Request) {
  try {
    const authHeader = request.headers.get('authorization');
    
    if (!authHeader || !authHeader.startsWith('Bearer ')) {
      return NextResponse.json(
        { success: false, message: '缺少认证令牌' },
        { status: 401 }
      );
    }

    const token = authHeader.substring(7); // Remove 'Bearer ' prefix
    const payload = verifyToken(token);

    if (!payload) {
      return NextResponse.json(
        { success: false, message: '无效或已过期的令牌' },
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

    // Return user data
    return NextResponse.json({
      success: true,
      user: {
        id: user.id,
        username: user.username,
        email: user.email,
        role: user.role,
        permissions: user.permissions,
        avatar: user.avatar,
        createdAt: user.createdAt,
        lastLogin: user.lastLogin,
      }
    });

  } catch (error) {
    console.error('Token verification error:', error);
    return NextResponse.json(
      { success: false, message: '令牌验证失败' },
      { status: 500 }
    );
  }
} 