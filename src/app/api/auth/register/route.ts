import { NextResponse } from 'next/server';
import { AuthResponse, RegisterData, addUser, findUserByUsernameOrEmail, generateRefreshToken, generateToken, sanitizeUser } from '@/lib/auth-backend';

function validateEmail(email: string): boolean {
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  return emailRegex.test(email);
}

function validatePassword(password: string): string[] {
  const errors: string[] = [];
  
  if (password.length < 6) {
    errors.push('密码长度不能少于6位');
  }
  
  if (!/[a-zA-Z]/.test(password)) {
    errors.push('密码必须包含字母');
  }
  
  if (!/[0-9]/.test(password)) {
    errors.push('密码必须包含数字');
  }
  
  return errors;
}

export async function POST(request: Request) {
  try {
    const data: RegisterData = await request.json();
    
    // Validate input
    const validationErrors: Record<string, string> = {};
    
    if (!data.username || data.username.trim().length < 3) {
      validationErrors.username = '用户名长度不能少于3位';
    }
    
    if (!data.email || !validateEmail(data.email)) {
      validationErrors.email = '请输入有效的邮箱地址';
    }
    
    if (!data.password) {
      validationErrors.password = '密码不能为空';
    } else {
      const passwordErrors = validatePassword(data.password);
      if (passwordErrors.length > 0) {
        validationErrors.password = passwordErrors[0];
      }
    }
    
    if (!data.confirmPassword) {
      validationErrors.confirmPassword = '请确认密码';
    } else if (data.password !== data.confirmPassword) {
      validationErrors.confirmPassword = '两次输入的密码不一致';
    }

    if (Object.keys(validationErrors).length > 0) {
      return NextResponse.json(
        { 
          success: false, 
          message: '注册信息有误',
          fields: validationErrors
        },
        { status: 400 }
      );
    }

    // Check if user already exists
    const existingUser = await findUserByUsernameOrEmail(data.username) || await findUserByUsernameOrEmail(data.email);

    if (existingUser) {
      const field = existingUser.username === data.username ? 'username' : 'email';
      const message = field === 'username' ? '用户名已存在' : '邮箱已被注册';
      
      return NextResponse.json(
        { 
          success: false, 
          message,
          fields: { [field]: message }
        },
        { status: 409 }
      );
    }

    // Create new user
    const newUser = await addUser({
      username: data.username,
      email: data.email,
      password: data.password,
    });

    // Generate tokens
    const token = generateToken(newUser);
    const refreshToken = generateRefreshToken(newUser);

    // Prepare response (exclude password)
    const userResponse = sanitizeUser(newUser);

    const authResponse: AuthResponse = {
      user: userResponse,
      token,
      refreshToken,
      expiresIn: 24 * 60 * 60,
    };

    return NextResponse.json({
      success: true,
      message: '注册成功',
      ...authResponse
    });

  } catch (error) {
    console.error('Registration error:', error);
    return NextResponse.json(
      { success: false, message: '注册失败，请重试' },
      { status: 500 }
    );
  }
}