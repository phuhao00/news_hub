'use client';

import { useState, useEffect } from 'react';
import { monitoringApi } from '@/utils/enhanced-api';

export default function MonitoringPage() {
  const [alerts, setAlerts] = useState<any[]>([]);
  const [systemHealth, setSystemHealth] = useState<any>({});
  const [performanceMetrics, setPerformanceMetrics] = useState<any>({});
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('overview');
  const [showCreateAlert, setShowCreateAlert] = useState(false);
  const [newAlert, setNewAlert] = useState({
    name: '',
    type: 'threshold',
    metric: '',
    condition: 'greater_than',
    value: '',
    channels: [] as string[]
  });

  const alertTypes = [
    { id: 'threshold', name: '📊 Threshold Alert', description: 'Trigger when metric crosses threshold' },
    { id: 'anomaly', name: '🔍 Anomaly Detection', description: 'AI-powered anomaly detection' },
    { id: 'trend', name: '📈 Trend Alert', description: 'Alert on trend changes' },
    { id: 'composite', name: '🔗 Composite Alert', description: 'Multiple conditions combined' }
  ];

  const availableMetrics = [
    { id: 'cpu_usage', name: 'CPU Usage (%)', category: 'System' },
    { id: 'memory_usage', name: 'Memory Usage (%)', category: 'System' },
    { id: 'disk_usage', name: 'Disk Usage (%)', category: 'System' },
    { id: 'response_time', name: 'Response Time (ms)', category: 'Performance' },
    { id: 'error_rate', name: 'Error Rate (%)', category: 'Performance' },
    { id: 'throughput', name: 'Requests/sec', category: 'Performance' },
    { id: 'content_crawled', name: 'Content Crawled/hour', category: 'Business' },
    { id: 'videos_generated', name: 'Videos Generated/hour', category: 'Business' },
    { id: 'engagement_rate', name: 'Engagement Rate (%)', category: 'Business' },
    { id: 'user_sessions', name: 'Active User Sessions', category: 'Business' }
  ];

  const notificationChannels = [
    { id: 'email', name: '📧 Email', description: 'Send email notifications' },
    { id: 'slack', name: '💬 Slack', description: 'Post to Slack channel' },
    { id: 'discord', name: '🎮 Discord', description: 'Send Discord message' },
    { id: 'webhook', name: '🔗 Webhook', description: 'HTTP webhook call' },
    { id: 'sms', name: '📱 SMS', description: 'Text message alerts' }
  ];

  const mockSystemHealth = {
    overall: 'healthy',
    services: [
      { name: 'Web Server', status: 'healthy', uptime: '99.9%', responseTime: '45ms' },
      { name: 'Database', status: 'healthy', uptime: '99.8%', responseTime: '12ms' },
      { name: 'AI Service', status: 'warning', uptime: '98.5%', responseTime: '230ms' },
      { name: 'File Storage', status: 'healthy', uptime: '99.9%', responseTime: '89ms' },
      { name: 'Cache Layer', status: 'healthy', uptime: '99.7%', responseTime: '3ms' }
    ],
    metrics: {
      cpuUsage: 45,
      memoryUsage: 67,
      diskUsage: 23,
      networkIO: 1.2,
      activeConnections: 1847
    }
  };

  const mockAlerts = [
    {
      id: 1,
      name: 'High CPU Usage',
      type: 'threshold',
      status: 'active',
      severity: 'warning',
      metric: 'CPU Usage',
      condition: 'greater_than',
      threshold: 80,
      currentValue: 85,
      triggeredAt: new Date(Date.now() - 300000),
      description: 'CPU usage has exceeded 80% threshold'
    },
    {
      id: 2,
      name: 'Low Engagement Rate',
      type: 'threshold',
      status: 'resolved',
      severity: 'info',
      metric: 'Engagement Rate',
      condition: 'less_than',
      threshold: 2.5,
      currentValue: 3.2,
      triggeredAt: new Date(Date.now() - 1800000),
      resolvedAt: new Date(Date.now() - 600000),
      description: 'Engagement rate dropped below 2.5%'
    },
    {
      id: 3,
      name: 'AI Service Anomaly',
      type: 'anomaly',
      status: 'active',
      severity: 'critical',
      metric: 'Response Time',
      currentValue: 2300,
      triggeredAt: new Date(Date.now() - 120000),
      description: 'AI service response time showing unusual patterns'
    }
  ];

  useEffect(() => {
    loadMonitoringData();
    const interval = setInterval(loadMonitoringData, 30000); // Refresh every 30 seconds
    return () => clearInterval(interval);
  }, []);

  const loadMonitoringData = async () => {
    try {
      setLoading(true);
      // In real app, load from API
      setSystemHealth(mockSystemHealth);
      setAlerts(mockAlerts);
      setPerformanceMetrics({
        avgResponseTime: 145,
        errorRate: 0.02,
        throughput: 1250,
        uptime: 99.8
      });
    } catch (error) {
      console.error('Failed to load monitoring data:', error);
    } finally {
      setLoading(false);
    }
  };

  const createAlert = async () => {
    if (!newAlert.name.trim() || !newAlert.metric || !newAlert.value) {
      alert('Please fill in all required fields');
      return;
    }

    try {
      // In real app, call API
      const alert = {
        id: Date.now(),
        ...newAlert,
        status: 'active',
        createdAt: new Date()
      };
      setAlerts([alert, ...alerts]);
      setShowCreateAlert(false);
      setNewAlert({
        name: '',
        type: 'threshold',
        metric: '',
        condition: 'greater_than',
        value: '',
        channels: []
      });
      alert('Alert created successfully!');
    } catch (error) {
      console.error('Failed to create alert:', error);
      alert('Failed to create alert');
    }
  };

  const acknowledgeAlert = async (alertId: number) => {
    try {
      setAlerts(alerts.map(a => 
        a.id === alertId ? { ...a, status: 'acknowledged' } : a
      ));
    } catch (error) {
      console.error('Failed to acknowledge alert:', error);
    }
  };

  const resolveAlert = async (alertId: number) => {
    try {
      setAlerts(alerts.map(a => 
        a.id === alertId ? { ...a, status: 'resolved', resolvedAt: new Date() } : a
      ));
    } catch (error) {
      console.error('Failed to resolve alert:', error);
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'healthy': return 'text-green-600 bg-green-100';
      case 'warning': return 'text-yellow-600 bg-yellow-100';
      case 'critical': return 'text-red-600 bg-red-100';
      case 'unknown': return 'text-gray-600 bg-gray-100';
      default: return 'text-gray-600 bg-gray-100';
    }
  };

  const getSeverityColor = (severity: string) => {
    switch (severity) {
      case 'critical': return 'text-red-600 bg-red-100';
      case 'warning': return 'text-yellow-600 bg-yellow-100';
      case 'info': return 'text-blue-600 bg-blue-100';
      default: return 'text-gray-600 bg-gray-100';
    }
  };

  const getAlertStatusColor = (status: string) => {
    switch (status) {
      case 'active': return 'text-red-600 bg-red-100';
      case 'acknowledged': return 'text-yellow-600 bg-yellow-100';
      case 'resolved': return 'text-green-600 bg-green-100';
      default: return 'text-gray-600 bg-gray-100';
    }
  };

  const activeAlerts = alerts.filter(a => a.status === 'active').length;
  const criticalAlerts = alerts.filter(a => a.severity === 'critical' && a.status === 'active').length;

  return (
    <div className="min-h-screen" style={{ backgroundColor: 'var(--aws-gray-50)' }}>
      {/* Header */}
      <div style={{ backgroundColor: 'var(--aws-blue)' }} className="text-white py-8">
        <div className="max-w-7xl mx-auto px-4">
          <div className="flex justify-between items-center">
            <div>
              <h1 className="text-3xl font-bold mb-2">🔍 System Monitoring</h1>
              <p className="text-gray-300">Real-time monitoring and alerting for your NewsHub infrastructure</p>
            </div>
            <div className="flex items-center space-x-4">
              <div className="text-center">
                <div className="text-2xl font-bold">{activeAlerts}</div>
                <div className="text-sm text-gray-300">Active Alerts</div>
              </div>
              <div className="text-center">
                <div className="text-2xl font-bold text-red-300">{criticalAlerts}</div>
                <div className="text-sm text-gray-300">Critical</div>
              </div>
              <button
                onClick={() => setShowCreateAlert(true)}
                className="aws-btn-primary"
              >
                ➕ Create Alert
              </button>
            </div>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 py-8">
        {/* Tabs */}
        <div className="flex space-x-1 mb-8">
          {[
            { id: 'overview', name: '📊 Overview' },
            { id: 'alerts', name: '🚨 Alerts', count: activeAlerts },
            { id: 'health', name: '💚 System Health' },
            { id: 'performance', name: '⚡ Performance' }
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`px-6 py-3 rounded-lg font-medium transition-colors ${
                activeTab === tab.id
                  ? 'bg-orange-500 text-white'
                  : 'bg-white text-gray-700 hover:bg-gray-50'
              }`}
            >
              {tab.name}
              {tab.count !== undefined && tab.count > 0 && (
                <span className={`ml-2 px-2 py-1 rounded-full text-xs ${
                  activeTab === tab.id ? 'bg-orange-600' : 'bg-red-500 text-white'
                }`}>
                  {tab.count}
                </span>
              )}
            </button>
          ))}
        </div>

        {loading ? (
          <div className="text-center py-12">
            <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-orange-500"></div>
            <p className="mt-2 text-gray-600">Loading monitoring data...</p>
          </div>
        ) : (
          <>
            {/* Overview Tab */}
            {activeTab === 'overview' && (
              <div className="space-y-8">
                {/* Key Metrics */}
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
                  <div className="aws-card p-6">
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="text-sm text-gray-600">System Uptime</p>
                        <p className="text-3xl font-bold text-green-600">{performanceMetrics.uptime}%</p>
                        <p className="text-sm text-gray-500">Last 30 days</p>
                      </div>
                      <div className="w-12 h-12 bg-green-100 rounded-lg flex items-center justify-center">
                        <span className="text-2xl">⏱️</span>
                      </div>
                    </div>
                  </div>

                  <div className="aws-card p-6">
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="text-sm text-gray-600">Avg Response Time</p>
                        <p className="text-3xl font-bold text-blue-600">{performanceMetrics.avgResponseTime}ms</p>
                        <p className="text-sm text-green-600">-12ms from yesterday</p>
                      </div>
                      <div className="w-12 h-12 bg-blue-100 rounded-lg flex items-center justify-center">
                        <span className="text-2xl">⚡</span>
                      </div>
                    </div>
                  </div>

                  <div className="aws-card p-6">
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="text-sm text-gray-600">Error Rate</p>
                        <p className="text-3xl font-bold text-yellow-600">{performanceMetrics.errorRate}%</p>
                        <p className="text-sm text-green-600">Within normal range</p>
                      </div>
                      <div className="w-12 h-12 bg-yellow-100 rounded-lg flex items-center justify-center">
                        <span className="text-2xl">⚠️</span>
                      </div>
                    </div>
                  </div>

                  <div className="aws-card p-6">
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="text-sm text-gray-600">Throughput</p>
                        <p className="text-3xl font-bold text-purple-600">{performanceMetrics.throughput}</p>
                        <p className="text-sm text-gray-500">requests/sec</p>
                      </div>
                      <div className="w-12 h-12 bg-purple-100 rounded-lg flex items-center justify-center">
                        <span className="text-2xl">📈</span>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Recent Alerts */}
                <div className="aws-card">
                  <div className="p-6 border-b border-gray-200">
                    <h2 className="text-xl font-semibold">🚨 Recent Alerts</h2>
                  </div>
                  <div className="p-6">
                    {alerts.slice(0, 5).map((alert) => (
                      <div key={alert.id} className="flex items-center justify-between py-3 border-b border-gray-100 last:border-b-0">
                        <div className="flex items-center space-x-4">
                          <span className={`px-2 py-1 rounded-full text-xs font-medium ${getSeverityColor(alert.severity)}`}>
                            {alert.severity}
                          </span>
                          <div>
                            <h4 className="font-semibold text-gray-900">{alert.name}</h4>
                            <p className="text-sm text-gray-600">{alert.description}</p>
                          </div>
                        </div>
                        <div className="text-right">
                          <span className={`px-2 py-1 rounded-full text-xs font-medium ${getAlertStatusColor(alert.status)}`}>
                            {alert.status}
                          </span>
                          <p className="text-xs text-gray-500 mt-1">
                            {alert.triggeredAt.toLocaleString()}
                          </p>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )}

            {/* Alerts Tab */}
            {activeTab === 'alerts' && (
              <div className="aws-card">
                <div className="p-6 border-b border-gray-200">
                  <h2 className="text-xl font-semibold">🚨 Alert Management</h2>
                </div>
                
                {alerts.length === 0 ? (
                  <div className="text-center py-12">
                    <svg className="w-16 h-16 text-gray-400 mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z" />
                    </svg>
                    <p className="text-gray-500 text-lg mb-2">No alerts configured</p>
                    <p className="text-gray-400 mb-4">Create your first alert to monitor system health</p>
                    <button
                      onClick={() => setShowCreateAlert(true)}
                      className="aws-btn-primary"
                    >
                      Create Alert
                    </button>
                  </div>
                ) : (
                  <div className="divide-y divide-gray-200">
                    {alerts.map((alert) => (
                      <div key={alert.id} className="p-6">
                        <div className="flex items-start justify-between">
                          <div className="flex-1">
                            <div className="flex items-center space-x-3 mb-2">
                              <h3 className="text-lg font-semibold text-gray-900">{alert.name}</h3>
                              <span className={`px-2 py-1 rounded-full text-xs font-medium ${getSeverityColor(alert.severity)}`}>
                                {alert.severity}
                              </span>
                              <span className={`px-2 py-1 rounded-full text-xs font-medium ${getAlertStatusColor(alert.status)}`}>
                                {alert.status}
                              </span>
                            </div>
                            
                            <p className="text-gray-600 mb-3">{alert.description}</p>
                            
                            <div className="flex flex-wrap gap-4 text-sm text-gray-500">
                              <div>
                                <span className="font-medium">Metric:</span> {alert.metric}
                              </div>
                              {alert.condition && (
                                <div>
                                  <span className="font-medium">Condition:</span> {alert.condition} {alert.threshold}
                                </div>
                              )}
                              <div>
                                <span className="font-medium">Current:</span> {alert.currentValue}
                              </div>
                              <div>
                                <span className="font-medium">Triggered:</span> {alert.triggeredAt.toLocaleString()}
                              </div>
                              {alert.resolvedAt && (
                                <div>
                                  <span className="font-medium">Resolved:</span> {alert.resolvedAt.toLocaleString()}
                                </div>
                              )}
                            </div>
                          </div>
                          
                          <div className="flex items-center space-x-2 ml-4">
                            {alert.status === 'active' && (
                              <>
                                <button
                                  onClick={() => acknowledgeAlert(alert.id)}
                                  className="px-3 py-1 bg-yellow-600 text-white rounded text-sm hover:bg-yellow-700 transition-colors"
                                >
                                  👁️ Acknowledge
                                </button>
                                <button
                                  onClick={() => resolveAlert(alert.id)}
                                  className="px-3 py-1 bg-green-600 text-white rounded text-sm hover:bg-green-700 transition-colors"
                                >
                                  ✅ Resolve
                                </button>
                              </>
                            )}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* System Health Tab */}
            {activeTab === 'health' && (
              <div className="space-y-6">
                {/* Overall Health */}
                <div className="aws-card p-6">
                  <div className="flex items-center justify-between mb-6">
                    <h2 className="text-xl font-semibold">🏥 System Health Overview</h2>
                    <span className={`px-4 py-2 rounded-full text-sm font-medium ${getStatusColor(systemHealth.overall)}`}>
                      {systemHealth.overall?.toUpperCase()}
                    </span>
                  </div>
                  
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                    {systemHealth.services?.map((service: any, index: number) => (
                      <div key={index} className="border border-gray-200 rounded-lg p-4">
                        <div className="flex items-center justify-between mb-3">
                          <h3 className="font-semibold text-gray-900">{service.name}</h3>
                          <span className={`px-2 py-1 rounded-full text-xs font-medium ${getStatusColor(service.status)}`}>
                            {service.status}
                          </span>
                        </div>
                        <div className="space-y-2 text-sm text-gray-600">
                          <div className="flex justify-between">
                            <span>Uptime:</span>
                            <span className="font-medium">{service.uptime}</span>
                          </div>
                          <div className="flex justify-between">
                            <span>Response Time:</span>
                            <span className="font-medium">{service.responseTime}</span>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Resource Usage */}
                <div className="aws-card p-6">
                  <h2 className="text-xl font-semibold mb-6">💻 Resource Usage</h2>
                  
                  <div className="space-y-6">
                    {[
                      { name: 'CPU Usage', value: systemHealth.metrics?.cpuUsage, max: 100, unit: '%', color: 'bg-blue-500' },
                      { name: 'Memory Usage', value: systemHealth.metrics?.memoryUsage, max: 100, unit: '%', color: 'bg-green-500' },
                      { name: 'Disk Usage', value: systemHealth.metrics?.diskUsage, max: 100, unit: '%', color: 'bg-yellow-500' },
                      { name: 'Network I/O', value: systemHealth.metrics?.networkIO, max: 10, unit: 'GB/s', color: 'bg-purple-500' }
                    ].map((metric, index) => (
                      <div key={index}>
                        <div className="flex justify-between items-center mb-2">
                          <span className="text-sm font-medium text-gray-700">{metric.name}</span>
                          <span className="text-sm text-gray-600">{metric.value}{metric.unit}</span>
                        </div>
                        <div className="w-full bg-gray-200 rounded-full h-2">
                          <div
                            className={`h-2 rounded-full ${metric.color}`}
                            style={{ width: `${(metric.value / metric.max) * 100}%` }}
                          ></div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )}

            {/* Performance Tab */}
            {activeTab === 'performance' && (
              <div className="aws-card p-6">
                <h2 className="text-xl font-semibold mb-6">⚡ Performance Metrics</h2>
                
                <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                  <div>
                    <h3 className="text-lg font-semibold mb-4">📊 Response Time Trends</h3>
                    <div className="h-64 bg-gray-100 rounded-lg flex items-center justify-center">
                      <span className="text-gray-500">Response Time Chart Placeholder</span>
                    </div>
                  </div>
                  
                  <div>
                    <h3 className="text-lg font-semibold mb-4">📈 Throughput Analysis</h3>
                    <div className="h-64 bg-gray-100 rounded-lg flex items-center justify-center">
                      <span className="text-gray-500">Throughput Chart Placeholder</span>
                    </div>
                  </div>
                </div>
              </div>
            )}
          </>
        )}
      </div>

      {/* Create Alert Modal */}
      {showCreateAlert && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg max-w-2xl w-full mx-4 max-h-[90vh] overflow-y-auto">
            <div className="p-6 border-b border-gray-200">
              <h2 className="text-xl font-semibold">🚨 Create New Alert</h2>
            </div>
            
            <div className="p-6 space-y-6">
              <div>
                <label className="block text-sm font-medium mb-2">Alert Name</label>
                <input
                  type="text"
                  value={newAlert.name}
                  onChange={(e) => setNewAlert({ ...newAlert, name: e.target.value })}
                  placeholder="Enter alert name..."
                  className="aws-input w-full"
                />
              </div>

              <div>
                <label className="block text-sm font-medium mb-2">Alert Type</label>
                <select
                  value={newAlert.type}
                  onChange={(e) => setNewAlert({ ...newAlert, type: e.target.value })}
                  className="aws-input w-full"
                >
                  {alertTypes.map(type => (
                    <option key={type.id} value={type.id}>
                      {type.name} - {type.description}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium mb-2">Metric</label>
                <select
                  value={newAlert.metric}
                  onChange={(e) => setNewAlert({ ...newAlert, metric: e.target.value })}
                  className="aws-input w-full"
                >
                  <option value="">Select a metric...</option>
                  {availableMetrics.map(metric => (
                    <option key={metric.id} value={metric.id}>
                      {metric.name} ({metric.category})
                    </option>
                  ))}
                </select>
              </div>

              {newAlert.type === 'threshold' && (
                <>
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="block text-sm font-medium mb-2">Condition</label>
                      <select
                        value={newAlert.condition}
                        onChange={(e) => setNewAlert({ ...newAlert, condition: e.target.value })}
                        className="aws-input w-full"
                      >
                        <option value="greater_than">Greater than</option>
                        <option value="less_than">Less than</option>
                        <option value="equals">Equals</option>
                        <option value="not_equals">Not equals</option>
                      </select>
                    </div>
                    <div>
                      <label className="block text-sm font-medium mb-2">Threshold Value</label>
                      <input
                        type="number"
                        value={newAlert.value}
                        onChange={(e) => setNewAlert({ ...newAlert, value: e.target.value })}
                        placeholder="Enter threshold value..."
                        className="aws-input w-full"
                      />
                    </div>
                  </div>
                </>
              )}

              <div>
                <label className="block text-sm font-medium mb-3">Notification Channels</label>
                <div className="space-y-2">
                  {notificationChannels.map(channel => (
                    <label key={channel.id} className="flex items-center p-3 border rounded-lg cursor-pointer hover:bg-gray-50">
                      <input
                        type="checkbox"
                        checked={newAlert.channels.includes(channel.id)}
                        onChange={(e) => {
                          if (e.target.checked) {
                            setNewAlert({
                              ...newAlert,
                              channels: [...newAlert.channels, channel.id]
                            });
                          } else {
                            setNewAlert({
                              ...newAlert,
                              channels: newAlert.channels.filter(c => c !== channel.id)
                            });
                          }
                        }}
                        className="text-orange-500 focus:ring-orange-500"
                      />
                      <div className="ml-3">
                        <div className="font-medium text-sm">{channel.name}</div>
                        <div className="text-xs text-gray-600">{channel.description}</div>
                      </div>
                    </label>
                  ))}
                </div>
              </div>
            </div>
            
            <div className="p-6 border-t border-gray-200 flex justify-end space-x-3">
              <button
                onClick={() => {
                  setShowCreateAlert(false);
                  setNewAlert({
                    name: '',
                    type: 'threshold',
                    metric: '',
                    condition: 'greater_than',
                    value: '',
                    channels: []
                  });
                }}
                className="px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={createAlert}
                className="aws-btn-primary"
              >
                Create Alert
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
