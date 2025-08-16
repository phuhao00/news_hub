'use client';

import { useState, useEffect } from 'react';
import { crawlTasksApi, creatorApi } from '@/utils/api';
import { useToast } from '@/components/Toast';
import { Trash2, Search, Filter, RefreshCw, Eye, Calendar, Clock, User, Tag, Image, Video, ExternalLink } from 'lucide-react';

interface CrawlTask {
  id?: string;
  _id?: string;
  task_id: string;
  platform: string;
  instance_id?: string;
  session_id?: string;
  task_type?: string;
  url: string;
  status: string;
  auto_triggered?: boolean;
  trigger_reason?: string;
  created_at: string;
  started_at?: string;
  updated_at?: string;
  completed_at?: string;
  error?: string;
  result?: {
    title?: string;
    content?: string;
    author?: string;
    publish_time?: string;
    tags?: string[];
    images?: string[];
    videos?: string[];
  };
}

interface Creator {
  id: string;
  username: string;
  displayName?: string;
  platform: string;
}

export default function ContentPage() {
  const [crawlTasks, setCrawlTasks] = useState<CrawlTask[]>([]);
  const [creators, setCreators] = useState<Creator[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [deleting, setDeleting] = useState<string | null>(null);
  const [selectedPlatform, setSelectedPlatform] = useState<string>('all');
  const [selectedStatus, setSelectedStatus] = useState<string>('all');
  const [searchTerm, setSearchTerm] = useState('');
  const { addToast } = useToast();

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      setLoading(true);
      setError(null);
      const [tasksData, creatorsData] = await Promise.all([
        crawlTasksApi.list({ limit: 50 }),
        creatorApi.list()
      ]);
      setCrawlTasks(tasksData.tasks || tasksData || []);
      setCreators(creatorsData || []);
    } catch (error) {
      console.error('加载数据失败:', error);
      setError(error instanceof Error ? error.message : '数据加载失败，请稍后重试');
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteTask = async (id: string) => {
    if (!confirm('确定要删除这个爬取任务吗？')) return;
    if (deleting) return; // 防止重复点击
    
    setDeleting(id);
    try {
      // 调用API删除任务
      await crawlTasksApi.delete(id);
      // 重新加载数据
      await loadData();
      addToast({
        type: 'success',
        title: '删除成功',
        message: '任务已成功删除'
      });
    } catch (error) {
      console.error('删除任务失败:', error);
      addToast({
        type: 'error',
        title: '删除失败',
        message: error instanceof Error ? error.message : '删除任务时发生错误'
      });
    } finally {
      setDeleting(null);
    }
  };

  const filteredTasks = crawlTasks.filter(task => {
    const matchesPlatform = selectedPlatform === 'all' || task.platform === selectedPlatform;
    const matchesStatus = selectedStatus === 'all' || task.status === selectedStatus;
    const matchesSearch = searchTerm === '' || 
      task.task_id?.toLowerCase().includes(searchTerm.toLowerCase()) ||
      task.url?.toLowerCase().includes(searchTerm.toLowerCase()) ||
      task.result?.title?.toLowerCase().includes(searchTerm.toLowerCase()) ||
      task.result?.content?.toLowerCase().includes(searchTerm.toLowerCase());
    
    return matchesPlatform && matchesStatus && matchesSearch;
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
    try {
      const date = new Date(dateString);
      if (isNaN(date.getTime())) {
        return '无效日期';
      }
      return date.toLocaleString('zh-CN');
    } catch (error) {
      return '日期格式错误';
    }
  };

  const formatTaskId = (taskId: string) => {
    if (!taskId) return '未知';
    return taskId.length > 8 ? `${taskId.substring(0, 8)}...` : taskId;
  };

  const getStatusColor = (status: string) => {
    switch (status?.toLowerCase()) {
      case 'completed':
        return 'bg-green-100 text-green-800';
      case 'running':
      case 'processing':
        return 'bg-blue-100 text-blue-800';
      case 'failed':
      case 'error':
        return 'bg-red-100 text-red-800';
      case 'pending':
      case 'waiting':
        return 'bg-yellow-100 text-yellow-800';
      default:
        return 'bg-gray-100 text-gray-800';
    }
  };

  const getStatusText = (status: string) => {
    switch (status?.toLowerCase()) {
      case 'completed':
        return '已完成';
      case 'running':
      case 'processing':
        return '执行中';
      case 'failed':
      case 'error':
        return '失败';
      case 'pending':
      case 'waiting':
        return '等待中';
      default:
        return status || '未知';
    }
  };

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

  if (error) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center max-w-md mx-auto">
          <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded mb-4">
            <strong className="font-bold">加载失败！</strong>
            <span className="block sm:inline"> {error}</span>
          </div>
          <button
            onClick={loadData}
            className="bg-blue-600 hover:bg-blue-700 text-white font-bold py-2 px-4 rounded"
          >
            重新加载
          </button>
        </div>
      </div>
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
              <div className="text-2xl font-bold">{filteredTasks.length}</div>
              <div className="text-sm text-gray-300">个任务</div>
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
                状态筛选
              </label>
              <select
                value={selectedStatus}
                onChange={(e) => setSelectedStatus(e.target.value)}
                className="aws-input w-full"
              >
                <option value="all">全部状态</option>
                <option value="pending">等待中</option>
                <option value="running">执行中</option>
                <option value="completed">已完成</option>
                <option value="failed">失败</option>
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

        {/* 任务列表 */}
        {filteredTasks.length === 0 ? (
          <div className="aws-card p-12 text-center">
            <svg className="w-16 h-16 text-gray-400 mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
            <h3 className="text-lg font-medium text-gray-900 mb-2">暂无任务</h3>
            <p className="text-gray-500">还没有任何爬取任务，请先添加创作者并触发爬虫</p>
          </div>
        ) : (
          <div className="space-y-4">
            {filteredTasks.map((task, index) => {
              return (
                <div key={task.id || task._id || task.task_id || `${task.url}-${index}`}
                     className="aws-card p-6 hover:shadow-lg transition-shadow">
                  {/* 头部信息 */}
                  <div className="flex items-center justify-between mb-4">
                    <div className="flex items-center space-x-3">
                      <div className="w-10 h-10 bg-gradient-to-br from-blue-500 to-purple-600 rounded-lg flex items-center justify-center text-white font-bold">
                        {getPlatformName(task.platform).charAt(0)}
                      </div>
                      <div className="flex-1">
                        <div className="flex items-center gap-2 mb-2">
                          <span className={`px-2 py-1 rounded-full text-xs font-medium ${getStatusColor(task.status)}`}>
                            {getStatusText(task.status)}
                          </span>
                          <span className="px-2 py-1 bg-gray-100 text-gray-700 rounded text-xs">
                            {getPlatformName(task.platform)}
                          </span>
                          {task.task_type && (
                            <span className="px-2 py-1 bg-blue-100 text-blue-700 rounded text-xs">
                              {task.task_type}
                            </span>
                          )}
                          {task.auto_triggered && (
                            <span className="px-2 py-1 bg-purple-100 text-purple-700 rounded text-xs">
                              自动
                            </span>
                          )}
                        </div>
                        <div className="mb-2">
                          <span className="text-xs text-gray-500">任务ID: </span>
                          <span className="text-xs font-mono text-gray-700" title={task.task_id}>{formatTaskId(task.task_id)}</span>
                          {task.instance_id && (
                            <span className="ml-4">
                              <span className="text-xs text-gray-500">实例: </span>
                              <span className="text-xs font-mono text-gray-700">{task.instance_id}</span>
                            </span>
                          )}
                        </div>
                        <h3 className="font-semibold text-gray-900 line-clamp-1">
                          {task.result?.title || '无标题'}
                        </h3>
                        {task.trigger_reason && (
                          <p className="text-xs text-gray-500 mb-1">
                            触发原因: {task.trigger_reason}
                          </p>
                        )}
                      </div>
                    </div>
                    <div className="flex items-center space-x-2">
                      <button
                        onClick={() => handleDeleteTask(task._id)}
                        disabled={deleting === task._id}
                        className={`p-2 rounded-lg transition-colors ${
                          deleting === task._id
                            ? 'text-gray-400 cursor-not-allowed'
                            : 'text-gray-400 hover:text-red-500 hover:bg-red-50'
                        }`}
                        title={deleting === task._id ? '删除中...' : '删除任务'}
                      >
                        {deleting === task._id ? (
                          <RefreshCw className="w-4 h-4 animate-spin" />
                        ) : (
                          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                          </svg>
                        )}
                      </button>
                    </div>
                  </div>

                  {/* 任务详情 */}
                  <div className="mb-4">
                    <div className="space-y-2">
                      <div className="flex items-center text-sm text-gray-600">
                        <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" />
                        </svg>
                        <span className="truncate">{task.url}</span>
                      </div>
                      <div className="flex items-center text-sm text-gray-600">
                        <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                        </svg>
                        <span>创建时间: {new Date(task.created_at).toLocaleString('zh-CN')}</span>
                      </div>
                      {task.session_id && (
                        <div className="flex items-center text-sm text-gray-600">
                          <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                          </svg>
                          <span>会话ID: {task.session_id}</span>
                        </div>
                      )}
                      {task.started_at && (
                        <div className="flex items-center text-sm text-gray-600">
                          <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14.828 14.828a4 4 0 01-5.656 0M9 10h1m4 0h1m-7 4h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2z" />
                          </svg>
                          <span>开始时间: {new Date(task.started_at).toLocaleString('zh-CN')}</span>
                        </div>
                      )}
                      {task.updated_at && (
                        <div className="flex items-center text-sm text-gray-600">
                          <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                          </svg>
                          <span>更新时间: {new Date(task.updated_at).toLocaleString('zh-CN')}</span>
                        </div>
                      )}
                      {task.completed_at && (
                        <div className="flex items-center text-sm text-gray-600">
                          <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                          </svg>
                          <span>完成时间: {new Date(task.completed_at).toLocaleString('zh-CN')}</span>
                        </div>
                      )}
                      {task.error && (
                        <div className="flex items-center text-sm text-red-600">
                          <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                          </svg>
                          <span>错误: {task.error}</span>
                        </div>
                      )}
                    </div>
                  </div>

                  {/* 内容预览 */}
                  {task.result && (
                    <div className="mt-4 p-4 bg-blue-50 rounded-lg">
                      <h4 className="font-medium text-blue-900 mb-2">内容预览</h4>
                      {task.result.title && (
                        <div className="mb-2">
                          <span className="font-medium text-blue-800">标题:</span>
                          <p className="text-blue-700">{task.result.title}</p>
                        </div>
                      )}
                      {task.result.author && (
                        <div className="mb-2">
                          <span className="font-medium text-blue-800">作者:</span>
                          <p className="text-blue-700">{task.result.author}</p>
                        </div>
                      )}
                      {task.result.publish_time && (
                              <div className="mb-2">
                                <span className="font-medium text-blue-800">发布时间:</span>
                                <p className="text-blue-700">{formatDate(task.result.publish_time)}</p>
                              </div>
                            )}
                      {task.result.tags && task.result.tags.length > 0 && (
                        <div className="mb-2">
                          <span className="font-medium text-blue-800">标签:</span>
                          <div className="flex flex-wrap gap-1 mt-1">
                            {task.result.tags.map((tag, tIdx) => (
                              <span key={`${task.id || task._id || index}-tag-${tag}-${tIdx}`} className="px-2 py-1 bg-blue-200 text-blue-800 rounded text-xs">
                                {tag}
                              </span>
                            ))}
                          </div>
                        </div>
                      )}
                      {task.result.content && (
                        <div className="mb-2">
                          <span className="font-medium text-blue-800">内容:</span>
                          <p className="text-blue-700 text-sm mt-1 line-clamp-3">{task.result.content}</p>
                        </div>
                      )}
                      {task.result.images && task.result.images.length > 0 && (
                        <div className="mb-2">
                          <span className="font-medium text-blue-800">图片 ({task.result.images.length}):</span>
                          <div className="grid grid-cols-4 gap-2 mt-1">
                            {task.result.images.slice(0, 4).map((image, imgIdx) => (
                              <img key={`${task.id || task._id || index}-image-${imgIdx}`} src={image} alt={`Image ${imgIdx + 1}`} className="w-full h-16 object-cover rounded" />
                            ))}
                          </div>
                        </div>
                      )}
                      {task.result.videos && task.result.videos.length > 0 && (
                        <div>
                          <span className="font-medium text-blue-800">视频 ({task.result.videos.length}):</span>
                          <div className="text-blue-700 text-sm mt-1">
                            {task.result.videos.map((video, vIdx) => (
                              <div key={`${task.id || task._id || index}-video-${vIdx}`} className="truncate">{video}</div>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </main>
  );
}