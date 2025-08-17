'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { Post, VideoGenerationConfig } from '@/types';
import { videoApi } from '@/utils/api';

export default function GeneratePage() {
  const router = useRouter();
  const [selectedPosts, setSelectedPosts] = useState<Post[]>([]);
  const [videoConfig, setVideoConfig] = useState<VideoGenerationConfig>({
    style: 'news',
    duration: 60,
    resolution: '1080p'
  });
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    try {
      const cached = sessionStorage.getItem('selectedPosts');
      if (cached) {
        const parsed = JSON.parse(cached) as Post[];
        if (Array.isArray(parsed) && parsed.length) {
          setSelectedPosts(parsed);
        }
      }
    } catch {}
  }, []);

  const handleGenerateVideo = async () => {
    if (selectedPosts.length === 0) {
      alert('请选择至少一个动态内容');
      return;
    }

    setLoading(true);
    try {
      const result = await videoApi.generate({
        postIds: selectedPosts.map(post => post.id),
        style: videoConfig.style,
        duration: videoConfig.duration
      });

      // 跳转到发布页面，并传递视频ID
      router.push(`/publish?videoId=${result.id}`);
    } catch (error) {
      console.error('视频生成失败:', error);
      alert('视频生成失败');
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="min-h-screen" style={{ backgroundColor: 'var(--aws-gray-50)' }}>
      {/* 页面头部 */}
      <div style={{ backgroundColor: 'var(--aws-blue)' }} className="text-white py-8">
        <div className="max-w-7xl mx-auto px-4">
          <div className="flex items-center space-x-3">
            <div className="w-10 h-10 bg-orange-500 rounded-lg flex items-center justify-center">
              <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" />
              </svg>
            </div>
            <div>
              <h1 className="text-3xl font-bold">AI视频生成</h1>
              <p className="text-gray-300 mt-1">基于采集的内容自动生成高质量视频</p>
            </div>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 py-8">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* 视频配置 */}
          <div className="lg:col-span-1">
            <div className="aws-card p-6">
              <div className="flex items-center mb-6">
                <div className="w-8 h-8 bg-blue-500 rounded flex items-center justify-center mr-3">
                  <svg className="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                  </svg>
                </div>
                <h2 className="text-xl font-semibold">视频设置</h2>
              </div>
              
              <div className="space-y-6">
                <div>
                  <label className="block text-sm font-medium mb-2" style={{ color: 'var(--aws-gray-900)' }}>
                    视频风格
                  </label>
                  <select
                    value={videoConfig.style}
                    onChange={(e) => setVideoConfig({ ...videoConfig, style: e.target.value as 'news' | 'vlog' | 'story' })}
                    className="aws-input w-full"
                    disabled={loading}
                  >
                    <option value="news">📺 新闻播报风格</option>
                    <option value="vlog">🎬 Vlog记录风格</option>
                    <option value="story">📖 故事叙述风格</option>
                  </select>
                  <p className="text-xs text-gray-500 mt-1">选择适合您内容的视频风格</p>
                </div>

                <div>
                  <label className="block text-sm font-medium mb-2" style={{ color: 'var(--aws-gray-900)' }}>
                    视频时长
                  </label>
                  <div className="relative">
                    <input
                      type="number"
                      value={videoConfig.duration}
                      onChange={(e) => setVideoConfig({ ...videoConfig, duration: parseInt(e.target.value) })}
                      min="30"
                      max="300"
                      className="aws-input w-full pr-12"
                      disabled={loading}
                    />
                    <span className="absolute right-3 top-1/2 transform -translate-y-1/2 text-sm text-gray-500">秒</span>
                  </div>
                  <div className="flex justify-between text-xs text-gray-500 mt-1">
                    <span>最短30秒</span>
                    <span>最长5分钟</span>
                  </div>
                </div>

                <div>
                  <label className="block text-sm font-medium mb-2" style={{ color: 'var(--aws-gray-900)' }}>
                    输出分辨率
                  </label>
                  <select
                    value={videoConfig.resolution}
                    onChange={(e) => setVideoConfig({ ...videoConfig, resolution: e.target.value as '1080p' | '4K' })}
                    className="aws-input w-full"
                    disabled={loading}
                  >
                    <option value="1080p">🎯 1080p (推荐)</option>
                    <option value="4K">⭐ 4K (超高清)</option>
                  </select>
                  <p className="text-xs text-gray-500 mt-1">4K分辨率生成时间较长</p>
                </div>
              </div>
            </div>
          </div>

          {/* 内容选择和预览 */}
          <div className="lg:col-span-2">
            <div className="aws-card p-6">
              <div className="flex items-center justify-between mb-6">
                <div className="flex items-center">
                  <div className="w-8 h-8 bg-green-500 rounded flex items-center justify-center mr-3">
                    <svg className="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                    </svg>
                  </div>
                  <h2 className="text-xl font-semibold">内容素材</h2>
                </div>
                <span className="text-sm px-3 py-1 bg-gray-100 rounded-full" style={{ color: 'var(--aws-gray-600)' }}>
                  已选择 {selectedPosts.length} 条
                </span>
              </div>
              
              {selectedPosts.length === 0 ? (
                <div className="text-center py-16">
                  <svg className="w-16 h-16 text-gray-400 mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                  </svg>
                  <h3 className="text-lg font-medium text-gray-900 mb-2">暂无选中的内容</h3>
                  <p className="text-gray-500 mb-4">请先在采集管理页面选择要生成视频的内容</p>
                  <button 
                    onClick={() => router.push('/')}
                    className="aws-btn-secondary"
                  >
                    前往选择内容
                  </button>
                </div>
              ) : (
                <div className="space-y-4 max-h-96 overflow-y-auto">
                  {selectedPosts.map((post, index) => (
                    <div key={post.id} className="border border-gray-200 rounded-lg p-4 hover:border-orange-300 transition-colors">
                      <div className="flex items-start justify-between">
                        <div className="flex-1">
                          <div className="flex items-center space-x-2 mb-2">
                            <span className="text-xs px-2 py-1 bg-blue-100 text-blue-800 rounded-full capitalize">
                              {post.platform}
                            </span>
                            <span className="text-xs text-gray-500">
                              素材 #{index + 1}
                            </span>
                          </div>
                          <p className="text-gray-900 mb-2 line-clamp-3">{post.content}</p>
                          <p className="text-sm text-gray-500">
                            📅 {new Date(post.publishedAt).toLocaleString()}
                          </p>
                        </div>
                        <button
                          className="text-gray-400 hover:text-red-500 transition-colors p-1 ml-4"
                          onClick={() => setSelectedPosts(selectedPosts.filter(p => p.id !== post.id))}
                          title="移除此内容"
                        >
                          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                          </svg>
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* 生成按钮 */}
            <div className="mt-6">
              <button
                onClick={handleGenerateVideo}
                disabled={selectedPosts.length === 0 || loading}
                className={`w-full aws-btn-primary text-lg py-4 ${(selectedPosts.length === 0 || loading) ? 'opacity-50 cursor-not-allowed' : ''}`}
              >
                {loading ? (
                  <span className="flex items-center justify-center">
                    <svg className="animate-spin -ml-1 mr-3 h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                    </svg>
                    🎬 AI正在生成视频...
                  </span>
                ) : (
                  <span className="flex items-center justify-center">
                    <svg className="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14.828 14.828a4 4 0 01-5.656 0M9 10h1.586a1 1 0 01.707.293l2.414 2.414a1 1 0 00.707.293H15M9 10V9a2 2 0 012-2h2a2 2 0 012 2v1M9 10v5a2 2 0 002 2h2a2 2 0 002-2v-5" />
                    </svg>
                    🚀 开始生成视频
                  </span>
                )}
              </button>
              
              {selectedPosts.length === 0 && (
                <p className="text-center text-sm text-gray-500 mt-2">
                  请先选择要生成视频的内容素材
                </p>
              )}
            </div>
          </div>
        </div>
      </div>
    </main>
  );
}