'use client';

import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Separator } from '@/components/ui/separator';
import { 
  Globe, 
  Plus, 
  Play, 
  Pause, 
  Trash2, 
  Eye, 
  Settings, 
  RefreshCw,
  CheckCircle,
  XCircle,
  Clock,
  Monitor,
  Cookie,
  Download,
  Upload,
  BarChart3,
  Bell,
  User
} from 'lucide-react';
import { toast } from 'sonner';

// 类型定义
interface Session {
  session_id: string;
  user_id: string;
  platform: string;
  status: 'active' | 'inactive' | 'expired';
  login_status: boolean;
  created_at: string;
  last_activity: string;
  expires_at: string;
  metadata: Record<string, unknown>;
  // optional fields from backend extensions
  login_user?: string;
  current_url?: string;
  last_login_check?: string;
}

interface BrowserInstance {
  instance_id: string;
  session_id: string;
  platform: string;
  status: 'running' | 'idle' | 'closed';
  created_at: string;
  last_used: string;
  current_url?: string;
  metadata: Record<string, unknown>;
  login_user?: string;
  login_status?: boolean;
}

interface CrawlTask {
  id: string;
  url: string;
  platform: string;
  priority: number;
  max_retries: number;
  status: 'pending' | 'running' | 'completed' | 'failed';
  created_at: string;
  updated_at?: string;
  result?: Record<string, unknown>;
  error?: string;
  retry_count?: number;
  task_id?: string;
}

const PLATFORMS = [
  { value: 'weibo', label: '微博', icon: '🐦' },
  { value: 'xiaohongshu', label: '小红书', icon: '📖' },
  { value: 'douyin', label: '抖音', icon: '🎵' },
  { value: 'bilibili', label: '哔哩哔哩', icon: '📺' },
  { value: 'x', label: 'X/Twitter', icon: '𝕏' },
  { value: 'zhihu', label: '知乎', icon: '🤔' },
  { value: 'custom', label: '自定义', icon: '🛠️' },
];

const PLATFORM_DISPLAY: Record<string, { label: string; icon: string }> = PLATFORMS.reduce((acc, cur) => {
  acc[cur.value] = { label: cur.label, icon: cur.icon } as { label: string; icon: string };
  return acc;
}, {} as Record<string, { label: string; icon: string }>);

function resolvePlatformDisplay(value: string, metadata?: Record<string, unknown>) {
  const alias = (metadata?.platform_alias as string) || undefined;
  if (value === 'custom' && alias && PLATFORM_DISPLAY[alias]) {
    return { value: alias, ...PLATFORM_DISPLAY[alias] };
  }
  return { value, ...(PLATFORM_DISPLAY[value] || { label: value, icon: '🌐' }) };
}

const STATUS_COLORS = {
  active: 'bg-green-100 text-green-800',
  inactive: 'bg-yellow-100 text-yellow-800',
  expired: 'bg-red-100 text-red-800',
  running: 'bg-blue-100 text-blue-800',
  idle: 'bg-gray-100 text-gray-800',
  closed: 'bg-red-100 text-red-800',
  pending: 'bg-yellow-100 text-yellow-800',
  completed: 'bg-green-100 text-green-800',
  failed: 'bg-red-100 text-red-800'
};

