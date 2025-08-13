import { NextResponse } from 'next/server';
import { AuthResponse, generateRefreshToken, generateToken, getUserSafeById, verifyRefreshToken, findUserById } from '@/lib/auth-backend';

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
    const user = await findUserById(payload.userId);

    if (!user) {
      return NextResponse.json(
        { success: false, message: '用户不存在' },
        { status: 404 }
      );
    }

    // Generate new tokens
    const newToken = generateToken(user);
    const newRefreshToken = generateRefreshToken(user);

    // Prepare response
    const authResponse: AuthResponse = {
      user: {
        id: user.id,
        username: user.username,
        email: user.email,
        role: user.role,
        permissions: user.permissions,
        avatar: user.avatar,
        createdAt: user.createdAt.toISOString(),
        lastLogin: user.lastLogin?.toISOString()
      },
      token: newToken,
      refreshToken: newRefreshToken,
      expiresIn: 3600,
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