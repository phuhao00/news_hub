import { NextResponse } from 'next/server';
import { getUserSafeById, verifyToken } from '@/lib/auth-backend';

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
    const user = await getUserSafeById(payload.userId);

    if (!user) {
      return NextResponse.json(
        { success: false, message: '用户不存在' },
        { status: 401 }
      );
    }

    // Return user data
    return NextResponse.json({ success: true, user });

  } catch (error) {
    console.error('Token verification error:', error);
    return NextResponse.json(
      { success: false, message: '令牌验证失败' },
      { status: 500 }
    );
  }
}