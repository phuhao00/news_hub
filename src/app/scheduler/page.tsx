'use client';

import React, { useState, useEffect } from 'react';
import { taskScheduler, ScheduledTask, TaskStatus, TaskType, TaskExecution } from '@/lib/scheduler';
import { useToast } from '@/components/Toast';

interface TaskFormData {
  name: string;
  description: string;
  type: TaskType;
  scheduleType: 'interval' | 'cron' | 'once';
  scheduleExpression: string;
  platform: string;
  creatorUrl: string;
  limit: number;
  priority: number;
}

export default function SchedulerPage() {
  const [tasks, setTasks] = useState<ScheduledTask[]>([]);
  const [selectedTask, setSelectedTask] = useState<ScheduledTask | null>(null);
  const [showAddForm, setShowAddForm] = useState(false);
  const [executions, setExecutions] = useState<TaskExecution[]>([]);
  const [refreshInterval, setRefreshInterval] = useState<NodeJS.Timeout | null>(null);
  const { addToast } = useToast();

  // 表单数据
  const [formData, setFormData] = useState<TaskFormData>({
    name: '',
    description: '',
    type: TaskType.CRAWLER,
    scheduleType: 'interval',
    scheduleExpression: '3600000', // 1小时
    platform: 'weibo',
    creatorUrl: '',
    limit: 20,
    priority: 5,
  });

  // 加载任务列表
  const loadTasks = () => {
    const allTasks = taskScheduler.getAllTasks();
    setTasks(allTasks);
  };

  // 加载执行记录
  const loadExecutions = (taskId: string) => {
    const taskExecutions = taskScheduler.getTaskExecutions(taskId);
    setExecutions(taskExecutions);
  };

  useEffect(() => {
    loadTasks();
    
    // 设置自动刷新
    const interval = setInterval(() => {
      loadTasks();
      if (selectedTask) {
        loadExecutions(selectedTask.id);
      }
    }, 2000);
    
    setRefreshInterval(interval);
    
    return () => {
      if (interval) clearInterval(interval);
    };
  }, [selectedTask]);

  // 创建任务
  const handleCreateTask = () => {
    try {
      const taskId = taskScheduler.addTask({
        name: formData.name,
        description: formData.description,
        type: formData.type,
        status: TaskStatus.PENDING,
        schedule: {
          type: formData.scheduleType,
          expression: formData.scheduleExpression,
        },
        config: {
          platform: formData.platform,
          creatorUrl: formData.creatorUrl,
          limit: formData.limit,
        },
        createdBy: 'current-user', // 实际项目中从认证上下文获取
        enabled: true,
        priority: formData.priority,
      });

      addToast({
        type: 'success',
        title: '任务创建成功',
        message: `任务 "${formData.name}" 已创建`,
      });

      setShowAddForm(false);
      setFormData({
        name: '',
        description: '',
        type: TaskType.CRAWLER,
        scheduleType: 'interval',
        scheduleExpression: '3600000',
        platform: 'weibo',
        creatorUrl: '',
        limit: 20,
        priority: 5,
      });
      loadTasks();
    } catch (error) {
      addToast({
        type: 'error',
        title: '创建失败',
        message: error instanceof Error ? error.message : '未知错误',
      });
    }
  };

  // 执行任务
  const handleExecuteTask = async (taskId: string) => {
    try {
      await taskScheduler.executeTask(taskId);
      addToast({
        type: 'success',
        title: '任务已启动',
        message: '任务正在执行中',
      });
    } catch (error) {
      addToast({
        type: 'error',
        title: '执行失败',
        message: error instanceof Error ? error.message : '未知错误',
      });
    }
  };

  // 暂停/恢复任务
  const handleToggleTask = (task: ScheduledTask) => {
    if (task.enabled) {
      taskScheduler.pauseTask(task.id);
      addToast({
        type: 'info',
        title: '任务已暂停',
        message: `任务 "${task.name}" 已暂停执行`,
      });
    } else {
      taskScheduler.resumeTask(task.id);
      addToast({
        type: 'success',
        title: '任务已恢复',
        message: `任务 "${task.name}" 已恢复执行`,
      });
    }
    loadTasks();
  };

  // 删除任务
  const handleDeleteTask = (taskId: string) => {
    if (confirm('确定要删除这个任务吗？')) {
      taskScheduler.removeTask(taskId);
      addToast({
        type: 'success',
        title: '任务已删除',
      });
      if (selectedTask?.id === taskId) {
        setSelectedTask(null);
      }
      loadTasks();
    }
  };

  // 获取状态颜色
  const getStatusColor = (status: TaskStatus) => {
    switch (status) {
      case TaskStatus.RUNNING:
        return 'text-blue-600 bg-blue-100';
      case TaskStatus.COMPLETED:
        return 'text-green-600 bg-green-100';
      case TaskStatus.FAILED:
        return 'text-red-600 bg-red-100';
      case TaskStatus.PAUSED:
        return 'text-yellow-600 bg-yellow-100';
      case TaskStatus.CANCELLED:
        return 'text-gray-600 bg-gray-100';
      default:
        return 'text-gray-600 bg-gray-100';
    }
  };

  // 获取类型名称
  const getTypeName = (type: TaskType) => {
    switch (type) {
      case TaskType.CRAWLER:
        return '内容爬取';
      case TaskType.VIDEO_GENERATION:
        return '视频生成';
      case TaskType.PUBLISHING:
        return '内容发布';
      case TaskType.DATA_CLEANUP:
        return '数据清理';
      default:
        return type;
    }
  };

  // 格式化调度表达式
  const formatSchedule = (schedule: ScheduledTask['schedule']) => {
    switch (schedule.type) {
      case 'interval':
        const ms = parseInt(schedule.expression);
        const minutes = Math.floor(ms / (1000 * 60));
        const hours = Math.floor(minutes / 60);
        if (hours >= 1) {
          return `每 ${hours} 小时`;
        } else {
          return `每 ${minutes} 分钟`;
        }
      case 'cron':
        return `Cron: ${schedule.expression}`;
      case 'once':
        return `单次: ${new Date(schedule.expression).toLocaleString()}`;
      default:
        return schedule.expression;
    }
  };

  return (
    <div className="container mx-auto px-4 py-8">
      <div className="mb-8">
        <div className="flex justify-between items-center mb-6">
          <div>
            <h1 className="text-3xl font-bold text-gray-900">定时任务管理</h1>
            <p className="text-gray-600 mt-2">管理和监控定时爬取任务的执行进度</p>
          </div>
          <button
            onClick={() => setShowAddForm(true)}
            className="bg-orange-500 hover:bg-orange-600 text-white px-6 py-2 rounded-lg font-medium transition-colors"
          >
            + 新建任务
          </button>
        </div>

        {/* 统计卡片 */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
          <div className="bg-white rounded-lg shadow p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-gray-600 text-sm">总任务数</p>
                <p className="text-2xl font-bold text-gray-900">{tasks.length}</p>
              </div>
              <div className="w-12 h-12 bg-blue-100 rounded-lg flex items-center justify-center">
                <svg className="w-6 h-6 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v10a2 2 0 002 2h8a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012-2" />
                </svg>
              </div>
            </div>
          </div>

          <div className="bg-white rounded-lg shadow p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-gray-600 text-sm">运行中</p>
                <p className="text-2xl font-bold text-blue-600">
                  {tasks.filter(t => t.status === TaskStatus.RUNNING).length}
                </p>
              </div>
              <div className="w-12 h-12 bg-blue-100 rounded-lg flex items-center justify-center">
                <svg className="w-6 h-6 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14.828 14.828a4 4 0 01-5.656 0M9 10h1m4 0h1m-6 4h.01M19 10a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              </div>
            </div>
          </div>

          <div className="bg-white rounded-lg shadow p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-gray-600 text-sm">已完成</p>
                <p className="text-2xl font-bold text-green-600">
                  {tasks.reduce((sum, t) => sum + t.execution.successfulRuns, 0)}
                </p>
              </div>
              <div className="w-12 h-12 bg-green-100 rounded-lg flex items-center justify-center">
                <svg className="w-6 h-6 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              </div>
            </div>
          </div>

          <div className="bg-white rounded-lg shadow p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-gray-600 text-sm">失败次数</p>
                <p className="text-2xl font-bold text-red-600">
                  {tasks.reduce((sum, t) => sum + t.execution.failedRuns, 0)}
                </p>
              </div>
              <div className="w-12 h-12 bg-red-100 rounded-lg flex items-center justify-center">
                <svg className="w-6 h-6 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* 任务列表 */}
        <div className="lg:col-span-2">
          <div className="bg-white rounded-lg shadow">
            <div className="p-6 border-b border-gray-200">
              <h2 className="text-xl font-semibold text-gray-900">任务列表</h2>
            </div>
            <div className="p-6">
              {tasks.length === 0 ? (
                <div className="text-center py-8">
                  <svg className="w-16 h-16 text-gray-400 mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v10a2 2 0 002 2h8a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012-2" />
                  </svg>
                  <p className="text-gray-600 mb-4">暂无定时任务</p>
                  <button
                    onClick={() => setShowAddForm(true)}
                    className="bg-orange-500 hover:bg-orange-600 text-white px-4 py-2 rounded-lg font-medium"
                  >
                    创建第一个任务
                  </button>
                </div>
              ) : (
                <div className="space-y-4">
                  {tasks.map((task) => (
                    <div
                      key={task.id}
                      className={`border rounded-lg p-4 cursor-pointer transition-colors ${
                        selectedTask?.id === task.id ? 'border-orange-200 bg-orange-50' : 'border-gray-200 hover:border-gray-300'
                      }`}
                      onClick={() => {
                        setSelectedTask(task);
                        loadExecutions(task.id);
                      }}
                    >
                      <div className="flex items-center justify-between mb-3">
                        <div className="flex items-center space-x-3">
                          <h3 className="font-medium text-gray-900">{task.name}</h3>
                          <span className={`px-2 py-1 rounded-full text-xs font-medium ${getStatusColor(task.status)}`}>
                            {task.status}
                          </span>
                          <span className="px-2 py-1 rounded-full text-xs font-medium bg-gray-100 text-gray-700">
                            {getTypeName(task.type)}
                          </span>
                        </div>
                        <div className="flex items-center space-x-2">
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              handleExecuteTask(task.id);
                            }}
                            className="text-blue-600 hover:text-blue-800"
                            title="立即执行"
                          >
                            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14.828 14.828a4 4 0 01-5.656 0M9 10h1m4 0h1m-6 4h.01M19 10a9 9 0 11-18 0 9 9 0 0118 0z" />
                            </svg>
                          </button>
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              handleToggleTask(task);
                            }}
                            className={task.enabled ? "text-yellow-600 hover:text-yellow-800" : "text-green-600 hover:text-green-800"}
                            title={task.enabled ? "暂停" : "恢复"}
                          >
                            {task.enabled ? (
                              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 9v6m4-6v6m7-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                              </svg>
                            ) : (
                              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14.828 14.828a4 4 0 01-5.656 0M9 10h1m4 0h1m-6 4h.01M19 10a9 9 0 11-18 0 9 9 0 0118 0z" />
                              </svg>
                            )}
                          </button>
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              handleDeleteTask(task.id);
                            }}
                            className="text-red-600 hover:text-red-800"
                            title="删除"
                          >
                            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                            </svg>
                          </button>
                        </div>
                      </div>

                      <p className="text-gray-600 text-sm mb-2">{task.description}</p>
                      
                      <div className="flex items-center justify-between text-xs text-gray-500">
                        <span>调度: {formatSchedule(task.schedule)}</span>
                        <span>
                          成功: {task.execution.successfulRuns} | 失败: {task.execution.failedRuns}
                        </span>
                      </div>

                      {/* 进度条 */}
                      {task.progress && task.status === TaskStatus.RUNNING && (
                        <div className="mt-3">
                          <div className="flex items-center justify-between text-xs text-gray-600 mb-1">
                            <span>{task.progress.stage}</span>
                            <span>{task.progress.percentage}%</span>
                          </div>
                          <div className="w-full bg-gray-200 rounded-full h-2">
                            <div
                              className="bg-blue-600 h-2 rounded-full transition-all duration-300"
                              style={{ width: `${task.progress.percentage}%` }}
                            ></div>
                          </div>
                          {task.progress.details && (
                            <p className="text-xs text-gray-500 mt-1">{task.progress.details}</p>
                          )}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>

        {/* 任务详情和执行记录 */}
        <div className="space-y-6">
          {selectedTask ? (
            <>
              {/* 任务详情 */}
              <div className="bg-white rounded-lg shadow">
                <div className="p-6 border-b border-gray-200">
                  <h2 className="text-xl font-semibold text-gray-900">任务详情</h2>
                </div>
                <div className="p-6">
                  <div className="space-y-4">
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">名称</label>
                      <p className="text-gray-900">{selectedTask.name}</p>
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">描述</label>
                      <p className="text-gray-600">{selectedTask.description}</p>
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">类型</label>
                      <p className="text-gray-900">{getTypeName(selectedTask.type)}</p>
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">调度</label>
                      <p className="text-gray-900">{formatSchedule(selectedTask.schedule)}</p>
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">下次执行</label>
                      <p className="text-gray-900">
                        {selectedTask.execution.nextRunAt 
                          ? new Date(selectedTask.execution.nextRunAt).toLocaleString()
                          : '未安排'
                        }
                      </p>
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">平均执行时间</label>
                      <p className="text-gray-900">
                        {selectedTask.execution.averageDuration > 0 
                          ? `${Math.round(selectedTask.execution.averageDuration / 1000)}秒`
                          : '暂无数据'
                        }
                      </p>
                    </div>
                  </div>
                </div>
              </div>

              {/* 执行记录 */}
              <div className="bg-white rounded-lg shadow">
                <div className="p-6 border-b border-gray-200">
                  <h2 className="text-xl font-semibold text-gray-900">执行记录</h2>
                </div>
                <div className="p-6">
                  {executions.length === 0 ? (
                    <p className="text-gray-600 text-center py-4">暂无执行记录</p>
                  ) : (
                    <div className="space-y-3">
                      {executions.map((execution) => (
                        <div key={execution.id} className="border rounded-lg p-3">
                          <div className="flex items-center justify-between mb-2">
                            <span className={`px-2 py-1 rounded-full text-xs font-medium ${getStatusColor(execution.status)}`}>
                              {execution.status}
                            </span>
                            <span className="text-xs text-gray-500">
                              {new Date(execution.startedAt).toLocaleString()}
                            </span>
                          </div>
                          {execution.progress && (
                            <div className="mb-2">
                              <div className="flex items-center justify-between text-xs text-gray-600 mb-1">
                                <span>{execution.progress.stage}</span>
                                <span>{execution.progress.percentage}%</span>
                              </div>
                              <div className="w-full bg-gray-200 rounded-full h-1">
                                <div
                                  className="bg-blue-600 h-1 rounded-full"
                                  style={{ width: `${execution.progress.percentage}%` }}
                                ></div>
                              </div>
                            </div>
                          )}
                          {execution.result && (
                            <p className="text-xs text-gray-600">
                              {execution.result.message}
                            </p>
                          )}
                          {execution.duration && (
                            <p className="text-xs text-gray-500 mt-1">
                              耗时: {Math.round(execution.duration / 1000)}秒
                            </p>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            </>
          ) : (
            <div className="bg-white rounded-lg shadow p-6">
              <div className="text-center py-8">
                <svg className="w-16 h-16 text-gray-400 mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v10a2 2 0 002 2h8a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012-2" />
                </svg>
                <p className="text-gray-600">选择一个任务查看详情</p>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* 新建任务弹窗 */}
      {showAddForm && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl max-w-md w-full mx-4">
            <div className="p-6 border-b border-gray-200">
              <h2 className="text-xl font-semibold text-gray-900">新建定时任务</h2>
            </div>
            <div className="p-6 space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">任务名称</label>
                <input
                  type="text"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-orange-500"
                  placeholder="输入任务名称"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">描述</label>
                <textarea
                  value={formData.description}
                  onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-orange-500"
                  rows={3}
                  placeholder="输入任务描述"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">任务类型</label>
                <select
                  value={formData.type}
                  onChange={(e) => setFormData({ ...formData, type: e.target.value as TaskType })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-orange-500"
                >
                  <option value={TaskType.CRAWLER}>内容爬取</option>
                  <option value={TaskType.VIDEO_GENERATION}>视频生成</option>
                  <option value={TaskType.PUBLISHING}>内容发布</option>
                  <option value={TaskType.DATA_CLEANUP}>数据清理</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">调度类型</label>
                <select
                  value={formData.scheduleType}
                  onChange={(e) => setFormData({ ...formData, scheduleType: e.target.value as 'interval' | 'cron' | 'once' })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-orange-500"
                >
                  <option value="interval">定时间隔</option>
                  <option value="cron">Cron表达式</option>
                  <option value="once">单次执行</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  {formData.scheduleType === 'interval' ? '间隔时间(毫秒)' : 
                   formData.scheduleType === 'cron' ? 'Cron表达式' : '执行时间'}
                </label>
                <input
                  type="text"
                  value={formData.scheduleExpression}
                  onChange={(e) => setFormData({ ...formData, scheduleExpression: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-orange-500"
                  placeholder={
                    formData.scheduleType === 'interval' ? '3600000 (1小时)' :
                    formData.scheduleType === 'cron' ? '0 */1 * * *' : '2024-01-01 10:00:00'
                  }
                />
              </div>
              {formData.type === TaskType.CRAWLER && (
                <>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">平台</label>
                    <select
                      value={formData.platform}
                      onChange={(e) => setFormData({ ...formData, platform: e.target.value })}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-orange-500"
                    >
                      <option value="weibo">微博</option>
                      <option value="douyin">抖音</option>
                      <option value="xiaohongshu">小红书</option>
                      <option value="bilibili">B站</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">创作者URL</label>
                    <input
                      type="text"
                      value={formData.creatorUrl}
                      onChange={(e) => setFormData({ ...formData, creatorUrl: e.target.value })}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-orange-500"
                      placeholder="输入创作者主页URL"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">爬取数量</label>
                    <input
                      type="number"
                      value={formData.limit}
                      onChange={(e) => setFormData({ ...formData, limit: parseInt(e.target.value) })}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-orange-500"
                      min="1"
                      max="100"
                    />
                  </div>
                </>
              )}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">优先级 (1-10)</label>
                <input
                  type="number"
                  value={formData.priority}
                  onChange={(e) => setFormData({ ...formData, priority: parseInt(e.target.value) })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-orange-500"
                  min="1"
                  max="10"
                />
              </div>
            </div>
            <div className="p-6 border-t border-gray-200 flex justify-end space-x-3">
              <button
                onClick={() => setShowAddForm(false)}
                className="px-4 py-2 text-gray-700 bg-gray-200 rounded-lg hover:bg-gray-300 transition-colors"
              >
                取消
              </button>
              <button
                onClick={handleCreateTask}
                disabled={!formData.name.trim()}
                className="px-4 py-2 bg-orange-500 text-white rounded-lg hover:bg-orange-600 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
              >
                创建任务
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
} 