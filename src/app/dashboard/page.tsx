'use client';

import { useAuth } from '@/lib/auth-client';
import { useRouter } from 'next/navigation';
import { useEffect } from 'react';
import DashboardContent from '@/components/DashboardContent';

export default function DashboardPage() {
  const { user, isAuthenticated, logout, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading && !isAuthenticated) {
      router.push('/auth/login');
    }
  }, [isAuthenticated, loading, router]);

  const handleLogout = async () => {
    await logout();
    router.push('/auth/login');
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-32 w-32 border-b-2 border-orange-500 mx-auto"></div>
          <p className="mt-4 text-gray-600">加载中...</p>
        </div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return null; // 重定向中
  }

  return (
    <div className="min-h-screen">
      {/* 用户信息栏 */}
      <div className="bg-white border-b border-gray-200 px-4 py-3">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div className="flex items-center space-x-4">
            <div className="flex items-center space-x-2">
              <div className="w-8 h-8 bg-gradient-to-r from-orange-500 to-orange-600 rounded-full flex items-center justify-center">
                <span className="text-white font-bold text-sm">
                  {(user?.username || 'U').charAt(0).toUpperCase()}
                </span>
              </div>
              <div>
                <p className="text-sm font-medium text-gray-900">
                  欢迎回来，{user?.username || 'User'}
                </p>
                <p className="text-xs text-gray-500">
                  {user?.role || 'User'} • 最后登录: {user?.lastLogin ? new Date(user.lastLogin).toLocaleString('zh-CN') : '首次登录'}
                </p>
              </div>
            </div>
          </div>
          
          <div className="flex items-center space-x-3">
            <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">
              ✓ 已认证
            </span>
            <button
              onClick={handleLogout}
              className="text-gray-500 hover:text-red-600 text-sm font-medium transition-colors"
            >
              退出登录
            </button>
          </div>
        </div>
      </div>

      {/* 主要内容 */}
      <DashboardContent />
    </div>
  );
}