export default function LoginStatePage() {
  const [sessions, setSessions] = useState<Session[]>([]);
  const [browserInstances, setBrowserInstances] = useState<BrowserInstance[]>([]);
  const [crawlTasks, setCrawlTasks] = useState<CrawlTask[]>([]);
  const [loading, setLoading] = useState(false);
  const [selectedPlatform, setSelectedPlatform] = useState('');
  const [crawlUrl, setCrawlUrl] = useState('');
  const [selectedSession, setSelectedSession] = useState('');
  type Stats = {
    session_stats?: { active?: number };
    browser_stats?: { running?: number };
    crawl_stats?: { total_tasks?: number };
    system_stats?: { total_cookies?: number };
  };
  const [statistics, setStatistics] = useState<Stats | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [validatingSession, setValidatingSession] = useState<string | null>(null);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [refreshInterval, setRefreshInterval] = useState(30); // 30秒
  const [lastRefresh, setLastRefresh] = useState<Date | null>(null);
  const [checkingLoginStatus, setCheckingLoginStatus] = useState<string | null>(null);
  const [notifications, setNotifications] = useState<any[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [showNotifications, setShowNotifications] = useState(false);

  // API 调用函数
  const apiCall = async (endpoint: string, options: RequestInit = {}) => {
    try {
      const response = await fetch(`http://localhost:8001/api/login-state${endpoint}`, {
        headers: {
          'Content-Type': 'application/json',
          'X-User-ID': 'demo-user', // 实际使用时应该从认证系统获取
          ...options.headers
        },
        ...options
      });
      
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        let rawDetail: any = (errorData && (errorData.detail ?? errorData.message ?? errorData.error)) ?? '';

        // 统一把 detail 格式化成人可读字符串
        let formattedDetail = '';
        if (Array.isArray(rawDetail)) {
          formattedDetail = rawDetail
            .map((item) => {
              const loc = Array.isArray(item.loc || item.path) ? (item.loc || item.path).join('.') : (item.loc || item.path || '');
              const msg = item.msg || item.message || JSON.stringify(item);
              return loc ? `${loc}: ${msg}` : `${msg}`;
            })
            .join('; ');
        } else if (typeof rawDetail === 'object' && rawDetail) {
          formattedDetail = JSON.stringify(rawDetail);
        } else if (typeof rawDetail === 'string') {
          formattedDetail = rawDetail;
        }

        let errorMessage = formattedDetail || `API调用失败: ${response.statusText}`;

        // 根据状态码提供更具体的错误信息
        switch (response.status) {
          case 400:
            errorMessage = `请求参数错误: ${errorMessage}`;
            break;
          case 401:
            errorMessage = '身份验证失败，请重新登录';
            break;
          case 403:
            errorMessage = '权限不足，无法执行此操作';
            break;
          case 404:
            errorMessage = '请求的资源不存在';
            break;
          case 409:
            errorMessage = `操作冲突: ${errorMessage}`;
            break;
          case 422:
            errorMessage = `参数校验失败: ${errorMessage}`;
            break;
          case 429:
            errorMessage = '请求过于频繁，请稍后再试';
            break;
          case 500:
            errorMessage = '服务器内部错误，请联系管理员';
            break;
          case 502:
          case 503:
          case 504:
            errorMessage = '服务暂时不可用，请稍后重试';
            break;
          default:
            errorMessage = `网络错误 (${response.status}): ${errorMessage}`;
        }

        throw new Error(errorMessage);
      }
      
      return response.json();
    } catch (error) {
      if (error instanceof TypeError && error.message.includes('fetch')) {
        throw new Error('网络连接失败，请检查后端服务是否正常运行 (端口8001)');
      }
      if (error instanceof SyntaxError) {
        throw new Error('服务器响应格式错误，请检查后端服务状态');
      }
      throw error;
    }
  };

  // 检查会话登录状态
  const checkSessionLoginStatus = async (sessionId: string) => {
    console.log('🔍 [DEBUG] checkSessionLoginStatus called with sessionId:', sessionId);
    console.log('🔍 [DEBUG] Current checkingLoginStatus state:', checkingLoginStatus);
    
    setCheckingLoginStatus(sessionId);
    console.log('🔍 [DEBUG] Set checkingLoginStatus to:', sessionId);
    
    try {
      const apiUrl = `/sessions/${sessionId}/check-login`;
      console.log('🔍 [DEBUG] Making API call to:', apiUrl);
      console.log('🔍 [DEBUG] API call method: POST');
      
      const result: any = await apiCall(apiUrl, {
        method: 'POST'
      });
      
      console.log('🔍 [DEBUG] API response received:', result);
      console.log('🔍 [DEBUG] result.is_logged_in:', result.is_logged_in);
      console.log('🔍 [DEBUG] result.browser_instances:', result.browser_instances);
      
      if (result.is_logged_in) {
        const loginUser = result.browser_instances?.find((bi: any) => bi.login_user)?.login_user;
        console.log('🔍 [DEBUG] Found login user:', loginUser);
        const successMessage = `检测到登录状态 - 用户: ${loginUser || '未知'}`;
        console.log('🔍 [DEBUG] Showing success toast:', successMessage);
        toast.success(successMessage);
      } else {
        const infoMessage = '当前会话未检测到登录状态';
        console.log('🔍 [DEBUG] Showing info toast:', infoMessage);
        toast.info(infoMessage);
      }
      
      // 刷新数据以更新UI状态
      console.log('🔍 [DEBUG] Calling loadData(true) to refresh UI');
      loadData(true);
      
      console.log('🔍 [DEBUG] checkSessionLoginStatus completed successfully');
      return result;
    } catch (error) {
      console.error('❌ [ERROR] Failed to check login status:', error);
      console.error('❌ [ERROR] Error details:', {
        message: error instanceof Error ? error.message : 'Unknown error',
        stack: error instanceof Error ? error.stack : undefined,
        sessionId: sessionId
      });
      const errorMessage = error instanceof Error ? error.message : '检查登录状态失败';
      console.log('🔍 [DEBUG] Showing error toast:', errorMessage);
      toast.error(errorMessage);
      return null;
    } finally {
      console.log('🔍 [DEBUG] Setting checkingLoginStatus to null');
      setCheckingLoginStatus(null);
    }
  };

  // 获取通知
  const loadNotifications = async () => {
    try {
      const response = await apiCall('/notifications/default_user');
      if (response.items) {
        setNotifications(response.items);
      }
    } catch (error) {
      console.error('获取通知失败:', error);
    }
  };

  // 获取未读通知数量
  const loadUnreadCount = async () => {
    try {
      const response = await apiCall('/notifications/default_user/unread-count');
      if (response.unread_count !== undefined) {
        setUnreadCount(response.unread_count);
      }
    } catch (error) {
      console.error('获取未读通知数量失败:', error);
    }
  };

  // 标记通知为已读
  const markNotificationRead = async (notificationId: string) => {
    try {
      await apiCall(`/notifications/${notificationId}/mark-read`, {
        method: 'POST',
        headers: {
          'X-User-ID': 'default_user'
        }
      });
      await loadNotifications();
      await loadUnreadCount();
    } catch (error) {
      console.error('标记通知已读失败:', error);
    }
  };

  // 标记所有通知为已读
  const markAllNotificationsRead = async () => {
    try {
      await apiCall('/notifications/default_user/mark-all-read', {
        method: 'POST'
      });
      await loadNotifications();
      await loadUnreadCount();
      toast.success('所有通知已标记为已读');
    } catch (error) {
      console.error('标记所有通知已读失败:', error);
      toast.error('标记所有通知已读失败');
    }
  };

  // 加载数据
  const loadData = async (silent = false) => {
    if (!silent) {
      setLoading(true);
    }
    setError(null);
    try {
      // 首先获取会话列表
      const sessionsData: any = await apiCall('/sessions?user_id=demo-user');
      const sessions: Session[] = sessionsData.items || [];
      
      // 获取所有会话的浏览器实例
      let allInstances: BrowserInstance[] = [];
      for (const session of sessions) {
        try {
          const instancesData = await apiCall(`/browser-instances?session_id=${session.session_id}`);
          allInstances = allInstances.concat((instancesData.items || []) as BrowserInstance[]);
        } catch (error) {
          console.warn(`Failed to load instances for session ${session.session_id}:`, error);
        }
      }
      
      // 获取异步任务调度系统的任务数据
      const tasksResponse = await fetch('http://localhost:8081/api/tasks', {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        }
      });
      
      let tasksData: { items: CrawlTask[] } = { items: [] };
      if (tasksResponse.ok) {
        tasksData = await tasksResponse.json();
      }
      
      const statsData: Stats = await apiCall('/stats/system');
      
      setSessions(sessions);
      setBrowserInstances(allInstances);
      setCrawlTasks(tasksData.items || []);
      setStatistics(statsData);
      setLastRefresh(new Date());
      
      // 加载通知数据
      await loadNotifications();
      await loadUnreadCount();
    } catch (error) {
      console.error('Failed to load data:', error);
      const errorMessage = error instanceof Error ? error.message : '加载数据失败';
      setError(errorMessage);
      if (!silent) {
        toast.error(errorMessage);
      }
    } finally {
      if (!silent) {
        setLoading(false);
      }
    }
  };

  // 验证会话状态
  const validateSession = async (sessionId: string) => {
    console.log('✅ [DEBUG] validateSession called with sessionId:', sessionId);
    console.log('✅ [DEBUG] Current validatingSession state:', validatingSession);
    
    setValidatingSession(sessionId);
    console.log('✅ [DEBUG] Set validatingSession to:', sessionId);
    
    try {
      const apiUrl = `/sessions/${sessionId}`;
      console.log('✅ [DEBUG] Making API call to:', apiUrl);
      console.log('✅ [DEBUG] API call method: GET');
      
      const result = await apiCall(apiUrl, {
        method: 'GET'
      });
      
      console.log('✅ [DEBUG] API response received:', result);
      console.log('✅ [DEBUG] result.is_logged_in:', result.is_logged_in);
      console.log('✅ [DEBUG] result.login_user:', result.login_user);
      
      if (result.is_logged_in) {
        const successMessage = `会话验证成功 - 已登录用户: ${result.login_user || '未知'}`;
        console.log('✅ [DEBUG] Showing success toast (logged in):', successMessage);
        toast.success(successMessage);
      } else {
        const successMessage = '会话有效，可以使用浏览器实例进行登录';
        console.log('✅ [DEBUG] Showing success toast (not logged in):', successMessage);
        toast.success(successMessage);
      }
      
      console.log('✅ [DEBUG] Calling loadData() to refresh UI');
      loadData(); // 刷新数据
      console.log('✅ [DEBUG] validateSession completed successfully');
    } catch (error) {
      console.error('❌ [ERROR] Failed to validate session:', error);
      console.error('❌ [ERROR] Error details:', {
        message: error instanceof Error ? error.message : 'Unknown error',
        stack: error instanceof Error ? error.stack : undefined,
        sessionId: sessionId
      });
      const errorMessage = error instanceof Error ? error.message : '验证会话失败';
      console.log('✅ [DEBUG] Showing error toast:', errorMessage);
      toast.error(errorMessage);
    } finally {
      console.log('✅ [DEBUG] Setting validatingSession to null');
      setValidatingSession(null);
    }
  };

  // 创建会话
  const createSession = async () => {
    if (!selectedPlatform) {
      toast.error('请选择平台');
      return;
    }

    try {
      const isX = selectedPlatform === 'x';
      const result = await apiCall('/sessions', {
        method: 'POST',
        body: JSON.stringify({
          platform: isX ? 'custom' : selectedPlatform,
          user_id: 'demo-user',
          browser_config: {
            headless: false,
            viewport: { width: 1920, height: 1080 }
          },
          // 传递别名，后端将持久化到 session.metadata
          metadata: isX ? { platform_alias: 'x' } : undefined
        })
      });
      
      toast.success('会话创建成功');
      setSelectedPlatform('');
      loadData();
    } catch (error) {
      console.error('Failed to create session:', error);
      toast.error('创建会话失败');
    }
  };

  // 创建浏览器实例
  const createBrowserInstance = async (sessionId: string) => {
    try {
      // 从会话中取平台与别名，若自定义且别名为x，则传递默认首页
      const session = sessions.find(s => s.session_id === sessionId);
      const alias = session?.metadata?.platform_alias as string | undefined;
      const defaultUrl = (session?.platform === 'custom' && alias === 'x') ? 'https://x.com' : undefined;

      const result = await apiCall('/browser-instances', {
        method: 'POST',
        body: JSON.stringify({
          session_id: sessionId,
          headless: false,
          custom_config: {
            viewport: { width: 1920, height: 1080 },
            ...(defaultUrl ? { default_url: defaultUrl } : {})
          }
        })
      });
      
      toast.success('浏览器实例创建成功');
      loadData();
    } catch (error) {
      console.error('Failed to create browser instance:', error);
      toast.error('创建浏览器实例失败');
    }
  };

  // 导航到URL
  const navigateToUrl = async (instanceId: string, url: string) => {
    try {
      await apiCall(`/browser-instances/${instanceId}/navigate`, {
        method: 'POST',
        body: JSON.stringify({ 
          url: url 
        })
      });
      
      toast.success('导航成功');
      loadData();
    } catch (error) {
      console.error('Failed to navigate:', error);
      toast.error('导航失败');
    }
  };

  // 直接抽取当前浏览器实例页面（调用 Python Login-State 手动爬取接口）
  const extractCurrentPage = async (instance: BrowserInstance) => {
    try {
      if (!instance.current_url) {
        toast.error('实例当前页为空，请先导航到目标帖子URL');
        return;
      }

      // 1) 创建手动爬取任务
      const createResp = await apiCall('/crawl/create', {
        method: 'POST',
        body: JSON.stringify({
          session_id: instance.session_id,
          url: instance.current_url,
          extract_content: true,
          extract_links: true,
          extract_images: true,
          wait_time: 2,
          scroll_to_bottom: false
        })
      });

      const taskId = createResp.task_id;
      if (!taskId) {
        toast.error('创建抽取任务失败');
        return;
      }

      // 2) 立即执行
      const execResp = await apiCall(`/crawl/${taskId}/execute`, { method: 'POST' });
      toast.success('抽取完成，结果已生成');
      console.log('Extract result:', execResp);
    } catch (error) {
      console.error('Failed to extract current page:', error);
      toast.error(error instanceof Error ? error.message : '抽取失败');
    }
  };

  // 创建爬取任务
  const createCrawlTask = async () => {
    if (!selectedSession || !crawlUrl) {
      toast.error('请选择会话和输入URL');
      return;
    }

    try {
      const session = sessions.find(s => s.session_id === selectedSession);
      if (!session) {
        toast.error('会话不存在');
        return;
      }

      // 调用Go后端的异步任务调度API
      const response = await fetch('http://localhost:8081/api/tasks/create', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          url: crawlUrl,
          platform: selectedPlatform || 'weibo',
          session_id: selectedSession,
          priority: 5,
          max_retries: 3,
          metadata: {
            extract_images: true,
            extract_links: true,
            max_posts: 10,
            save_to_db: true
          }
        })
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const result = await response.json();
      
      toast.success('爬取任务创建成功');
      setCrawlUrl('');
      setSelectedSession('');
      loadData();
    } catch (error) {
      console.error('Failed to create crawl task:', error);
      toast.error('创建爬取任务失败');
    }
  };

  // 执行爬取任务
  const executeCrawlTask = async (taskId: string) => {
    try {
      // 调用Go后端的任务执行API
      const response = await fetch(`http://localhost:8081/api/tasks/${taskId}/execute`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        }
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const result = await response.json();
      
      toast.success('爬取任务执行成功');
      loadData();
    } catch (error) {
      console.error('Failed to execute crawl task:', error);
      toast.error('执行爬取任务失败');
    }
  };

  // 删除会话
  const deleteSession = async (sessionId: string) => {
    try {
      await apiCall(`/sessions/${sessionId}`, {
        method: 'DELETE'
      });
      
      toast.success('会话删除成功');
      loadData();
    } catch (error) {
      console.error('Failed to delete session:', error);
      toast.error('删除会话失败');
    }
  };

  // 关闭浏览器实例
  const closeBrowserInstance = async (instanceId: string) => {
    try {
      await apiCall(`/browser-instances/${instanceId}`, {
        method: 'DELETE'
      });
      
      toast.success('浏览器实例关闭成功');
      loadData();
    } catch (error) {
      console.error('Failed to close browser instance:', error);
      toast.error('关闭浏览器实例失败');
    }
  };

  // 初始化和定时刷新
  useEffect(() => {
    loadData();
  }, []);

  // 自动刷新机制
  useEffect(() => {
    if (!autoRefresh) return;

    const interval = setInterval(() => {
      loadData(true); // 静默刷新，不显示loading状态
    }, refreshInterval * 1000);

    return () => clearInterval(interval);
  }, [autoRefresh, refreshInterval]);

  // 定期检查活跃会话的登录状态
  useEffect(() => {
    if (!autoRefresh) return;

    const loginCheckInterval = setInterval(async () => {
      const activeSessions = sessions.filter(s => s.status === 'active' && !s.login_status);
      
      for (const session of activeSessions) {
        try {
          await checkSessionLoginStatus(session.session_id);
          // 添加延迟避免过于频繁的请求
          await new Promise(resolve => setTimeout(resolve, 1000));
        } catch (error) {
          console.warn(`Failed to check login status for session ${session.session_id}:`, error);
        }
      }
    }, 60000); // 每分钟检查一次登录状态

    return () => clearInterval(loginCheckInterval);
  }, [autoRefresh, sessions]);

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'active':
      case 'running':
      case 'completed':
        return <CheckCircle className="h-4 w-4" />;
      case 'inactive':
      case 'idle':
      case 'pending':
        return <Clock className="h-4 w-4" />;
      case 'expired':
      case 'closed':
      case 'failed':
        return <XCircle className="h-4 w-4" />;
      default:
        return <Clock className="h-4 w-4" />;
    }
  };

  return (
    <div className="container mx-auto p-6 space-y-6">
      {/* 错误状态显示 */}
      {error && (
        <Alert className="border-red-200 bg-red-50">
          <XCircle className="h-4 w-4 text-red-600" />
          <AlertDescription className="text-red-800">
            <div className="flex items-center justify-between">
              <span>{error}</span>
              <Button 
                variant="outline" 
                size="sm" 
                onClick={() => {
                  setError(null);
                  loadData();
                }}
                className="ml-4 border-red-300 text-red-700 hover:bg-red-100"
              >
                <RefreshCw className="h-3 w-3 mr-1" />
                重试
              </Button>
            </div>
          </AlertDescription>
        </Alert>
      )}
      
      {/* 操作指导 */}
      {sessions.length === 0 && !loading && !error && (
        <Alert className="border-blue-200 bg-blue-50">
          <Settings className="h-4 w-4 text-blue-600" />
          <AlertDescription className="text-blue-800">
            <div>
              <p className="font-medium mb-2">开始使用登录状态管理系统：</p>
              <ol className="list-decimal list-inside space-y-1 text-sm">
                <li>创建新的会话（选择目标平台）</li>
                <li>打开浏览器实例</li>
                <li>在浏览器中手动登录目标平台</li>
                <li>点击"检查登录"验证登录状态</li>
                <li>创建并执行爬取任务</li>
              </ol>
            </div>
          </AlertDescription>
        </Alert>
      )}
      
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">登录状态管理</h1>
          <p className="text-muted-foreground mt-2">
            管理浏览器会话、检测登录状态并执行手动爬取任务
          </p>
          {lastRefresh && (
            <p className="text-xs text-muted-foreground mt-1">
              最后更新: {lastRefresh.toLocaleTimeString()}
            </p>
          )}
        </div>
        <div className="flex items-center space-x-4">
          {/* 自动刷新控制 */}
          <div className="flex items-center space-x-2">
            <Label htmlFor="auto-refresh" className="text-sm">
              自动刷新
            </Label>
            <input
              id="auto-refresh"
              type="checkbox"
              checked={autoRefresh}
              onChange={(e) => setAutoRefresh(e.target.checked)}
              className="rounded"
            />
            {autoRefresh && (
              <Select value={refreshInterval.toString()} onValueChange={(value) => setRefreshInterval(parseInt(value))}>
                <SelectTrigger className="w-20">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="15">15s</SelectItem>
                  <SelectItem value="30">30s</SelectItem>
                  <SelectItem value="60">60s</SelectItem>
                  <SelectItem value="120">2m</SelectItem>
                </SelectContent>
              </Select>
            )}
          </div>
          <Button onClick={() => loadData()} disabled={loading}>
            <RefreshCw className={`h-4 w-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
            手动刷新
          </Button>
          
          {/* 系统状态指示器 */}
          <div className="flex items-center gap-2">
            <div className={`h-2 w-2 rounded-full ${
              error ? 'bg-red-500' : 'bg-green-500'
            }`} />
            <span className="text-sm text-muted-foreground">
              {error ? '服务异常' : '服务正常'}
            </span>
          </div>
          
          {/* 通知按钮 */}
          <div className="relative">
            <Button
              onClick={() => setShowNotifications(!showNotifications)}
              variant="outline"
              className="relative"
            >
              <Bell className="h-4 w-4 mr-2" />
              通知
              {unreadCount > 0 && (
                <span className="absolute -top-2 -right-2 bg-red-500 text-white text-xs rounded-full h-5 w-5 flex items-center justify-center">
                  {unreadCount > 99 ? '99+' : unreadCount}
                </span>
              )}
            </Button>
            
            {/* 通知下拉菜单 */}
            {showNotifications && (
              <div className="absolute right-0 mt-2 w-80 bg-white border border-gray-200 rounded-lg shadow-lg z-50">
                <div className="p-4 border-b border-gray-200 flex justify-between items-center">
                  <h3 className="font-semibold text-gray-900">通知</h3>
                  {unreadCount > 0 && (
                    <Button
                      onClick={markAllNotificationsRead}
                      variant="ghost"
                      size="sm"
                      className="text-sm text-blue-600 hover:text-blue-800"
                    >
                      全部标记已读
                    </Button>
                  )}
                </div>
                <div className="max-h-96 overflow-y-auto">
                  {notifications.length === 0 ? (
                    <div className="p-4 text-center text-gray-500">
                      暂无通知
                    </div>
                  ) : (
                    notifications.map((notification) => (
                      <div
                        key={notification._id}
                        className={`p-4 border-b border-gray-100 hover:bg-gray-50 cursor-pointer ${
                          !notification.read ? 'bg-blue-50' : ''
                        }`}
                        onClick={() => !notification.read && markNotificationRead(notification._id)}
                      >
                        <div className="flex justify-between items-start">
                          <div className="flex-1">
                            <p className={`text-sm ${!notification.read ? 'font-semibold text-gray-900' : 'text-gray-700'}`}>
                              {notification.message}
                            </p>
                            <p className="text-xs text-gray-500 mt-1">
                              {new Date(notification.timestamp).toLocaleString()}
                            </p>
                            {notification.platform && (
                              <span className="inline-block mt-1 px-2 py-1 text-xs bg-gray-100 text-gray-600 rounded">
                                {notification.platform}
                              </span>
                            )}
                          </div>
                          {!notification.read && (
                            <div className="w-2 h-2 bg-blue-500 rounded-full ml-2 mt-1"></div>
                          )}
                        </div>
                      </div>
                    ))
                  )}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* 错误提示 */}
      {error && (
        <Alert variant="destructive">
          <XCircle className="h-4 w-4" />
          <AlertDescription>
            {error}
          </AlertDescription>
        </Alert>
      )}

      {/* 统计信息 */}
      {statistics && (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <Card>
            <CardContent className="p-4">
              <div className="flex items-center space-x-2">
                <Globe className="h-5 w-5 text-blue-500" />
                <div>
                  <p className="text-sm text-muted-foreground">活跃会话</p>
                  <p className="text-2xl font-bold">{statistics.session_stats?.active || 0}</p>
                </div>
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="p-4">
              <div className="flex items-center space-x-2">
                <Monitor className="h-5 w-5 text-green-500" />
                <div>
                  <p className="text-sm text-muted-foreground">浏览器实例</p>
                  <p className="text-2xl font-bold">{statistics.browser_stats?.running || 0}</p>
                </div>
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="p-4">
              <div className="flex items-center space-x-2">
                <BarChart3 className="h-5 w-5 text-purple-500" />
                <div>
                  <p className="text-sm text-muted-foreground">爬取任务</p>
                  <p className="text-2xl font-bold">{statistics.crawl_stats?.total_tasks || 0}</p>
                </div>
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="p-4">
              <div className="flex items-center space-x-2">
                <Cookie className="h-5 w-5 text-orange-500" />
                <div>
                  <p className="text-sm text-muted-foreground">存储的Cookie</p>
                  <p className="text-2xl font-bold">{statistics.system_stats?.total_cookies || 0}</p>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      <Tabs defaultValue="sessions" className="space-y-4">
        <TabsList>
          <TabsTrigger value="sessions">会话管理</TabsTrigger>
          <TabsTrigger value="browsers">浏览器实例</TabsTrigger>
          <TabsTrigger value="crawl">手动爬取</TabsTrigger>
        </TabsList>

        {/* 会话管理 */}
        <TabsContent value="sessions" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>创建新会话</CardTitle>
              <CardDescription>
                为指定平台创建登录会话，用于后续的浏览器操作和内容爬取
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex space-x-4">
                <div className="flex-1">
                  <Label htmlFor="platform">选择平台</Label>
                  <Select value={selectedPlatform} onValueChange={setSelectedPlatform}>
                    <SelectTrigger className="w-64">
                      <SelectValue placeholder="选择要登录的平台" />
                    </SelectTrigger>
                    <SelectContent className="w-64">
                      {PLATFORMS.filter(p => p.value !== 'custom').map(platform => (
                        <SelectItem key={platform.value} value={platform.value}>
                          {platform.icon} {platform.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="flex items-end">
                  <Button onClick={createSession} disabled={!selectedPlatform || loading}>
                    <Plus className="h-4 w-4 mr-2" />
                    {loading ? '创建中...' : '创建会话'}
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>会话列表</CardTitle>
              <CardDescription>
                管理所有平台的登录会话状态
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {sessions.length === 0 ? (
                  <Alert>
                    <AlertDescription>
                      暂无会话，请先创建一个新会话
                    </AlertDescription>
                  </Alert>
                ) : (
                  sessions.map(session => (
                    <div key={session.session_id} className="border rounded-lg p-4">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center space-x-4">
                          <div className="text-2xl">
                            {resolvePlatformDisplay(session.platform, session.metadata).icon}
                          </div>
                          <div>
                            <h3 className="font-semibold">
                              {resolvePlatformDisplay(session.platform, session.metadata).label}
                            </h3>
                            <p className="text-sm text-muted-foreground">
                              会话ID: {session.session_id}
                            </p>
                            <p className="text-sm text-muted-foreground">
                              创建时间: {new Date(session.created_at).toLocaleString()}
                            </p>
                            {session.login_user && (
                              <p className="text-sm text-green-600 font-medium">
                                登录用户: {session.login_user}
                              </p>
                            )}
                            {session.current_url && (
                              <p className="text-sm text-blue-600">
                                当前页面: {session.current_url.length > 50 ? session.current_url.substring(0, 50) + '...' : session.current_url}
                              </p>
                            )}
                            {session.last_login_check && (
                              <p className="text-sm text-muted-foreground">
                                最后检查: {new Date(session.last_login_check).toLocaleString()}
                              </p>
                            )}
                          </div>
                        </div>
                        <div className="flex items-center space-x-2">
                          <Badge className={STATUS_COLORS[session.status]}>
                            {getStatusIcon(session.status)}
                            <span className="ml-1">{session.status}</span>
                          </Badge>
                          <Badge variant={session.login_status ? 'default' : 'secondary'}>
                            {session.login_status ? '已登录' : '未登录'}
                          </Badge>
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => {
                              console.log('🔘 [BUTTON] 验证状态 button clicked for session:', session.session_id);
                              console.log('🔘 [BUTTON] Current validatingSession state:', validatingSession);
                              console.log('🔘 [BUTTON] Button disabled state:', validatingSession === session.session_id);
                              validateSession(session.session_id);
                            }}
                            disabled={validatingSession === session.session_id}
                          >
                            <RefreshCw className={`h-4 w-4 mr-1 ${validatingSession === session.session_id ? 'animate-spin' : ''}`} />
                            验证状态
                          </Button>
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => {
                              console.log('🔘 [BUTTON] 检查登录 button clicked for session:', session.session_id);
                              console.log('🔘 [BUTTON] Current checkingLoginStatus state:', checkingLoginStatus);
                              console.log('🔘 [BUTTON] Button disabled state:', checkingLoginStatus === session.session_id);
                              checkSessionLoginStatus(session.session_id);
                            }}
                            disabled={checkingLoginStatus === session.session_id}
                          >
                            <Eye className={`h-4 w-4 mr-1 ${checkingLoginStatus === session.session_id ? 'animate-spin' : ''}`} />
                            检查登录
                          </Button>
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => createBrowserInstance(session.session_id)}
                            disabled={loading}
                          >
                            <Monitor className="h-4 w-4 mr-1" />
                            打开浏览器
                          </Button>
                          <Button
                            size="sm"
                            variant="destructive"
                            onClick={() => deleteSession(session.session_id)}
                            disabled={loading}
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </div>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* 浏览器实例 */}
        <TabsContent value="browsers" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>浏览器实例</CardTitle>
              <CardDescription>
                管理所有活跃的浏览器实例，用于手动登录和页面操作
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {browserInstances.length === 0 ? (
                  <Alert>
                    <AlertDescription>
                      暂无浏览器实例，请先创建会话并打开浏览器
                    </AlertDescription>
                  </Alert>
                ) : (
                  browserInstances.map(instance => (
                    <div key={instance.instance_id} className="border rounded-lg p-4">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center space-x-4">
                          <Monitor className="h-8 w-8 text-blue-500" />
                          <div>
                            <h3 className="font-semibold">
                              {resolvePlatformDisplay(instance.platform, instance.metadata).label}
                            </h3>
                            <p className="text-sm text-muted-foreground">
                              实例ID: {instance.instance_id}
                            </p>
                            <p className="text-sm text-muted-foreground">
                              会话ID: {instance.session_id}
                            </p>
                            {instance.current_url && (
                              <p className="text-sm text-blue-600">
                                当前URL: {instance.current_url.length > 60 ? instance.current_url.substring(0, 60) + '...' : instance.current_url}
                              </p>
                            )}
                            {instance.login_user && (
                              <p className="text-sm text-green-600 font-medium">
                                登录用户: {instance.login_user}
                              </p>
                            )}
                            {instance.login_status && (
                              <Badge variant="default" className="mt-1">
                                <User className="h-3 w-3 mr-1" />
                                已登录
                              </Badge>
                            )}
                          </div>
                        </div>
                        <div className="flex items-center space-x-2">
                          <Badge className={STATUS_COLORS[instance.status]}>
                            {getStatusIcon(instance.status)}
                            <span className="ml-1">{instance.status}</span>
                          </Badge>
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => {
                              const url = prompt('请输入要导航的URL:');
                              if (url) {
                                navigateToUrl(instance.instance_id, url);
                              }
                            }}
                            disabled={loading || instance.status !== 'running'}
                          >
                            <Globe className="h-4 w-4 mr-1" />
                            导航
                          </Button>
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => extractCurrentPage(instance)}
                            disabled={loading || instance.status !== 'running'}
                          >
                            <BarChart3 className="h-4 w-4 mr-1" />
                            抽取当前页
                          </Button>
                          <Button
                            size="sm"
                            variant="destructive"
                            onClick={() => closeBrowserInstance(instance.instance_id)}
                            disabled={loading}
                          >
                            <XCircle className="h-4 w-4" />
                          </Button>
                        </div>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* 手动爬取 */}
        <TabsContent value="crawl" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>创建爬取任务</CardTitle>
              <CardDescription>
                基于已登录的会话创建手动爬取任务
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div>
                  <Label htmlFor="session">选择会话</Label>
                  <Select value={selectedSession} onValueChange={setSelectedSession}>
                    <SelectTrigger>
                      <SelectValue placeholder="选择已登录的会话" />
                    </SelectTrigger>
                    <SelectContent>
                      {sessions.filter((s: Session) => s.login_status).map((session: Session) => (
                        <SelectItem key={session.session_id} value={session.session_id}>
                          {PLATFORMS.find(p => p.value === session.platform)?.icon} {' '}
                          {PLATFORMS.find(p => p.value === session.platform)?.label} - {session.session_id.slice(0, 8)}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div>
                  <Label htmlFor="crawl-url">目标URL</Label>
                  <Input
                    id="crawl-url"
                    value={crawlUrl}
                    onChange={(e) => setCrawlUrl(e.target.value)}
                    placeholder="输入要爬取的页面URL"
                  />
                </div>
                <div className="flex items-end">
                  <Button onClick={createCrawlTask} disabled={!selectedSession || !crawlUrl || loading}>
                    <Plus className="h-4 w-4 mr-2" />
                    {loading ? '创建中...' : '创建任务'}
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>爬取任务列表</CardTitle>
              <CardDescription>
                查看和管理所有爬取任务的执行状态
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {crawlTasks.length === 0 ? (
                  <Alert>
                    <AlertDescription>
                      暂无爬取任务，请先创建一个新任务
                    </AlertDescription>
                  </Alert>
                ) : (
                  crawlTasks.map(task => (
                    <div key={task.task_id} className="border rounded-lg p-4">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center space-x-4">
                          <div className="text-2xl">
                            {resolvePlatformDisplay(task.platform, (task as any).result as any)?.icon || '🌐'}
                          </div>
                          <div>
                            <h3 className="font-semibold">
                              {task.url}
                            </h3>
                            <p className="text-sm text-muted-foreground">
                              任务ID: {task.task_id}
                            </p>
                            <p className="text-sm text-muted-foreground">
                              创建时间: {new Date(task.created_at).toLocaleString()}
                            </p>
                          </div>
                        </div>
                        <div className="flex items-center space-x-2">
                          <Badge className={STATUS_COLORS[task.status]}>
                            {getStatusIcon(task.status)}
                            <span className="ml-1">{task.status}</span>
                          </Badge>
                          {task.status === 'pending' && (
                            <Button
                              size="sm"
                              onClick={() => executeCrawlTask(task.id)}
                              disabled={loading}
                            >
                              <Play className="h-4 w-4 mr-1" />
                              执行
                            </Button>
                          )}
                          {task.status === 'running' && (
                            <Button
                              size="sm"
                              variant="outline"
                              disabled
                            >
                              <RefreshCw className="h-4 w-4 mr-1 animate-spin" />
                              执行中
                            </Button>
                          )}
                          {task.result && (
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => {
                                // 显示爬取结果的详细信息
                                const resultWindow = window.open('', '_blank');
                                if (resultWindow) {
                                  resultWindow.document.write(`
                                    <html>
                                      <head><title>爬取结果 - ${task.task_id}</title></head>
                                      <body>
                                        <h1>爬取结果</h1>
                                        <h2>URL: ${task.url}</h2>
                                        <h3>任务ID: ${task.id}</h3>
                                        <pre>${JSON.stringify(task.result, null, 2)}</pre>
                                      </body>
                                    </html>
                                  `);
                                  resultWindow.document.close();
                                } else {
                                  console.log('Crawl result:', task.result);
                                  toast.success('结果已在控制台显示（弹窗被阻止）');
                                }
                              }}
                            >
                              <Eye className="h-4 w-4 mr-1" />
                              查看结果
                            </Button>
                          )}
                        </div>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}