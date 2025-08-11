import { NextResponse } from 'next/server';
import { AuthResponse, LoginCredentials, findUserByUsernameOrEmail, generateRefreshToken, generateToken, sanitizeUser, updateLastLogin } from '@/lib/auth';

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
    const user = findUserByUsernameOrEmail(credentials.username);

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
    updateLastLogin(user.id);

    // Prepare response (exclude password)
    const userResponse = sanitizeUser(user);

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