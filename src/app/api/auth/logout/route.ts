import { NextResponse } from 'next/server';

// In a real application, you might want to maintain a blacklist of revoked tokens
// or store active sessions in a database/cache like Redis
const REVOKED_TOKENS = new Set<string>();

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
    
    // Add token to revoked list (in production, store this in Redis or database)
    REVOKED_TOKENS.add(token);

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

// Helper function to check if token is revoked (use in other auth routes)
export function isTokenRevoked(token: string): boolean {
  return REVOKED_TOKENS.has(token);
} 