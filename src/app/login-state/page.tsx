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
  BarChart3
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
}

interface CrawlTask {
  task_id: string;
  session_id: string;
  platform: string;
  url: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  created_at: string;
  result?: Record<string, unknown>;
}

const PLATFORMS = [
  { value: 'weibo', label: '微博', icon: '🐦' },
  { value: 'xiaohongshu', label: '小红书', icon: '📖' },
  { value: 'douyin', label: '抖音', icon: '🎵' },
  { value: 'bilibili', label: '哔哩哔哩', icon: '📺' },
  { value: 'zhihu', label: '知乎', icon: '🤔' }
];

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
  const [statistics, setStatistics] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [validatingSession, setValidatingSession] = useState<string | null>(null);

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
        throw new Error(errorData.detail || errorData.message || `API call failed: ${response.statusText}`);
      }
      
      return response.json();
    } catch (error) {
      if (error instanceof TypeError && error.message.includes('fetch')) {
        throw new Error('网络连接失败，请检查服务器是否运行');
      }
      throw error;
    }
  };

  // 加载数据
  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      // 首先获取会话列表
      const sessionsData = await apiCall('/sessions?user_id=demo-user');
      const sessions = sessionsData.items || [];
      
      // 获取所有会话的浏览器实例
      let allInstances = [];
      for (const session of sessions) {
        try {
          const instancesData = await apiCall(`/browser-instances?session_id=${session.session_id}`);
          allInstances = allInstances.concat(instancesData.items || []);
        } catch (error) {
          console.warn(`Failed to load instances for session ${session.session_id}:`, error);
        }
      }
      
      const [tasksData, statsData] = await Promise.all([
        apiCall('/crawl'),
        apiCall('/stats/system')
      ]);
      
      setSessions(sessions);
       setBrowserInstances(allInstances);
       setCrawlTasks(tasksData.items || []);
       setStatistics(statsData);
    } catch (error) {
      console.error('Failed to load data:', error);
      const errorMessage = error instanceof Error ? error.message : '加载数据失败';
      setError(errorMessage);
      toast.error(errorMessage);
    } finally {
      setLoading(false);
    }
  };

  // 验证会话状态
  const validateSession = async (sessionId: string) => {
    setValidatingSession(sessionId);
    try {
      const result = await apiCall(`/sessions/${sessionId}`, {
        method: 'GET'
      });
      
      if (result.is_logged_in) {
        toast.success(`会话验证成功 - 已登录用户: ${result.login_user || '未知'}`);
      } else {
        toast.success('会话有效，可以使用浏览器实例进行登录');
      }
      
      loadData(); // 刷新数据
    } catch (error) {
      console.error('Failed to validate session:', error);
      const errorMessage = error instanceof Error ? error.message : '验证会话失败';
      toast.error(errorMessage);
    } finally {
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
      const result = await apiCall('/sessions', {
        method: 'POST',
        body: JSON.stringify({
          platform: selectedPlatform,
          user_id: 'demo-user',
          browser_config: {
            headless: false,
            viewport: { width: 1920, height: 1080 }
          }
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
      const result = await apiCall('/browser-instances', {
        method: 'POST',
        body: JSON.stringify({
          session_id: sessionId,
          headless: false,
          custom_config: {
            viewport: { width: 1920, height: 1080 }
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

      const result = await apiCall('/crawl/create', {
        method: 'POST',
        body: JSON.stringify({
          url: crawlUrl,
          session_id: selectedSession,
          extract_options: {
            extract_images: true,
            extract_links: true,
            max_posts: 10
          },
          save_to_db: true
        })
      });
      
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
      const result = await apiCall(`/crawl/${taskId}/execute`, {
        method: 'POST'
      });
      
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

  useEffect(() => {
    loadData();
  }, []);

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
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">登录状态管理</h1>
          <p className="text-muted-foreground mt-2">
            管理平台登录会话、浏览器实例和手动爬取任务
          </p>
        </div>
        <Button onClick={loadData} disabled={loading}>
          <RefreshCw className={`h-4 w-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
          刷新
        </Button>
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
                    <SelectTrigger>
                      <SelectValue placeholder="选择要登录的平台" />
                    </SelectTrigger>
                    <SelectContent>
                      {PLATFORMS.map(platform => (
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
                            {PLATFORMS.find(p => p.value === session.platform)?.icon || '🌐'}
                          </div>
                          <div>
                            <h3 className="font-semibold">
                              {PLATFORMS.find(p => p.value === session.platform)?.label || session.platform}
                            </h3>
                            <p className="text-sm text-muted-foreground">
                              会话ID: {session.session_id}
                            </p>
                            <p className="text-sm text-muted-foreground">
                              创建时间: {new Date(session.created_at).toLocaleString()}
                            </p>
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
                            onClick={() => validateSession(session.session_id)}
                            disabled={validatingSession === session.session_id}
                          >
                            <RefreshCw className={`h-4 w-4 mr-1 ${validatingSession === session.session_id ? 'animate-spin' : ''}`} />
                            验证状态
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
                              {PLATFORMS.find(p => p.value === instance.platform)?.label || instance.platform}
                            </h3>
                            <p className="text-sm text-muted-foreground">
                              实例ID: {instance.instance_id}
                            </p>
                            <p className="text-sm text-muted-foreground">
                              会话ID: {instance.session_id}
                            </p>
                            {instance.current_url && (
                              <p className="text-sm text-muted-foreground">
                                当前URL: {instance.current_url}
                              </p>
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
                      {sessions.filter(s => s.login_status).map(session => (
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
                            {PLATFORMS.find(p => p.value === task.platform)?.icon || '🌐'}
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
                              onClick={() => executeCrawlTask(task.task_id)}
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
                                        <h3>任务ID: ${task.task_id}</h3>
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