'use client';

import { useState, useEffect } from 'react';
import { SocialPlatform, Creator } from '@/types';
import { creatorApi } from '@/utils/api';

export default function Home() {
  const [creators, setCreators] = useState<Creator[]>([]);
  const [newCreator, setNewCreator] = useState({
    username: '',
    platform: 'weibo' as SocialPlatform,
  });
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    loadCreators();
  }, []);

  const loadCreators = async () => {
    try {
      const data = await creatorApi.list();
      setCreators(data);
    } catch (error) {
      console.error('加载创作者失败:', error);
      alert('加载创作者失败');
    }
  };

  const handleAddCreator = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      const result = await creatorApi.create(newCreator);
      setCreators([...creators, result]);
      setNewCreator({ username: '', platform: 'weibo' });
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
        {/* 功能概览卡片 */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
          <div className="aws-card p-6 text-center">
            <div className="w-12 h-12 bg-orange-100 rounded-lg flex items-center justify-center mx-auto mb-4">
              <svg className="w-6 h-6 text-orange-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
              </svg>
            </div>
            <h3 className="text-lg font-semibold mb-2">创作者管理</h3>
            <p className="text-gray-600 text-sm">添加和管理多平台创作者账号</p>
          </div>
          
          <div className="aws-card p-6 text-center">
            <div className="w-12 h-12 bg-blue-100 rounded-lg flex items-center justify-center mx-auto mb-4">
              <svg className="w-6 h-6 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" />
              </svg>
            </div>
            <h3 className="text-lg font-semibold mb-2">视频生成</h3>
            <p className="text-gray-600 text-sm">AI自动生成高质量视频内容</p>
          </div>
          
          <div className="aws-card p-6 text-center">
            <div className="w-12 h-12 bg-green-100 rounded-lg flex items-center justify-center mx-auto mb-4">
              <svg className="w-6 h-6 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
              </svg>
            </div>
            <h3 className="text-lg font-semibold mb-2">一键发布</h3>
            <p className="text-gray-600 text-sm">同时发布到多个社交媒体平台</p>
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
                {creators.length} 个
              </span>
            </div>
            
            {creators.length === 0 ? (
              <div className="text-center py-12">
                <svg className="w-12 h-12 text-gray-400 mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
                </svg>
                <p className="text-gray-500 mb-2">暂无创作者</p>
                <p className="text-sm text-gray-400">添加第一个创作者开始使用</p>
              </div>
            ) : (
              <div className="space-y-3 max-h-96 overflow-y-auto">
                {creators.map((creator) => (
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
                      <div>
                        <h3 className="font-medium text-gray-900">{creator.displayName || creator.username}</h3>
                        <p className="text-sm text-gray-500 capitalize">{creator.platform}</p>
                      </div>
                    </div>
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
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </main>
  );
}
