'use client';

import { useState, useEffect } from 'react';
import { creatorApi, crawlerApi } from '@/utils/api';

interface Creator {
  id: string;
  username: string;
  platform: string;
  created_at: string;
}

interface CrawlerTask {
  id: string;
  platform: string;
  creator_url: string;
  limit: number;
  status: string;
  error?: string;
  started_at?: string;
  completed_at?: string;
  created_at: string;
  updated_at: string;
}

interface CrawlerContent {
  id: string;
  task_id: string;
  title: string;
  content: string;
  author: string;
  platform: string;
  url: string;
  published_at?: string;
  tags: string[];
  images: string[];
  video_url?: string;
  created_at: string;
}

interface CrawlerStatus {
  status: string;
  message: string;
  service_url?: string;
  last_check?: string;
}

const platformOptions = [
  { value: 'weibo', label: '微博' },
  { value: 'douyin', label: '抖音' },
  { value: 'xiaohongshu', label: '小红书' },
  { value: 'bilibili', label: 'B站' },
];

export default function CrawlerPage() {
  const [creators, setCreators] = useState<Creator[]>([]);
  const [crawlerStatus, setCrawlerStatus] = useState<CrawlerStatus>({ status: 'unknown', message: '检查中...' });
  const [tasks, setTasks] = useState<CrawlerTask[]>([]);
  const [contents, setContents] = useState<CrawlerContent[]>([]);
  const [loading, setLoading] = useState(true);
  const [triggering, setTriggering] = useState(false);
  
  // 新任务表单状态
  const [newTask, setNewTask] = useState({
    platform: 'weibo',
    creator_url: '',
    limit: 10,
  });

  // 搜索模式状态
  const [searchMode, setSearchMode] = useState<'search' | 'url'>('search');

  // 定时刷新间隔（毫秒）
  const REFRESH_INTERVAL = 10000; // 10秒

  useEffect(() => {
    loadData();
    
    // 设置定时刷新
    const interval = setInterval(() => {
      loadCrawlerStatus();
      loadTasks();
      loadContents();
    }, REFRESH_INTERVAL);

    return () => clearInterval(interval);
  }, []);

  const loadData = async () => {
    try {
      setLoading(true);
      await Promise.all([
        loadCreators(),
        loadCrawlerStatus(),
        loadTasks(),
        loadContents(),
      ]);
    } catch (error) {
      console.error('加载数据失败:', error);
    } finally {
      setLoading(false);
    }
  };

  const loadCreators = async () => {
    try {
      const data = await creatorApi.list();
      setCreators(data || []);
    } catch (error) {
      console.error('加载创作者失败:', error);
    }
  };

  const loadCrawlerStatus = async () => {
    try {
      const status = await crawlerApi.status();
      setCrawlerStatus(status);
    } catch (error) {
      console.error('获取爬虫状态失败:', error);
      setCrawlerStatus({ status: 'error', message: '服务不可用' });
    }
  };

  const loadTasks = async () => {
    try {
      const data = await crawlerApi.tasks.list();
      setTasks(data.tasks || []);
    } catch (error) {
      console.error('加载任务列表失败:', error);
    }
  };

  const loadContents = async () => {
    try {
      const data = await crawlerApi.contents.list();
      setContents(data.contents || []);
    } catch (error) {
      console.error('加载内容列表失败:', error);
    }
  };

  const handleCreateTask = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newTask.creator_url.trim()) {
      alert(searchMode === 'search' ? '请输入搜索关键词' : '请输入创作者URL');
      return;
    }

    setTriggering(true);
    try {
      const result = await crawlerApi.trigger(newTask);
      console.log('爬取任务创建成功:', result);
      
      // 重置表单
      setNewTask({
        platform: 'weibo',
        creator_url: '',
        limit: 10,
      });

      // 刷新数据
      await loadTasks();
      
      // 显示成功消息
      const message = searchMode === 'search' 
        ? `搜索任务创建成功！正在搜索"${newTask.creator_url}"相关内容...`
        : '爬取任务创建成功！正在处理中...';
      alert(message);
    } catch (error) {
      console.error('创建爬取任务失败:', error);
      const errorMessage = error instanceof Error ? error.message : '未知错误';
      alert(`创建任务失败: ${errorMessage}`);
    } finally {
      setTriggering(false);
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'pending': return 'text-yellow-600 bg-yellow-100';
      case 'running': return 'text-blue-600 bg-blue-100';
      case 'completed': return 'text-green-600 bg-green-100';
      case 'failed': return 'text-red-600 bg-red-100';
      default: return 'text-gray-600 bg-gray-100';
    }
  };

  const getStatusText = (status: string) => {
    switch (status) {
      case 'pending': return '等待中';
      case 'running': return '运行中';
      case 'completed': return '已完成';
      case 'failed': return '失败';
      default: return status;
    }
  };

  if (loading) {
    return (
      <div className="container mx-auto p-6">
        <div className="text-center py-8">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto"></div>
          <p className="mt-2 text-gray-600">加载中...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="container mx-auto p-6 space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-bold">爬虫管理</h1>
        <div className="flex items-center space-x-2">
          <div className={`px-3 py-1 rounded-full text-sm ${
            crawlerStatus.status === 'active' ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
          }`}>
            {crawlerStatus.message}
          </div>
          <button
            onClick={loadData}
            className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
          >
            刷新
          </button>
        </div>
      </div>

      {/* 创建新任务 */}
      <div className="bg-white p-6 rounded-lg shadow">
        <h2 className="text-xl font-semibold mb-4">创建爬取任务</h2>
        
        {/* 搜索模式切换 */}
        <div className="mb-6">
          <div className="flex space-x-4 mb-4">
            <button
              type="button"
              onClick={() => setSearchMode('search')}
              className={`px-4 py-2 rounded-lg font-medium ${
                searchMode === 'search'
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
              }`}
            >
              🔍 关键词搜索
            </button>
            <button
              type="button"
              onClick={() => setSearchMode('url')}
              className={`px-4 py-2 rounded-lg font-medium ${
                searchMode === 'url'
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
              }`}
            >
              🔗 URL爬取
            </button>
          </div>
          <p className="text-sm text-gray-600">
            {searchMode === 'search' 
              ? '输入关键词，系统将在指定平台搜索相关内容' 
              : '输入创作者链接或网页URL进行爬取'
            }
          </p>
        </div>

        <form onSubmit={handleCreateTask} className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                平台
              </label>
              <select
                value={newTask.platform}
                onChange={(e) => setNewTask({ ...newTask, platform: e.target.value })}
                className="w-full p-3 border border-gray-300 rounded-lg"
              >
                {platformOptions.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                {searchMode === 'search' ? '搜索关键词' : '创作者URL'}
              </label>
              <input
                type={searchMode === 'search' ? 'text' : 'url'}
                value={newTask.creator_url}
                onChange={(e) => setNewTask({ ...newTask, creator_url: e.target.value })}
                placeholder={
                  searchMode === 'search' 
                    ? '例如：科技新闻、美食推荐、旅游攻略' 
                    : 'https://example.com/creator'
                }
                className="w-full p-3 border border-gray-300 rounded-lg"
                required
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                爬取数量
              </label>
              <input
                type="number"
                value={newTask.limit}
                onChange={(e) => setNewTask({ ...newTask, limit: parseInt(e.target.value) })}
                min="1"
                max="50"
                className="w-full p-3 border border-gray-300 rounded-lg"
              />
            </div>
          </div>
          
          {/* 提示信息 */}
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
            <div className="flex items-start">
              <div className="flex-shrink-0">
                <span className="text-blue-600">💡</span>
              </div>
              <div className="ml-3 text-sm text-blue-800">
                <p className="font-medium">爬取说明：</p>
                <ul className="mt-1 space-y-1">
                  <li>• <strong>微博</strong>：搜索相关话题和用户动态</li>
                  <li>• <strong>B站</strong>：搜索视频内容和UP主作品</li>
                  <li>• <strong>小红书</strong>：搜索生活笔记和种草内容</li>
                  <li>• <strong>抖音</strong>：由于反爬限制，提供基础搜索</li>
                  <li>• <strong>新闻</strong>：从多个新闻源搜索相关资讯</li>
                </ul>
              </div>
            </div>
          </div>
          
          <button
            type="submit"
            disabled={triggering}
            className="w-full bg-blue-600 text-white p-3 rounded-lg hover:bg-blue-700 disabled:opacity-50 flex items-center justify-center"
          >
            {triggering ? (
              <>
                <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div>
                正在爬取中...
              </>
            ) : (
              <>
                🚀 开始{searchMode === 'search' ? '搜索' : '爬取'}任务
              </>
            )}
          </button>
        </form>
      </div>

      {/* 任务列表 */}
      <div className="bg-white p-6 rounded-lg shadow">
        <h2 className="text-xl font-semibold mb-4">爬取任务 ({tasks.length})</h2>
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  平台
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  搜索内容/URL
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  状态
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  数量
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  创建时间
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  完成时间
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {tasks.map((task) => (
                <tr key={task.id} className="hover:bg-gray-50">
                  <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                    {platformOptions.find(p => p.value === task.platform)?.label || task.platform}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    <div className="max-w-xs">
                      {task.creator_url.startsWith('http') ? (
                        <a 
                          href={task.creator_url} 
                          target="_blank" 
                          rel="noopener noreferrer"
                          className="text-blue-600 hover:text-blue-800 truncate block"
                          title={task.creator_url}
                        >
                          {task.creator_url}
                        </a>
                      ) : (
                        <span className="text-gray-700 font-medium truncate block" title={task.creator_url}>
                          🔍 {task.creator_url}
                        </span>
                      )}
                    </div>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <span className={`inline-flex px-2 py-1 text-xs font-semibold rounded-full ${getStatusColor(task.status)}`}>
                      {getStatusText(task.status)}
                    </span>
                    {task.error && (
                      <div className="text-xs text-red-600 mt-1" title={task.error}>
                        错误: {task.error.substring(0, 50)}...
                      </div>
                    )}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    <span className="bg-gray-100 text-gray-800 px-2 py-1 rounded-full text-xs">
                      {task.limit} 条
                    </span>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    {new Date(task.created_at).toLocaleString()}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    {task.completed_at ? new Date(task.completed_at).toLocaleString() : '-'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {tasks.length === 0 && (
            <div className="text-center py-8 text-gray-500">
              暂无爬取任务
            </div>
          )}
        </div>
      </div>

      {/* 爬取内容 */}
      <div className="bg-white p-6 rounded-lg shadow">
        <h2 className="text-xl font-semibold mb-4">爬取内容 ({contents.length})</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {contents.map((content) => (
            <div key={content.id} className="border border-gray-200 rounded-lg p-4 hover:shadow-md transition-shadow">
              <div className="flex justify-between items-start mb-2">
                <h3 className="font-semibold text-lg line-clamp-2">{content.title}</h3>
                <span className="text-xs text-gray-500 ml-2 whitespace-nowrap">
                  {platformOptions.find(p => p.value === content.platform)?.label || content.platform}
                </span>
              </div>
              <p className="text-gray-600 text-sm line-clamp-3 mb-3">{content.content}</p>
              <div className="text-xs text-gray-500 space-y-1">
                <div>作者: {content.author}</div>
                <div>发布: {content.published_at ? new Date(content.published_at).toLocaleString() : '未知'}</div>
                {content.tags && content.tags.length > 0 && (
                  <div className="flex flex-wrap gap-1 mt-2">
                    {content.tags.map((tag, index) => (
                      <span key={index} className="bg-gray-100 text-gray-600 px-2 py-1 rounded-full text-xs">
                        {tag}
                      </span>
                    ))}
                  </div>
                )}
              </div>
              {content.url && (
                <a 
                  href={content.url} 
                  target="_blank" 
                  rel="noopener noreferrer"
                  className="inline-block mt-2 text-blue-600 hover:text-blue-800 text-sm"
                >
                  查看原文 →
                </a>
              )}
            </div>
          ))}
        </div>
        {contents.length === 0 && (
          <div className="text-center py-8 text-gray-500">
            暂无爬取内容
          </div>
        )}
      </div>
    </div>
  );
}