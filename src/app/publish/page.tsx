'use client';

import { useState, useEffect } from 'react';
import { useSearchParams } from 'next/navigation';
import { SocialPlatform, PublishTask } from '@/types';
import { publishApi } from '@/utils/api';

export default function PublishPage() {
  const searchParams = useSearchParams();
  const videoId = searchParams.get('videoId');

  const [selectedPlatforms, setSelectedPlatforms] = useState<SocialPlatform[]>([]);
  const [description, setDescription] = useState('');
  const [publishTasks, setPublishTasks] = useState<PublishTask[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    loadPublishTasks();
  }, []);

  const loadPublishTasks = async () => {
    try {
      const data = await publishApi.list();
      setPublishTasks(data);
    } catch (error) {
      console.error('加载发布任务失败:', error);
      alert('加载发布任务失败');
    }
  };

  const handlePublish = async () => {
    if (!videoId) {
      alert('未找到视频ID');
      return;
    }

    if (selectedPlatforms.length === 0) {
      alert('请选择至少一个发布平台');
      return;
    }

    setLoading(true);
    try {
      const result = await publishApi.create({
        videoId,
        platforms: selectedPlatforms,
        description
      });

      setPublishTasks([...publishTasks, result]);
      // 清空表单
      setSelectedPlatforms([]);
      setDescription('');
    } catch (error) {
      console.error('发布失败:', error);
      alert('发布失败');
    } finally {
      setLoading(false);
    }
  };

  const togglePlatform = (platform: SocialPlatform) => {
    setSelectedPlatforms(prev =>
      prev.includes(platform)
        ? prev.filter(p => p !== platform)
        : [...prev, platform]
    );
  };

  return (
    <main className="min-h-screen" style={{ backgroundColor: 'var(--aws-gray-50)' }}>
      {/* 页面头部 */}
      <div style={{ backgroundColor: 'var(--aws-blue)' }} className="text-white py-8">
        <div className="max-w-7xl mx-auto px-4">
          <div className="flex items-center space-x-3">
            <div className="w-10 h-10 bg-orange-500 rounded-lg flex items-center justify-center">
              <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 4V2a1 1 0 011-1h8a1 1 0 011 1v2m3 0H4a1 1 0 00-1 1v16a1 1 0 001 1h16a1 1 0 001-1V5a1 1 0 00-1-1z" />
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 11V9a2 2 0 114 0v2M7 11h10l-1 8H8l-1-8z" />
              </svg>
            </div>
            <div>
              <h1 className="text-3xl font-bold">内容发布管理</h1>
              <p className="text-gray-300 mt-1">一键发布到多个社交媒体平台</p>
            </div>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 py-8">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* 视频预览 */}
          <div className="lg:col-span-2">
            <div className="aws-card p-6 mb-6">
              <div className="flex items-center mb-6">
                <div className="w-8 h-8 bg-purple-500 rounded flex items-center justify-center mr-3">
                  <svg className="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" />
                  </svg>
                </div>
                <h2 className="text-xl font-semibold">视频预览</h2>
              </div>
              
              <div className="aspect-video bg-gray-100 rounded-lg flex items-center justify-center border-2 border-dashed border-gray-300">
                {videoId ? (
                  <video
                    src={`/api/videos/${videoId}`}
                    controls
                    className="w-full h-full rounded-lg"
                  />
                ) : (
                  <div className="text-center">
                    <svg className="w-16 h-16 text-gray-400 mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" />
                    </svg>
                    <p className="text-gray-500 text-lg">暂无视频</p>
                    <p className="text-gray-400 text-sm mt-1">请先生成视频后再进行发布</p>
                  </div>
                )}
              </div>
            </div>

            {/* 发布任务列表 */}
            <div className="aws-card p-6">
              <div className="flex items-center justify-between mb-6">
                <div className="flex items-center">
                  <div className="w-8 h-8 bg-green-500 rounded flex items-center justify-center mr-3">
                    <svg className="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v10a2 2 0 002 2h8a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
                    </svg>
                  </div>
                  <h2 className="text-xl font-semibold">发布任务</h2>
                </div>
                <span className="text-sm px-3 py-1 bg-gray-100 rounded-full" style={{ color: 'var(--aws-gray-600)' }}>
                  共 {publishTasks.length} 个任务
                </span>
              </div>
              
              {publishTasks.length === 0 ? (
                <div className="text-center py-12">
                  <svg className="w-12 h-12 text-gray-400 mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v10a2 2 0 002 2h8a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
                  </svg>
                  <p className="text-gray-500">暂无发布任务</p>
                </div>
              ) : (
                <div className="space-y-4 max-h-96 overflow-y-auto">
                  {publishTasks.map((task) => (
                    <div key={task.id} className="border border-gray-200 rounded-lg p-4 hover:border-orange-300 transition-colors">
                      <div className="flex items-center justify-between">
                        <div className="flex-1">
                          <div className="flex items-center space-x-2 mb-2">
                            {task.platforms.map((platform) => (
                              <span key={platform} className="text-xs px-2 py-1 bg-blue-100 text-blue-800 rounded-full">
                                {platform === 'weibo' && '📱 微博'}
                                {platform === 'douyin' && '🎵 抖音'}
                                {platform === 'xiaohongshu' && '📖 小红书'}
                                {platform === 'bilibili' && '📺 哔哩哔哩'}
                              </span>
                            ))}
                          </div>
                          <div className="flex items-center space-x-2">
                            <span className={`text-xs px-2 py-1 rounded-full ${
                              task.status === 'pending' ? 'bg-yellow-100 text-yellow-800' :
                              task.status === 'processing' ? 'bg-blue-100 text-blue-800' :
                              task.status === 'published' ? 'bg-green-100 text-green-800' :
                              'bg-red-100 text-red-800'
                            }`}>
                              {task.status === 'pending' && '⏳ 等待发布'}
                              {task.status === 'processing' && '🔄 发布中'}
                              {task.status === 'published' && '✅ 已发布'}
                              {task.status === 'failed' && '❌ 发布失败'}
                            </span>
                          </div>
                          {task.error && (
                            <p className="text-sm text-red-500 mt-2 bg-red-50 p-2 rounded">⚠️ {task.error}</p>
                          )}
                        </div>
                        {task.status === 'published' && task.publishedAt && (
                          <a
                            href={task.publishedAt}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="aws-btn-secondary text-sm"
                          >
                            查看发布
                          </a>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* 发布设置 */}
          <div className="lg:col-span-1">
            <div className="aws-card p-6">
              <div className="flex items-center mb-6">
                <div className="w-8 h-8 bg-orange-500 rounded flex items-center justify-center mr-3">
                  <svg className="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.746 0 3.332.477 4.5 1.253v13C19.832 18.477 18.246 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
                  </svg>
                </div>
                <h2 className="text-xl font-semibold">发布设置</h2>
              </div>
              
              <div className="space-y-6">
                <div>
                  <label className="block text-sm font-medium mb-3" style={{ color: 'var(--aws-gray-900)' }}>
                    选择发布平台
                  </label>
                  <div className="grid grid-cols-2 gap-3">
                    {(['weibo', 'douyin', 'xiaohongshu', 'bilibili'] as SocialPlatform[]).map((platform) => (
                      <button
                        key={platform}
                        onClick={() => togglePlatform(platform)}
                        className={`p-3 rounded-lg border-2 text-sm font-medium transition-all ${
                          selectedPlatforms.includes(platform)
                            ? 'border-orange-500 bg-orange-50 text-orange-700'
                            : 'border-gray-200 text-gray-700 hover:border-orange-300 hover:bg-orange-50'
                        }`}
                        disabled={loading}
                      >
                        <div className="text-center">
                          <div className="text-lg mb-1">
                            {platform === 'weibo' && '📱'}
                            {platform === 'douyin' && '🎵'}
                            {platform === 'xiaohongshu' && '📖'}
                            {platform === 'bilibili' && '📺'}
                          </div>
                          <div>
                            {platform === 'weibo' && '微博'}
                            {platform === 'douyin' && '抖音'}
                            {platform === 'xiaohongshu' && '小红书'}
                            {platform === 'bilibili' && '哔哩哔哩'}
                          </div>
                        </div>
                      </button>
                    ))}
                  </div>
                  <p className="text-xs text-gray-500 mt-2">选择要发布的社交媒体平台</p>
                </div>

                <div>
                  <label className="block text-sm font-medium mb-2" style={{ color: 'var(--aws-gray-900)' }}>
                    发布文案
                  </label>
                  <textarea
                    value={description}
                    onChange={(e) => setDescription(e.target.value)}
                    className="aws-input w-full h-32 resize-none"
                    placeholder="请输入发布文案，支持话题标签和@用户..."
                    disabled={loading}
                  />
                  <div className="flex justify-between text-xs text-gray-500 mt-1">
                    <span>添加合适的话题标签可以提高曝光率</span>
                    <span>{description.length}/500</span>
                  </div>
                </div>
              </div>

              {/* 发布按钮 */}
              <div className="mt-8">
                <button
                  onClick={handlePublish}
                  disabled={!videoId || selectedPlatforms.length === 0 || loading}
                  className={`w-full aws-btn-primary text-lg py-4 ${(!videoId || selectedPlatforms.length === 0 || loading) ? 'opacity-50 cursor-not-allowed' : ''}`}
                >
                  {loading ? (
                    <span className="flex items-center justify-center">
                      <svg className="animate-spin -ml-1 mr-3 h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                      </svg>
                      🚀 发布中...
                    </span>
                  ) : (
                    <span className="flex items-center justify-center">
                      <svg className="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
                      </svg>
                      📤 发布到选中平台
                    </span>
                  )}
                </button>
                
                {(!videoId || selectedPlatforms.length === 0) && (
                  <div className="text-center text-sm text-gray-500 mt-2">
                    {!videoId && <p>⚠️ 请先生成视频</p>}
                    {videoId && selectedPlatforms.length === 0 && <p>⚠️ 请选择发布平台</p>}
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>
    </main>
  );
}