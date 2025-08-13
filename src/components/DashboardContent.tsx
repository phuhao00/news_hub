'use client';

import { useState, useEffect } from 'react';
import { SocialPlatform, Creator } from '@/types';
import { creatorApi, crawlerApi, postApi } from '@/utils/api';
import Link from 'next/link';

export default function DashboardContent() {
  const [creators, setCreators] = useState<Creator[]>([]);
  const [newCreator, setNewCreator] = useState({
    username: '',
    platform: 'weibo' as SocialPlatform,
    profileUrl: '',
    displayName: '',
    autoCrawlEnabled: true,
    crawlInterval: 60,
  });
  const [loading, setLoading] = useState(false);
  const [stats, setStats] = useState({ totalPosts: 0, isRunning: false });
  const [quickCrawling, setQuickCrawling] = useState(false);

  useEffect(() => {
    loadCreators();
    loadStats();
  }, []);

  const loadCreators = async () => {
    try {
      const data = await creatorApi.list();
      setCreators(Array.isArray(data) ? data : []);
    } catch (error) {
      console.error('加载创作者失败:', error);
      setCreators([]); // Set empty array on error
      alert('加载创作者失败');
    }
  };

  const loadStats = async () => {
    try {
      const [postsData, crawlerStatus] = await Promise.all([
        postApi.list({ limit: 1 }),
        crawlerApi.status()
      ]);
      setStats({
        totalPosts: postsData?.length || 0,
        isRunning: crawlerStatus?.isRunning || false
      });
    } catch (error) {
      console.error('加载统计数据失败:', error);
    }
  };

  const handleAddCreator = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      const result = await creatorApi.create(newCreator);
      setCreators([...creators, result]);
      setNewCreator({ 
        username: '', 
        platform: 'weibo',
        profileUrl: '',
        displayName: '',
        autoCrawlEnabled: true,
        crawlInterval: 60,
      });
    } catch (error) {
      console.error('添加创作者失败:', error);
      alert('添加创作者失败');
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteCreator = async (id: string) => {
    if (!confirm('确定要删除这个创作者吗？')) return;
    
    try {
      await creatorApi.delete(id);
      setCreators(creators.filter(creator => creator.id !== id));
    } catch (error) {
      console.error('删除创作者失败:', error);
      alert('删除创作者失败');
    }
  };

  const handleQuickCrawl = async () => {
    if (creators.length === 0) {
      alert('请先添加创作者');
      return;
    }
    
    try {
      setQuickCrawling(true);
      
      // 为每个创作者触发爬取任务
      const crawlPromises = creators.map(creator => 
        crawlerApi.trigger({
          platform: creator.platform,
          creator_url: creator.profileUrl || creator.username,
          limit: 20
        })
      );
      
      await Promise.all(crawlPromises);
      alert(`已为 ${creators.length} 个创作者启动爬取任务！`);
      setTimeout(loadStats, 2000);
    } catch (error) {
      console.error('启动爬虫失败:', error);
      alert('启动爬虫失败: ' + (error instanceof Error ? error.message : '未知错误'));
    } finally {
      setQuickCrawling(false);
    }
  };

  return (
    <main className="min-h-screen" style={{ backgroundColor: 'var(--aws-gray-50)' }}>
      {/* 页面头部 */}
      <div style={{ backgroundColor: 'var(--aws-blue)' }} className="text-white py-12">
        <div className="max-w-7xl mx-auto px-4">
          <div className="text-center">
            <h1 className="text-4xl font-bold mb-4">社交媒体内容管理平台</h1>
            <p className="text-xl text-gray-300 max-w-3xl mx-auto">
              轻松管理多平台创作者，自动采集动态内容，一键生成视频并发布到各大社交媒体平台
            </p>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 py-8">
        {/* 统计概览卡片 */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
          <div className="aws-card p-6 text-center">
            <div className="w-12 h-12 bg-orange-100 rounded-lg flex items-center justify-center mx-auto mb-4">
              <svg className="w-6 h-6 text-orange-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
              </svg>
            </div>
            <h3 className="text-2xl font-bold text-orange-600 mb-1">{creators ? creators.length : 0}</h3>
            <p className="text-gray-600 text-sm">创作者</p>
          </div>
          
          <div className="aws-card p-6 text-center">
            <div className="w-12 h-12 bg-blue-100 rounded-lg flex items-center justify-center mx-auto mb-4">
              <svg className="w-6 h-6 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
            </div>
            <h3 className="text-2xl font-bold text-blue-600 mb-1">{stats.totalPosts}</h3>
            <p className="text-gray-600 text-sm">内容数量</p>
          </div>
          
          <div className="aws-card p-6 text-center">
            <div className="w-12 h-12 bg-green-100 rounded-lg flex items-center justify-center mx-auto mb-4">
              <div className={`w-3 h-3 rounded-full ${
                stats.isRunning ? 'bg-green-500 animate-pulse' : 'bg-gray-400'
              }`}></div>
            </div>
            <h3 className={`text-lg font-semibold mb-1 ${
              stats.isRunning ? 'text-green-600' : 'text-gray-600'
            }`}>
              {stats.isRunning ? '运行中' : '空闲'}
            </h3>
            <p className="text-gray-600 text-sm">爬虫状态</p>
          </div>
          
          <div className="aws-card p-6 text-center">
            <button
              onClick={handleQuickCrawl}
              disabled={quickCrawling || stats.isRunning || !creators || creators.length === 0}
              className={`w-full aws-btn-primary ${
                (quickCrawling || stats.isRunning || !creators || creators.length === 0) ? 'opacity-50 cursor-not-allowed' : ''
              }`}
            >
              {quickCrawling ? (
                <span className="flex items-center justify-center">
                  <svg className="animate-spin -ml-1 mr-2 h-4 w-4 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                  </svg>
                  启动中...
                </span>
              ) : stats.isRunning ? (
                '运行中'
              ) : !creators || creators.length === 0 ? (
                '需要创作者'
              ) : (
                '快速爬取'
              )}
            </button>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          {/* 添加创作者表单 */}
          <div className="aws-card p-6">
            <div className="flex items-center mb-6">
              <div className="w-8 h-8 bg-orange-500 rounded flex items-center justify-center mr-3">
                <svg className="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
                </svg>
              </div>
              <h2 className="text-xl font-semibold">添加创作者</h2>
            </div>
            
            <form onSubmit={handleAddCreator} className="space-y-4">
              <div>
                <label className="block text-sm font-medium mb-2" style={{ color: 'var(--aws-gray-900)' }}>
                  选择平台
                </label>
                <select
                  value={newCreator.platform}
                  onChange={(e) => setNewCreator({ ...newCreator, platform: e.target.value as SocialPlatform })}
                  className="aws-input w-full"
                  disabled={loading}
                >
                  <option value="weibo">微博</option>
                  <option value="douyin">抖音</option>
                  <option value="xiaohongshu">小红书</option>
                  <option value="bilibili">哔哩哔哩</option>
                </select>
              </div>
              
              <div>
                <label className="block text-sm font-medium mb-2" style={{ color: 'var(--aws-gray-900)' }}>
                  用户名/账号
                </label>
                <input
                  type="text"
                  value={newCreator.username}
                  onChange={(e) => setNewCreator({ ...newCreator, username: e.target.value })}
                  className="aws-input w-full"
                  placeholder="请输入用户名或账号ID"
                  required
                  disabled={loading}
                />
              </div>

              <div>
                <label className="block text-sm font-medium mb-2" style={{ color: 'var(--aws-gray-900)' }}>
                  创作者主页URL
                </label>
                <input
                  type="url"
                  value={newCreator.profileUrl}
                  onChange={(e) => setNewCreator({ ...newCreator, profileUrl: e.target.value })}
                  className="aws-input w-full"
                  placeholder="请输入创作者主页链接，用于自动爬取内容"
                  required
                  disabled={loading}
                />
                <p className="text-xs text-gray-500 mt-1">💡 这是系统自动爬取内容的URL</p>
              </div>

              <div>
                <label className="block text-sm font-medium mb-2" style={{ color: 'var(--aws-gray-900)' }}>
                  显示名称
                </label>
                <input
                  type="text"
                  value={newCreator.displayName}
                  onChange={(e) => setNewCreator({ ...newCreator, displayName: e.target.value })}
                  className="aws-input w-full"
                  placeholder="创作者显示名称（可选）"
                  disabled={loading}
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="flex items-center space-x-2">
                    <input
                      type="checkbox"
                      checked={newCreator.autoCrawlEnabled}
                      onChange={(e) => setNewCreator({ ...newCreator, autoCrawlEnabled: e.target.checked })}
                      className="rounded"
                      disabled={loading}
                    />
                    <span className="text-sm font-medium" style={{ color: 'var(--aws-gray-900)' }}>
                      启用自动爬取
                    </span>
                  </label>
                  <p className="text-xs text-gray-500 mt-1">🔄 定时获取最新动态</p>
                </div>

                <div>
                  <label className="block text-sm font-medium mb-2" style={{ color: 'var(--aws-gray-900)' }}>
                    爬取间隔 (分钟)
                  </label>
                  <input
                    type="number"
                    value={newCreator.crawlInterval}
                    onChange={(e) => setNewCreator({ ...newCreator, crawlInterval: parseInt(e.target.value) || 60 })}
                    className="aws-input w-full"
                    min="30"
                    max="1440"
                    disabled={loading || !newCreator.autoCrawlEnabled}
                  />
                </div>
              </div>
              
              <button
                type="submit"
                className={`w-full aws-btn-primary ${loading ? 'opacity-50 cursor-not-allowed' : ''}`}
                disabled={loading}
              >
                {loading ? (
                  <span className="flex items-center justify-center">
                    <svg className="animate-spin -ml-1 mr-3 h-4 w-4 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                    </svg>
                    添加中...
                  </span>
                ) : (
                  '添加创作者'
                )}
              </button>
            </form>
          </div>

          {/* 创作者列表 */}
          <div className="aws-card p-6">
            <div className="flex items-center justify-between mb-6">
              <div className="flex items-center">
                <div className="w-8 h-8 bg-blue-500 rounded flex items-center justify-center mr-3">
                  <svg className="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
                  </svg>
                </div>
                <h2 className="text-xl font-semibold">已添加的创作者</h2>
              </div>
              <span className="text-sm px-3 py-1 bg-gray-100 rounded-full" style={{ color: 'var(--aws-gray-600)' }}>
                {creators ? creators.length : 0} 个
              </span>
            </div>
            
            {!creators || creators.length === 0 ? (
              <div className="text-center py-12">
                <svg className="w-12 h-12 text-gray-400 mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
                </svg>
                <p className="text-gray-500 mb-2">暂无创作者</p>
                <p className="text-sm text-gray-400">添加第一个创作者开始使用</p>
              </div>
            ) : (
              <div className="space-y-3 max-h-96 overflow-y-auto">
                {creators && creators.map((creator) => (
                  <div
                    key={creator.id}
                    className="flex items-center justify-between p-4 border border-gray-200 rounded-lg hover:border-orange-300 transition-colors"
                  >
                    <div className="flex items-center space-x-3">
                      <div className="w-10 h-10 bg-gradient-to-r from-orange-400 to-orange-600 rounded-full flex items-center justify-center">
                        <span className="text-white font-semibold text-sm">
                          {(creator.displayName || creator.username).charAt(0).toUpperCase()}
                        </span>
                      </div>
                      <div className="flex-1">
                        <div className="flex items-center space-x-2">
                          <h3 className="font-medium text-gray-900">{creator.displayName || creator.username}</h3>
                          <span className={`text-xs px-2 py-1 rounded-full ${
                            creator.crawlStatus === 'crawling' ? 'bg-blue-100 text-blue-800' :
                            creator.crawlStatus === 'failed' ? 'bg-red-100 text-red-800' :
                            creator.autoCrawlEnabled ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-600'
                          }`}>
                            {creator.crawlStatus === 'crawling' && '🔄 爬取中'}
                            {creator.crawlStatus === 'failed' && '❌ 失败'}
                            {creator.crawlStatus === 'idle' && creator.autoCrawlEnabled && '✅ 自动'}
                            {creator.crawlStatus === 'idle' && !creator.autoCrawlEnabled && '⏸️ 已停用'}
                          </span>
                        </div>
                        <div className="flex items-center space-x-4 text-sm text-gray-500">
                          <span className="capitalize">{creator.platform}</span>
                          {creator.autoCrawlEnabled && (
                            <>
                              <span>•</span>
                              <span>每 {creator.crawlInterval} 分钟</span>
                            </>
                          )}
                          {creator.lastCrawlAt && (
                            <>
                              <span>•</span>
                              <span>上次: {new Date(creator.lastCrawlAt).toLocaleString()}</span>
                            </>
                          )}
                        </div>
                        {creator.crawlError && (
                          <p className="text-xs text-red-500 mt-1">
                            ⚠️ {creator.crawlError}
                          </p>
                        )}
                      </div>
                    </div>
                    <div className="flex items-center space-x-2">
                      {creator.profileUrl && (
                        <a
                          href={creator.profileUrl}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-gray-400 hover:text-blue-500 transition-colors p-2"
                          title="查看主页"
                        >
                          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                          </svg>
                        </a>
                      )}
                      <button
                        className="text-gray-400 hover:text-red-500 transition-colors p-2"
                        onClick={() => handleDeleteCreator(creator.id)}
                        title="删除创作者"
                      >
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                        </svg>
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </main>
  );
}