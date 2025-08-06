'use client';

import { useState, useEffect } from 'react';
import { analyticsApi, aiApi } from '@/utils/enhanced-api';
import Link from 'next/link';

export default function DashboardPage() {
  const [metrics, setMetrics] = useState<any>({});
  const [aiInsights, setAiInsights] = useState<any[]>([]);
  const [recentActivity, setRecentActivity] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [timeRange, setTimeRange] = useState('7d');

  useEffect(() => {
    loadDashboardData();
  }, [timeRange]);

  const loadDashboardData = async () => {
    try {
      setLoading(true);
      const [metricsData, insightsData] = await Promise.all([
        analyticsApi.getOverview(timeRange),
        aiApi.getInsights()
      ]);
      
      setMetrics(metricsData || {});
      setAiInsights(Array.isArray(insightsData) ? insightsData : []);
      
      // Mock recent activity data
      setRecentActivity([
        { id: 1, type: 'video_generated', title: 'AI Video Created', time: '2 minutes ago', status: 'success' },
        { id: 2, type: 'content_crawled', title: '50 New Posts Crawled', time: '5 minutes ago', status: 'success' },
        { id: 3, type: 'automation_triggered', title: 'Auto-publish Workflow', time: '10 minutes ago', status: 'running' },
        { id: 4, type: 'team_member_joined', title: 'New Team Member', time: '1 hour ago', status: 'info' }
      ]);
    } catch (error) {
      console.error('Failed to load dashboard data:', error);
      setMetrics({});
      setAiInsights([]);
      setRecentActivity([]);
    } finally {
      setLoading(false);
    }
  };

  const getActivityIcon = (type: string) => {
    switch (type) {
      case 'video_generated': return '🎬';
      case 'content_crawled': return '🕷️';
      case 'automation_triggered': return '🤖';
      case 'team_member_joined': return '👥';
      default: return '📊';
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'success': return 'text-green-600 bg-green-100';
      case 'running': return 'text-blue-600 bg-blue-100';
      case 'warning': return 'text-yellow-600 bg-yellow-100';
      case 'error': return 'text-red-600 bg-red-100';
      default: return 'text-gray-600 bg-gray-100';
    }
  };

  const quickActions = [
    { title: 'Start Crawling', description: 'Collect new content', href: '/crawler', icon: '🕷️', color: 'bg-blue-500' },
    { title: 'Generate Video', description: 'Create AI video', href: '/generate', icon: '🎬', color: 'bg-purple-500' },
    { title: 'AI Assistant', description: 'Get AI help', href: '/ai-assistant', icon: '🤖', color: 'bg-green-500' },
    { title: 'View Analytics', description: 'Check performance', href: '/analytics', icon: '📊', color: 'bg-orange-500' }
  ];

  return (
    <div className="min-h-screen" style={{ backgroundColor: 'var(--aws-gray-50)' }}>
      {/* Header */}
      <div style={{ backgroundColor: 'var(--aws-blue)' }} className="text-white py-8">
        <div className="max-w-7xl mx-auto px-4">
          <div className="flex justify-between items-center">
            <div>
              <h1 className="text-3xl font-bold mb-2">📊 Executive Dashboard</h1>
              <p className="text-gray-300">Real-time insights and AI-powered analytics for your content operations</p>
            </div>
            <div className="flex items-center space-x-3">
              <select
                value={timeRange}
                onChange={(e) => setTimeRange(e.target.value)}
                className="bg-white text-gray-900 px-3 py-2 rounded-lg text-sm"
              >
                <option value="1d">Last 24 Hours</option>
                <option value="7d">Last 7 Days</option>
                <option value="30d">Last 30 Days</option>
                <option value="90d">Last 90 Days</option>
              </select>
              <button
                onClick={loadDashboardData}
                className="aws-btn-secondary"
              >
                🔄 Refresh
              </button>
            </div>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 py-8">
        {loading ? (
          <div className="text-center py-12">
            <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-orange-500"></div>
            <p className="mt-2 text-gray-600">Loading dashboard data...</p>
          </div>
        ) : (
          <div className="space-y-8">
            {/* Key Metrics */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
              <div className="aws-card p-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-gray-600">Total Content</p>
                    <p className="text-3xl font-bold text-gray-900">{metrics.totalContent || 1247}</p>
                    <p className="text-sm text-green-600">+12% from last week</p>
                  </div>
                  <div className="w-12 h-12 bg-blue-100 rounded-lg flex items-center justify-center">
                    <span className="text-2xl">📝</span>
                  </div>
                </div>
              </div>

              <div className="aws-card p-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-gray-600">Videos Generated</p>
                    <p className="text-3xl font-bold text-gray-900">{metrics.videosGenerated || 89}</p>
                    <p className="text-sm text-green-600">+23% from last week</p>
                  </div>
                  <div className="w-12 h-12 bg-purple-100 rounded-lg flex items-center justify-center">
                    <span className="text-2xl">🎬</span>
                  </div>
                </div>
              </div>

              <div className="aws-card p-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-gray-600">Total Engagement</p>
                    <p className="text-3xl font-bold text-gray-900">{metrics.totalEngagement || '2.4M'}</p>
                    <p className="text-sm text-green-600">+8% from last week</p>
                  </div>
                  <div className="w-12 h-12 bg-green-100 rounded-lg flex items-center justify-center">
                    <span className="text-2xl">❤️</span>
                  </div>
                </div>
              </div>

              <div className="aws-card p-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-gray-600">AI Automations</p>
                    <p className="text-3xl font-bold text-gray-900">{metrics.automations || 15}</p>
                    <p className="text-sm text-blue-600">5 active workflows</p>
                  </div>
                  <div className="w-12 h-12 bg-orange-100 rounded-lg flex items-center justify-center">
                    <span className="text-2xl">🤖</span>
                  </div>
                </div>
              </div>
            </div>

            {/* Quick Actions */}
            <div className="aws-card">
              <div className="p-6 border-b border-gray-200">
                <h2 className="text-xl font-semibold">⚡ Quick Actions</h2>
              </div>
              <div className="p-6">
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                  {quickActions.map((action, index) => (
                    <Link
                      key={index}
                      href={action.href}
                      className="block p-4 rounded-lg border border-gray-200 hover:border-orange-300 hover:shadow-md transition-all"
                    >
                      <div className="flex items-center space-x-3">
                        <div className={`w-10 h-10 ${action.color} rounded-lg flex items-center justify-center text-white`}>
                          <span className="text-lg">{action.icon}</span>
                        </div>
                        <div>
                          <h3 className="font-semibold text-gray-900">{action.title}</h3>
                          <p className="text-sm text-gray-600">{action.description}</p>
                        </div>
                      </div>
                    </Link>
                  ))}
                </div>
              </div>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
              {/* AI Insights */}
              <div className="aws-card">
                <div className="p-6 border-b border-gray-200">
                  <h2 className="text-xl font-semibold">🧠 AI Insights</h2>
                </div>
                <div className="p-6">
                  {aiInsights.length === 0 ? (
                    <div className="space-y-4">
                      <div className="p-4 bg-blue-50 rounded-lg border border-blue-200">
                        <div className="flex items-start space-x-3">
                          <span className="text-blue-600 text-lg">💡</span>
                          <div>
                            <h4 className="font-semibold text-blue-900">Content Performance Trend</h4>
                            <p className="text-sm text-blue-700 mt-1">
                              Your video content is performing 23% better than text posts. Consider increasing video production.
                            </p>
                          </div>
                        </div>
                      </div>
                      
                      <div className="p-4 bg-green-50 rounded-lg border border-green-200">
                        <div className="flex items-start space-x-3">
                          <span className="text-green-600 text-lg">📈</span>
                          <div>
                            <h4 className="font-semibold text-green-900">Optimal Posting Time</h4>
                            <p className="text-sm text-green-700 mt-1">
                              Your audience is most active between 2-4 PM. Schedule more content during this window.
                            </p>
                          </div>
                        </div>
                      </div>
                      
                      <div className="p-4 bg-purple-50 rounded-lg border border-purple-200">
                        <div className="flex items-start space-x-3">
                          <span className="text-purple-600 text-lg">🎯</span>
                          <div>
                            <h4 className="font-semibold text-purple-900">Trending Topics</h4>
                            <p className="text-sm text-purple-700 mt-1">
                              AI technology and automation content is trending. Create more content in this niche.
                            </p>
                          </div>
                        </div>
                      </div>
                    </div>
                  ) : (
                    <div className="space-y-4">
                      {aiInsights.map((insight, index) => (
                        <div key={index} className="p-4 bg-gray-50 rounded-lg">
                          <h4 className="font-semibold text-gray-900">{insight.title}</h4>
                          <p className="text-sm text-gray-600 mt-1">{insight.description}</p>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>

              {/* Recent Activity */}
              <div className="aws-card">
                <div className="p-6 border-b border-gray-200">
                  <h2 className="text-xl font-semibold">🕐 Recent Activity</h2>
                </div>
                <div className="p-6">
                  <div className="space-y-4">
                    {recentActivity.map((activity) => (
                      <div key={activity.id} className="flex items-center space-x-4">
                        <div className="w-10 h-10 bg-gray-100 rounded-full flex items-center justify-center">
                          <span className="text-lg">{getActivityIcon(activity.type)}</span>
                        </div>
                        <div className="flex-1">
                          <h4 className="font-semibold text-gray-900">{activity.title}</h4>
                          <p className="text-sm text-gray-600">{activity.time}</p>
                        </div>
                        <span className={`px-2 py-1 rounded-full text-xs font-medium ${getStatusColor(activity.status)}`}>
                          {activity.status}
                        </span>
                      </div>
                    ))}
                  </div>
                  
                  <div className="mt-6 pt-4 border-t border-gray-200">
                    <Link
                      href="/analytics"
                      className="text-orange-600 hover:text-orange-700 text-sm font-medium"
                    >
                      View All Activity →
                    </Link>
                  </div>
                </div>
              </div>
            </div>

            {/* Platform Performance */}
            <div className="aws-card">
              <div className="p-6 border-b border-gray-200">
                <h2 className="text-xl font-semibold">📱 Platform Performance</h2>
              </div>
              <div className="p-6">
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
                  {[
                    { platform: 'Weibo', engagement: '45.2K', growth: '+15%', color: 'bg-red-500' },
                    { platform: 'Bilibili', engagement: '32.8K', growth: '+22%', color: 'bg-blue-500' },
                    { platform: 'Xiaohongshu', engagement: '28.1K', growth: '+8%', color: 'bg-pink-500' },
                    { platform: 'Douyin', engagement: '51.7K', growth: '+31%', color: 'bg-black' }
                  ].map((platform, index) => (
                    <div key={index} className="text-center">
                      <div className={`w-16 h-16 ${platform.color} rounded-full mx-auto mb-3 flex items-center justify-center text-white font-bold`}>
                        {platform.platform.charAt(0)}
                      </div>
                      <h3 className="font-semibold text-gray-900">{platform.platform}</h3>
                      <p className="text-2xl font-bold text-gray-900 mt-1">{platform.engagement}</p>
                      <p className="text-sm text-green-600">{platform.growth}</p>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}