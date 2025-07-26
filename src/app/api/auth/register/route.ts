import { NextResponse } from 'next/server';
import { AuthResponse, RegisterData } from '@/lib/auth';

// Mock user database - extend the same structure as login
const MOCK_USERS = [
  {
    id: '1',
    username: 'admin',
    email: 'admin@newshub.com',
    password: 'admin123',
    role: 'admin' as const,
    permissions: ['admin:all'],
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
    const existingUser = MOCK_USERS.find(
      u => u.username === data.username || u.email === data.email
    );

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
    const newUser = {
      id: (MOCK_USERS.length + 1).toString(),
      username: data.username.trim(),
      email: data.email.trim().toLowerCase(),
      password: data.password, // In production, hash this password
      role: 'user' as const, // Default role for new registrations
      permissions: [
        'crawler:read', 'crawler:write',
        'content:read', 'content:write',
        'video:read', 'video:generate',
        'publish:read', 'publish:write'
      ],
      avatar: null,
      createdAt: new Date().toISOString(),
      lastLogin: new Date().toISOString(),
    };

    // Add to mock database
    MOCK_USERS.push(newUser);

    // Generate tokens
    const token = generateToken(newUser.id);
    const refreshToken = generateRefreshToken(newUser.id);

    // Prepare response (exclude password)
    const userResponse = {
      id: newUser.id,
      username: newUser.username,
      email: newUser.email,
      role: newUser.role,
      permissions: newUser.permissions,
      avatar: newUser.avatar,
      createdAt: newUser.createdAt,
      lastLogin: newUser.lastLogin,
    };

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