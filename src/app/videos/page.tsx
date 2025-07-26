'use client';

import { useState, useEffect } from 'react';
import { videoApi, creatorApi } from '@/utils/api';

interface Video {
  id: string;
  title: string;
  description: string;
  creator_id: string;
  creator_name?: string;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  video_url?: string;
  thumbnail_url?: string;
  duration?: number;
  created_at: string;
  updated_at: string;
}

interface Creator {
  id: string;
  name: string;
  platform: string;
}

export default function VideosPage() {
  const [videos, setVideos] = useState<Video[]>([]);
  const [creators, setCreators] = useState<Creator[]>([]);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [newVideo, setNewVideo] = useState({
    title: '',
    description: '',
    creator_id: ''
  });
  const [filter, setFilter] = useState({
    status: '',
    creator_id: '',
    search: ''
  });

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      setLoading(true);
      const [videosResponse, creatorsResponse] = await Promise.all([
        videoApi.list(),
        creatorApi.list()
      ]);
      
      // Ensure arrays are never null
      const safeVideosResponse = Array.isArray(videosResponse) ? videosResponse : [];
      const safeCreatorsResponse = Array.isArray(creatorsResponse) ? creatorsResponse : [];
      
      // 为视频添加创作者名称
      const videosWithCreators = safeVideosResponse.map((video: Video) => {
        const creator = safeCreatorsResponse.find((c: Creator) => c.id === video.creator_id);
        return {
          ...video,
          creator_name: creator?.name || '未知创作者'
        };
      });
      
      setVideos(videosWithCreators);
      setCreators(safeCreatorsResponse);
    } catch (error) {
      console.error('加载数据失败:', error);
      setVideos([]); // Set empty arrays on error
      setCreators([]);
      alert('加载数据失败，请重试');
    } finally {
      setLoading(false);
    }
  };

  const handleGenerateVideo = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newVideo.title.trim() || !newVideo.creator_id) {
      alert('请填写完整信息');
      return;
    }

    try {
      setGenerating(true);
      await videoApi.generate(newVideo);
      alert('视频生成任务已启动！');
      setNewVideo({ title: '', description: '', creator_id: '' });
      loadData();
    } catch (error) {
      console.error('生成视频失败:', error);
      alert('生成视频失败，请重试');
    } finally {
      setGenerating(false);
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed': return 'text-green-600 bg-green-100';
      case 'processing': return 'text-blue-600 bg-blue-100';
      case 'failed': return 'text-red-600 bg-red-100';
      default: return 'text-gray-600 bg-gray-100';
    }
  };

  const getStatusText = (status: string) => {
    switch (status) {
      case 'pending': return '等待中';
      case 'processing': return '处理中';
      case 'completed': return '已完成';
      case 'failed': return '失败';
      default: return status;
    }
  };

  const formatDuration = (seconds?: number) => {
    if (!seconds) return '未知';
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = seconds % 60;
    return `${minutes}:${remainingSeconds.toString().padStart(2, '0')}`;
  };

  const filteredVideos = videos ? videos.filter(video => {
    if (filter.status && video.status !== filter.status) return false;
    if (filter.creator_id && video.creator_id !== filter.creator_id) return false;
    if (filter.search && !video.title.toLowerCase().includes(filter.search.toLowerCase())) return false;
    return true;
  }) : [];

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <p className="text-gray-600">加载中...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 p-6">
      <div className="max-w-7xl mx-auto">
        {/* 页面头部 */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900 mb-2">视频生成</h1>
          <p className="text-gray-600">管理和生成视频内容</p>
        </div>

        {/* 统计卡片 */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
          <div className="aws-card">
            <h3 className="text-lg font-semibold text-gray-900 mb-2">总视频数</h3>
            <p className="text-3xl font-bold text-blue-600">{videos ? videos.length : 0}</p>
          </div>
          <div className="aws-card">
            <h3 className="text-lg font-semibold text-gray-900 mb-2">已完成</h3>
            <p className="text-3xl font-bold text-green-600">
              {videos ? videos.filter(v => v.status === 'completed').length : 0}
            </p>
          </div>
          <div className="aws-card">
            <h3 className="text-lg font-semibold text-gray-900 mb-2">处理中</h3>
            <p className="text-3xl font-bold text-blue-600">
              {videos ? videos.filter(v => v.status === 'processing').length : 0}
            </p>
          </div>
          <div className="aws-card">
            <h3 className="text-lg font-semibold text-gray-900 mb-2">失败</h3>
            <p className="text-3xl font-bold text-red-600">
              {videos ? videos.filter(v => v.status === 'failed').length : 0}
            </p>
          </div>
        </div>

        {/* 生成视频表单 */}
        <div className="aws-card mb-8">
          <h2 className="text-xl font-semibold text-gray-900 mb-4">生成新视频</h2>
          <form onSubmit={handleGenerateVideo} className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  视频标题
                </label>
                <input
                  type="text"
                  value={newVideo.title}
                  onChange={(e) => setNewVideo({ ...newVideo, title: e.target.value })}
                  className="aws-input"
                  placeholder="输入视频标题"
                  required
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  创作者
                </label>
                <select
                  value={newVideo.creator_id}
                  onChange={(e) => setNewVideo({ ...newVideo, creator_id: e.target.value })}
                  className="aws-input"
                  required
                >
                  <option value="">选择创作者</option>
                  {creators && creators.map((creator) => (
                    <option key={creator.id} value={creator.id}>
                      {creator.name} ({creator.platform})
                    </option>
                  ))}
                </select>
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                视频描述
              </label>
              <textarea
                value={newVideo.description}
                onChange={(e) => setNewVideo({ ...newVideo, description: e.target.value })}
                className="aws-input"
                rows={3}
                placeholder="输入视频描述（可选）"
              />
            </div>
            <button
              type="submit"
              disabled={generating}
              className="aws-btn-primary disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {generating ? '生成中...' : '生成视频'}
            </button>
          </form>
        </div>

        {/* 筛选器 */}
        <div className="aws-card mb-6">
          <h2 className="text-xl font-semibold text-gray-900 mb-4">筛选视频</h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                状态
              </label>
              <select
                value={filter.status}
                onChange={(e) => setFilter({ ...filter, status: e.target.value })}
                className="aws-input"
              >
                <option value="">全部状态</option>
                <option value="pending">等待中</option>
                <option value="processing">处理中</option>
                <option value="completed">已完成</option>
                <option value="failed">失败</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                创作者
              </label>
              <select
                value={filter.creator_id}
                onChange={(e) => setFilter({ ...filter, creator_id: e.target.value })}
                className="aws-input"
              >
                <option value="">全部创作者</option>
                {creators && creators.map((creator) => (
                  <option key={creator.id} value={creator.id}>
                    {creator.name}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                搜索
              </label>
              <input
                type="text"
                value={filter.search}
                onChange={(e) => setFilter({ ...filter, search: e.target.value })}
                className="aws-input"
                placeholder="搜索视频标题"
              />
            </div>
          </div>
        </div>

        {/* 视频列表 */}
        <div className="aws-card">
          <h2 className="text-xl font-semibold text-gray-900 mb-4">
            视频列表 ({filteredVideos ? filteredVideos.length : 0})
          </h2>
          {!filteredVideos || filteredVideos.length === 0 ? (
            <div className="text-center py-12">
              <div className="text-gray-400 text-6xl mb-4">🎬</div>
              <h3 className="text-lg font-medium text-gray-900 mb-2">暂无视频</h3>
              <p className="text-gray-600">开始生成您的第一个视频吧！</p>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {filteredVideos && filteredVideos.map((video) => (
                <div key={video.id} className="border border-gray-200 rounded-lg p-4 hover:shadow-md transition-shadow">
                  {/* 缩略图 */}
                  <div className="aspect-video bg-gray-100 rounded-lg mb-4 flex items-center justify-center">
                    {video.thumbnail_url ? (
                      <img
                        src={video.thumbnail_url}
                        alt={video.title}
                        className="w-full h-full object-cover rounded-lg"
                      />
                    ) : (
                      <div className="text-gray-400 text-4xl">🎬</div>
                    )}
                  </div>
                  
                  {/* 视频信息 */}
                  <div className="space-y-2">
                    <h3 className="font-semibold text-gray-900 line-clamp-2">{video.title}</h3>
                    {video.description && (
                      <p className="text-sm text-gray-600 line-clamp-2">{video.description}</p>
                    )}
                    <div className="flex items-center justify-between text-sm text-gray-500">
                      <span>{video.creator_name}</span>
                      <span>{formatDuration(video.duration)}</span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className={`px-2 py-1 rounded-full text-xs font-medium ${getStatusColor(video.status)}`}>
                        {getStatusText(video.status)}
                      </span>
                      {video.video_url && video.status === 'completed' && (
                        <a
                          href={video.video_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-blue-600 hover:text-blue-800 text-sm font-medium"
                        >
                          查看视频
                        </a>
                      )}
                    </div>
                    <div className="text-xs text-gray-400">
                      创建时间: {new Date(video.created_at).toLocaleString()}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}