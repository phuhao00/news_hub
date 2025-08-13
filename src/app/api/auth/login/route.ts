import { NextResponse } from 'next/server';
import { AuthResponse, LoginCredentials, findUserByUsernameOrEmail, generateRefreshToken, generateToken, sanitizeUser, updateLastLogin, verifyPassword } from '@/lib/auth-backend';

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
    const user = await findUserByUsernameOrEmail(credentials.username);

    if (!user) {
      return NextResponse.json(
        { success: false, message: '用户不存在' },
        { status: 401 }
      );
    }

    // Verify password
    const isPasswordValid = await verifyPassword(credentials.password, user.password);
    if (!isPasswordValid) {
      return NextResponse.json(
        { success: false, message: '密码错误' },
        { status: 401 }
      );
    }

    // Generate tokens
    const token = generateToken(user);
    const refreshToken = generateRefreshToken(user);

    // Update last login
    await updateLastLogin(user.id);

    // Prepare response (exclude password)
    const userResponse = sanitizeUser(user);

    const authResponse: AuthResponse = {
      user: userResponse,
      token,
      refreshToken,
      expiresIn: 3600, // 1 hour
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