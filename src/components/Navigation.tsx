'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';

export default function Navigation() {
  const pathname = usePathname();

  const isActive = (path: string) => pathname === path;

  return (
    <nav style={{ backgroundColor: 'var(--aws-blue)' }} className="shadow-lg">
      <div className="max-w-7xl mx-auto px-4">
        <div className="flex items-center justify-between h-16">
          {/* Logo区域 */}
          <div className="flex items-center">
            <Link
              href="/"
              className="flex items-center space-x-2 text-white hover:text-orange-300 transition-colors"
            >
              <div className="w-8 h-8 bg-orange-500 rounded flex items-center justify-center">
                <span className="text-white font-bold text-sm">NH</span>
              </div>
              <span className="text-xl font-bold">NewHub</span>
            </Link>
          </div>

          {/* 导航菜单 */}
          <div className="flex space-x-1">
            <Link
              href="/"
              className={`px-4 py-2 rounded text-sm font-medium transition-colors ${
                isActive('/') 
                  ? 'bg-orange-500 text-white'
                  : 'text-gray-300 hover:text-white hover:bg-gray-700'
              }`}
            >
              采集管理
            </Link>

            <Link
              href="/generate"
              className={`px-4 py-2 rounded text-sm font-medium transition-colors ${
                isActive('/generate')
                  ? 'bg-orange-500 text-white'
                  : 'text-gray-300 hover:text-white hover:bg-gray-700'
              }`}
            >
              生成视频
            </Link>

            <Link
              href="/publish"
              className={`px-4 py-2 rounded text-sm font-medium transition-colors ${
                isActive('/publish')
                  ? 'bg-orange-500 text-white'
                  : 'text-gray-300 hover:text-white hover:bg-gray-700'
              }`}
            >
              发布管理
            </Link>
          </div>

          {/* 右侧操作区 */}
          <div className="flex items-center space-x-4">
            <button className="text-gray-300 hover:text-white transition-colors">
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 17h5l-5 5-5-5h5v-12" />
              </svg>
            </button>
            <button className="text-gray-300 hover:text-white transition-colors">
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
              </svg>
            </button>
          </div>
        </div>
      </div>
    </nav>
  );
}