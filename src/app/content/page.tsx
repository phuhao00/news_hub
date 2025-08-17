'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { crawlTasksApi, creatorApi, crawlerApi } from '@/utils/api';
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
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [creators, setCreators] = useState<Creator[]>([]);
  const [platformOptions, setPlatformOptions] = useState<{ value: string; label: string }[]>([
    { value: 'all', label: '全部平台' },
    { value: 'weibo', label: '微博' },
    { value: 'douyin', label: '抖音' },
    { value: 'xiaohongshu', label: '小红书' },
    { value: 'bilibili', label: '哔哩哔哩' },
  ]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [deleting, setDeleting] = useState<string | null>(null);
  const [selectedPlatform, setSelectedPlatform] = useState<string>('all');
  const [selectedStatus, setSelectedStatus] = useState<string>('all');
  const [searchTerm, setSearchTerm] = useState('');
  const { addToast } = useToast();
  const router = useRouter();

  useEffect(() => {
    loadData();
    // 动态加载平台选项
    (async () => {
      try {
        const data = await crawlerApi.platforms();
        const list: { key: string; name: string }[] = data?.platforms || [];
        if (Array.isArray(list) && list.length) {
          const dynamic = [{ value: 'all', label: '全部平台' }].concat(
            list.map((p) => ({ value: p.key, label: p.name }))
          );
          setPlatformOptions(dynamic);
        }
      } catch (e) {
        // 保持默认选项
      }
    })();
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
      setSelectedIds([]);
      setCreators(creatorsData || []);
    } catch (error) {
      console.error('加载数据失败:', error);
      setError(error instanceof Error ? error.message : '数据加载失败，请稍后重试');
    } finally {
      setLoading(false);
    }
  };
  const toggleSelectOne = (id: string, checked: boolean) => {
    setSelectedIds((prev) => {
      const set = new Set(prev);
      if (checked) set.add(id); else set.delete(id);
      return Array.from(set);
    });
  };

  const toggleSelectAllVisible = (checked: boolean) => {
    const visibleIds = filteredTasks.map(t => (t.id || t._id)!).filter(Boolean);
    setSelectedIds(checked ? visibleIds : []);
  };

  const handleBatchDelete = async () => {
    if (selectedIds.length === 0) return;
    if (!confirm(`确定要删除选中的 ${selectedIds.length} 个任务吗？`)) return;
    try {
      await crawlTasksApi.batchDelete({ task_ids: selectedIds });
      await loadData();
      addToast({ type: 'success', title: '批量删除成功', message: `已删除 ${selectedIds.length} 个任务` });
    } catch (error) {
      console.error('批量删除失败:', error);
      addToast({ type: 'error', title: '批量删除失败', message: error instanceof Error ? error.message : '批量删除时发生错误' });
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

  const handleGenerateVideo = () => {
    if (selectedIds.length === 0) {
      addToast({ type: 'error', title: '未选择内容', message: '请先选择至少一条内容' });
      return;
    }
    const idSet = new Set(selectedIds);
    const selectedTasks = crawlTasks.filter(t => idSet.has((t.id || t._id)!));
    const posts = selectedTasks.map((task) => {
      const result = task.result || {} as any;
      const images = Array.isArray(result.images) ? result.images : [];
      const videos = Array.isArray(result.videos) ? result.videos : [];
      const published = (result.publish_time as string) || task.completed_at || task.created_at;
      const collected = task.updated_at || task.completed_at || task.created_at;
      return {
        id: (task.id || task._id || task.task_id) as string,
        creatorId: task.session_id || '',
        platform: task.platform,
        content: (result.content as string) || (result.title as string) || task.url,
        images,
        video: videos.length ? videos[0] : undefined,
        url: task.url,
        publishedAt: published,
        collectedAt: collected,
      };
    });
    try {
      sessionStorage.setItem('selectedPosts', JSON.stringify(posts));
    } catch {}
    router.push('/generate');
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
      case 'x': return 'X/Twitter';
      case 'twitter': return 'X/Twitter';
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
        <div className="aws-card p-6 mb-6 space-y-4">
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
                placeholder="搜索标题、正文或URL..."
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
                {platformOptions.map((opt) => (
                  <option key={opt.value} value={opt.value}>{opt.label}</option>
                ))}
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
              <button onClick={loadData} className="aws-btn-secondary w-full">刷新数据</button>
            </div>
          </div>
          <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3">
            <div className="text-sm text-gray-600">
              已选 <span className="px-2 py-0.5 rounded-full bg-gray-100 text-gray-800">{selectedIds.length}</span> 条
            </div>
            <div className="flex flex-wrap gap-2">
              <button onClick={handleBatchDelete} disabled={selectedIds.length === 0} className={`${selectedIds.length === 0 ? 'aws-btn-disabled' : 'aws-btn-danger'}`}>
                批量删除{selectedIds.length ? `（${selectedIds.length}）` : ''}
              </button>
              <button onClick={handleGenerateVideo} disabled={selectedIds.length === 0} className={`${selectedIds.length === 0 ? 'aws-btn-disabled' : 'aws-btn-primary'}`}>
                生成视频并前往
              </button>
              <button
                onClick={() => {
                  if (selectedIds.length === 0) return;
                  const idSet = new Set(selectedIds);
                  const selectedTasks = crawlTasks.filter(t => idSet.has((t.id || t._id)!));
                  const combined = selectedTasks.map(t => (t.result?.content || t.result?.title || t.url || '')).filter(Boolean).join('\n');
                  try { sessionStorage.setItem('speechText', combined); } catch {}
                  router.push('/speech');
                }}
                disabled={selectedIds.length === 0}
                className={`${selectedIds.length === 0 ? 'aws-btn-disabled' : 'aws-btn-secondary'}`}
              >
                转语音并前往
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
            <div className="sticky top-2 z-10 bg-white/70 backdrop-blur rounded px-3 py-2 flex items-center gap-3">
              <input type="checkbox" className="scale-110" onChange={(e) => toggleSelectAllVisible(e.target.checked)} checked={filteredTasks.length > 0 && filteredTasks.every(t => selectedIds.includes((t.id || t._id)!))} />
              <span className="text-sm text-gray-600">全选本页</span>
              <span className="ml-auto text-xs text-gray-500">共 {filteredTasks.length} 条</span>
            </div>
            {filteredTasks.map((task, index) => {
              return (
                <div key={task.id || task._id || task.task_id || `${task.url}-${index}`}
                     className="aws-card p-6 hover:shadow-lg transition-shadow">
                  <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
                    {/* 左侧：任务信息 */}
                    <div className="lg:col-span-8">
                      <div className="flex items-center justify-between mb-4">
                        <div className="flex items-center space-x-3">
                          <input type="checkbox" className="mr-2" onChange={(e) => {
                            const realId = (task.id || task._id) as string;
                            if (!realId) return;
                            toggleSelectOne(realId, e.target.checked);
                          }} checked={selectedIds.includes((task.id || task._id)!)} />
                          <div className="w-10 h-10 bg-gradient-to-br from-blue-500 to-purple-600 rounded-lg flex items-center justify-center text-white font-bold">
                            {getPlatformName(task.platform).charAt(0)}
                          </div>
                          <div className="flex-1">
                            <div className="flex flex-wrap items-center gap-2 mb-2">
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
                            onClick={() => {
                              const realId = (task.id || task._id) as string;
                              if (!realId) return;
                              handleDeleteTask(realId);
                            }}
                            disabled={deleting === (task.id || task._id)}
                            className={`p-2 rounded-lg transition-colors ${
                              deleting === (task.id || task._id)
                                ? 'text-gray-400 cursor-not-allowed'
                                : 'text-gray-400 hover:text-red-500 hover:bg-red-50'
                            }`}
                            title={deleting === (task.id || task._id) ? '删除中...' : '删除任务'}
                          >
                            {deleting === (task.id || task._id) ? (
                              <RefreshCw className="w-4 h-4 animate-spin" />
                            ) : (
                              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                              </svg>
                            )}
                          </button>
                        </div>
                      </div>

                      {/* 任务详情行 */}
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-sm text-gray-600">
                        <div className="flex items-center">
                          <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" />
                          </svg>
                          <span className="truncate">
                            {(() => {
                              const domainMap: Record<string, string> = { weibo: 'weibo.com', douyin: 'douyin.com', xiaohongshu: 'xiaohongshu.com', bilibili: 'bilibili.com', x: 'x.com', twitter: 'twitter.com' };
                              const platformDomain = domainMap[task.platform];
                              if (platformDomain) return platformDomain;
                              try { return new URL(task.url).host; } catch { return task.url; }
                            })()}
                          </span>
                        </div>
                        <div className="flex items-center">
                          <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                          </svg>
                          <span>创建时间: {new Date(task.created_at).toLocaleString('zh-CN')}</span>
                        </div>
                        {task.session_id && (
                          <div className="flex items-center">
                            <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                            </svg>
                            <span>会话ID: {task.session_id}</span>
                          </div>
                        )}
                        {task.started_at && (
                          <div className="flex items-center">
                            <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14.828 14.828a4 4 0 01-5.656 0M9 10h1m4 0h1m-7 4h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2z" />
                            </svg>
                            <span>开始时间: {new Date(task.started_at).toLocaleString('zh-CN')}</span>
                          </div>
                        )}
                        {task.updated_at && (
                          <div className="flex items-center">
                            <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                            </svg>
                            <span>更新时间: {new Date(task.updated_at).toLocaleString('zh-CN')}</span>
                          </div>
                        )}
                        {task.completed_at && (
                          <div className="flex items-center">
                            <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                            </svg>
                            <span>完成时间: {new Date(task.completed_at).toLocaleString('zh-CN')}</span>
                          </div>
                        )}
                        {task.error && (
                          <div className="flex items-center text-red-600">
                            <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                            </svg>
                            <span>错误: {task.error}</span>
                          </div>
                        )}
                      </div>
                    </div>

                    {/* 右侧：内容预览 */}
                    {task.result && (
                      <div className="lg:col-span-4">
                        <div className="p-4 bg-blue-50 rounded-lg h-full">
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
                              <p className="text-blue-700 text-sm mt-1 line-clamp-5">{task.result.content}</p>
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
                      </div>
                    )}
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