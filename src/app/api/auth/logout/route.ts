import { NextResponse } from 'next/server';
import { revokeToken } from '@/lib/auth-backend';

export async function POST(request: Request) {
  try {
    const authHeader = request.headers.get('authorization');
    
    if (!authHeader || !authHeader.startsWith('Bearer ')) {
      return NextResponse.json(
        { success: false, message: '缺少认证令牌' },
        { status: 401 }
      );
    }

    const token = authHeader.substring(7); // Remove 'Bearer ' prefix
    // Revoke token
    revokeToken(token);

    return NextResponse.json({
      success: true,
      message: '注销成功'
    });

  } catch (error) {
    console.error('Logout error:', error);
    return NextResponse.json(
      { success: false, message: '注销失败' },
      { status: 500 }
    );
  }
}