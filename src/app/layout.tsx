import type { Metadata, Viewport } from 'next';
import { Inter } from 'next/font/google';
import './globals.css';
import Navigation from '@/components/Navigation';
import { ErrorBoundary } from '@/components/ErrorBoundary';
import { ToastProvider } from '@/components/Toast';
import { AuthProvider } from '@/lib/auth-client';

const inter = Inter({ subsets: ['latin'] });

export const metadata: Metadata = {
  title: 'NewsHub - 智能内容爬取与管理平台',
  description: '现代化的内容爬取、管理和发布平台，支持多平台真实搜索和智能内容提取',
  keywords: ['内容爬取', '社交媒体', 'AI视频生成', '多平台发布', '内容管理'],
  authors: [{ name: 'NewsHub Team' }],
  openGraph: {
    title: 'NewsHub - 智能内容爬取与管理平台',
    description: '一站式内容创作解决方案：从智能爬取到AI视频生成，再到多平台发布',
    type: 'website',
    locale: 'zh_CN',
  },
  robots: {
    index: true,
    follow: true,
  },
};

export const viewport: Viewport = {
  width: 'device-width',
  initialScale: 1,
  themeColor: '#f97316',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="zh-CN">
      <head>
        <link rel="icon" href="/favicon.ico" />
        <meta charSet="utf-8" />
      </head>
      <body className={inter.className}>
        <ErrorBoundary>
          <AuthProvider>
            <ToastProvider>
              <div className="min-h-screen bg-gray-50">
                <Navigation />
                <main className="pb-8">
                  <ErrorBoundary>
                    {children}
                  </ErrorBoundary>
                </main>
              </div>
            </ToastProvider>
          </AuthProvider>
        </ErrorBoundary>
      </body>
    </html>
  );
}
