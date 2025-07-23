'use client';

import { useState, useEffect } from 'react';
import { postApi, creatorApi } from '@/utils/api';

interface Post {
  id: string;
  title: string;
  content: string;
  platform: string;
  creatorId: string;
  creatorName?: string;
  publishedAt: string;
  imageUrl?: string;
  videoUrl?: string;
  likes?: number;
  shares?: number;
  comments?: number;
}

interface Creator {
  id: string;
  username: string;
  displayName?: string;
  platform: string;
}

export default function ContentPage() {
  const [posts, setPosts] = useState<Post[]>([]);
  const [creators, setCreators] = useState<Creator[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedPlatform, setSelectedPlatform] = useState<string>('all');
  const [selectedCreator, setSelectedCreator] = useState<string>('all');
  const [searchTerm, setSearchTerm] = useState('');

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      setLoading(true);
      const [postsData, creatorsData] = await Promise.all([
        postApi.list({ limit: 50 }),
        creatorApi.list()
      ]);
      setPosts(postsData || []);
      setCreators(creatorsData || []);
    } catch (error) {
      console.error('加载数据失败:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleDeletePost = async (id: string) => {
    if (!confirm('确定要删除这条内容吗？')) return;
    
    try {
      await postApi.delete(id);
      setPosts(posts.filter(post => post.id !== id));
    } catch (error) {
      console.error('删除内容失败:', error);
      alert('删除内容失败');
    }
  };

  const filteredPosts = posts.filter(post => {
    const matchesPlatform = selectedPlatform === 'all' || post.platform === selectedPlatform;
    const matchesCreator = selectedCreator === 'all' || post.creatorId === selectedCreator;
    const matchesSearch = searchTerm === '' || 
      post.title?.toLowerCase().includes(searchTerm.toLowerCase()) ||
      post.content?.toLowerCase().includes(searchTerm.toLowerCase());
    
    return matchesPlatform && matchesCreator && matchesSearch;
  });

  const getPlatformIcon = (platform: string) => {
    switch (platform) {
      case 'weibo': return '🐦';
      case 'douyin': return '🎵';
      case 'xiaohongshu': return '📖';
      case 'bilibili': return '📺';
      default: return '📱';
    }
  };

  const getPlatformName = (platform: string) => {
    switch (platform) {
      case 'weibo': return '微博';
      case 'douyin': return '抖音';
      case 'xiaohongshu': return '小红书';
      case 'bilibili': return '哔哩哔哩';
      default: return platform;
    }
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleString('zh-CN');
  };

  if (loading) {
    return (
      <main className="min-h-screen" style={{ backgroundColor: 'var(--aws-gray-50)' }}>
        <div className="max-w-7xl mx-auto px-4 py-8">
          <div className="flex items-center justify-center py-12">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-orange-500"></div>
            <span className="ml-2 text-gray-600">加载中...</span>
          </div>
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-screen" style={{ backgroundColor: 'var(--aws-gray-50)' }}>
      {/* 页面头部 */}
      <div style={{ backgroundColor: 'var(--aws-blue)' }} className="text-white py-8">
        <div className="max-w-7xl mx-auto px-4">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-3xl font-bold mb-2">内容管理</h1>
              <p className="text-gray-300">管理和查看已爬取的社交媒体内容</p>
            </div>
            <div className="text-right">
              <div className="text-2xl font-bold">{filteredPosts.length}</div>
              <div className="text-sm text-gray-300">条内容</div>
            </div>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 py-8">
        {/* 筛选和搜索 */}
        <div className="aws-card p-6 mb-6">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div>
              <label className="block text-sm font-medium mb-2" style={{ color: 'var(--aws-gray-900)' }}>
                搜索内容
              </label>
              <input
                type="text"
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="aws-input w-full"
                placeholder="搜索标题或内容..."
              />
            </div>
            
            <div>
              <label className="block text-sm font-medium mb-2" style={{ color: 'var(--aws-gray-900)' }}>
                平台筛选
              </label>
              <select
                value={selectedPlatform}
                onChange={(e) => setSelectedPlatform(e.target.value)}
                className="aws-input w-full"
              >
                <option value="all">全部平台</option>
                <option value="weibo">微博</option>
                <option value="douyin">抖音</option>
                <option value="xiaohongshu">小红书</option>
                <option value="bilibili">哔哩哔哩</option>
              </select>
            </div>
            
            <div>
              <label className="block text-sm font-medium mb-2" style={{ color: 'var(--aws-gray-900)' }}>
                创作者筛选
              </label>
              <select
                value={selectedCreator}
                onChange={(e) => setSelectedCreator(e.target.value)}
                className="aws-input w-full"
              >
                <option value="all">全部创作者</option>
                {creators.map((creator) => (
                  <option key={creator.id} value={creator.id}>
                    {creator.displayName || creator.username} ({getPlatformName(creator.platform)})
                  </option>
                ))}
              </select>
            </div>
            
            <div className="flex items-end">
              <button
                onClick={loadData}
                className="aws-btn-secondary w-full"
              >
                刷新数据
              </button>
            </div>
          </div>
        </div>

        {/* 内容列表 */}
        {filteredPosts.length === 0 ? (
          <div className="aws-card p-12 text-center">
            <svg className="w-16 h-16 text-gray-400 mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
            <h3 className="text-lg font-medium text-gray-900 mb-2">暂无内容</h3>
            <p className="text-gray-500">还没有爬取到任何内容，请先添加创作者并触发爬虫</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-6">
            {filteredPosts.map((post) => {
              const creator = creators.find(c => c.id === post.creatorId);
              return (
                <div key={post.id} className="aws-card p-6 hover:shadow-lg transition-shadow">
                  {/* 头部信息 */}
                  <div className="flex items-center justify-between mb-4">
                    <div className="flex items-center space-x-3">
                      <div className="w-8 h-8 bg-gradient-to-r from-blue-400 to-blue-600 rounded-full flex items-center justify-center">
                        <span className="text-white text-sm font-semibold">
                          {getPlatformIcon(post.platform)}
                        </span>
                      </div>
                      <div>
                        <div className="font-medium text-gray-900">
                          {creator?.displayName || creator?.username || '未知创作者'}
                        </div>
                        <div className="text-sm text-gray-500">
                          {getPlatformName(post.platform)}
                        </div>
                      </div>
                    </div>
                    <button
                      onClick={() => handleDeletePost(post.id)}
                      className="text-gray-400 hover:text-red-500 transition-colors p-1"
                      title="删除内容"
                    >
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                      </svg>
                    </button>
                  </div>

                  {/* 内容 */}
                  <div className="mb-4">
                    {post.title && (
                      <h3 className="font-semibold text-gray-900 mb-2 line-clamp-2">
                        {post.title}
                      </h3>
                    )}
                    {post.content && (
                      <p className="text-gray-600 text-sm line-clamp-3">
                        {post.content}
                      </p>
                    )}
                  </div>

                  {/* 媒体预览 */}
                  {post.imageUrl && (
                    <div className="mb-4">
                      <img
                        src={post.imageUrl}
                        alt="内容图片"
                        className="w-full h-32 object-cover rounded-lg"
                      />
                    </div>
                  )}

                  {/* 统计信息 */}
                  <div className="flex items-center justify-between text-sm text-gray-500 mb-3">
                    <div className="flex space-x-4">
                      {post.likes !== undefined && (
                        <span className="flex items-center">
                          <svg className="w-4 h-4 mr-1" fill="currentColor" viewBox="0 0 20 20">
                            <path d="M3.172 5.172a4 4 0 015.656 0L10 6.343l1.172-1.171a4 4 0 115.656 5.656L10 17.657l-6.828-6.829a4 4 0 010-5.656z" />
                          </svg>
                          {post.likes}
                        </span>
                      )}
                      {post.shares !== undefined && (
                        <span className="flex items-center">
                          <svg className="w-4 h-4 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8.684 13.342C8.886 12.938 9 12.482 9 12c0-.482-.114-.938-.316-1.342m0 2.684a3 3 0 110-2.684m0 2.684l6.632 3.316m-6.632-6l6.632-3.316m0 0a3 3 0 105.367-2.684 3 3 0 00-5.367 2.684zm0 9.316a3 3 0 105.367 2.684 3 3 0 00-5.367-2.684z" />
                          </svg>
                          {post.shares}
                        </span>
                      )}
                      {post.comments !== undefined && (
                        <span className="flex items-center">
                          <svg className="w-4 h-4 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                          </svg>
                          {post.comments}
                        </span>
                      )}
                    </div>
                  </div>

                  {/* 发布时间 */}
                  <div className="text-xs text-gray-400">
                    {formatDate(post.publishedAt)}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </main>
  );
}