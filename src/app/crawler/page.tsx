'use client';

import { useState, useEffect } from 'react';
import { crawlerApi, creatorApi } from '@/utils/api';

interface Creator {
  id: string;
  username: string;
  displayName?: string;
  platform: string;
}

interface CrawlerStatus {
  isRunning: boolean;
  lastRunTime?: string;
  totalPosts?: number;
  errors?: string[];
}

export default function CrawlerPage() {
  const [creators, setCreators] = useState<Creator[]>([]);
  const [crawlerStatus, setCrawlerStatus] = useState<CrawlerStatus>({ isRunning: false });
  const [loading, setLoading] = useState(true);
  const [triggering, setTriggering] = useState(false);
  const [selectedCreators, setSelectedCreators] = useState<string[]>([]);
  const [selectedPlatforms, setSelectedPlatforms] = useState<string[]>([]);

  useEffect(() => {
    loadData();
    // 每30秒刷新一次状态
    const interval = setInterval(loadCrawlerStatus, 30000);
    return () => clearInterval(interval);
  }, []);

  const loadData = async () => {
    try {
      setLoading(true);
      const [creatorsData, statusData] = await Promise.all([
        creatorApi.list(),
        loadCrawlerStatus()
      ]);
      setCreators(creatorsData || []);
    } catch (error) {
      console.error('加载数据失败:', error);
    } finally {
      setLoading(false);
    }
  };

  const loadCrawlerStatus = async () => {
    try {
      const status = await crawlerApi.status();
      setCrawlerStatus(status);
      return status;
    } catch (error) {
      console.error('获取爬虫状态失败:', error);
      return null;
    }
  };

  const handleTriggerCrawler = async () => {
    try {
      setTriggering(true);
      const data: { creatorIds?: string[]; platforms?: string[] } = {};
      
      if (selectedCreators.length > 0) {
        data.creatorIds = selectedCreators;
      }
      if (selectedPlatforms.length > 0) {
        data.platforms = selectedPlatforms;
      }

      await crawlerApi.trigger(data);
      alert('爬虫任务已触发！');
      
      // 延迟一下再刷新状态
      setTimeout(loadCrawlerStatus, 2000);
    } catch (error) {
      console.error('触发爬虫失败:', error);
      alert('触发爬虫失败，请稍后重试');
    } finally {
      setTriggering(false);
    }
  };

  const handleCreatorSelection = (creatorId: string) => {
    setSelectedCreators(prev => 
      prev.includes(creatorId)
        ? prev.filter(id => id !== creatorId)
        : [...prev, creatorId]
    );
  };

  const handlePlatformSelection = (platform: string) => {
    setSelectedPlatforms(prev => 
      prev.includes(platform)
        ? prev.filter(p => p !== platform)
        : [...prev, platform]
    );
  };

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

  const platforms = ['weibo', 'douyin', 'xiaohongshu', 'bilibili'];

  if (loading) {
    return (
      <main className="min-h-screen" style={{ backgroundColor: 'var(--aws-gray-50)' }}>
        <div className="max-w-7xl mx-auto px-4 py-8">
          <div className="flex items-center justify-center py-12">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-orange-500"></div>
            <span className="ml-2 text-gray-600">加载中...</span>
          </div>
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-screen" style={{ backgroundColor: 'var(--aws-gray-50)' }}>
      {/* 页面头部 */}
      <div style={{ backgroundColor: 'var(--aws-blue)' }} className="text-white py-8">
        <div className="max-w-7xl mx-auto px-4">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-3xl font-bold mb-2">爬虫控制</h1>
              <p className="text-gray-300">管理和控制社交媒体内容爬取任务</p>
            </div>
            <div className="text-right">
              <div className={`inline-flex items-center px-3 py-1 rounded-full text-sm font-medium ${
                crawlerStatus.isRunning 
                  ? 'bg-green-100 text-green-800' 
                  : 'bg-gray-100 text-gray-800'
              }`}>
                <div className={`w-2 h-2 rounded-full mr-2 ${
                  crawlerStatus.isRunning ? 'bg-green-500' : 'bg-gray-500'
                }`}></div>
                {crawlerStatus.isRunning ? '运行中' : '空闲'}
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 py-8">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* 爬虫状态 */}
          <div className="lg:col-span-1">
            <div className="aws-card p-6 mb-6">
              <div className="flex items-center mb-4">
                <div className="w-8 h-8 bg-blue-500 rounded flex items-center justify-center mr-3">
                  <svg className="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                  </svg>
                </div>
                <h2 className="text-xl font-semibold">爬虫状态</h2>
              </div>
              
              <div className="space-y-4">
                <div className="flex justify-between items-center">
                  <span className="text-gray-600">运行状态</span>
                  <span className={`font-medium ${
                    crawlerStatus.isRunning ? 'text-green-600' : 'text-gray-600'
                  }`}>
                    {crawlerStatus.isRunning ? '运行中' : '空闲'}
                  </span>
                </div>
                
                {crawlerStatus.lastRunTime && (
                  <div className="flex justify-between items-center">
                    <span className="text-gray-600">最后运行</span>
                    <span className="text-sm text-gray-500">
                      {new Date(crawlerStatus.lastRunTime).toLocaleString('zh-CN')}
                    </span>
                  </div>
                )}
                
                {crawlerStatus.totalPosts !== undefined && (
                  <div className="flex justify-between items-center">
                    <span className="text-gray-600">总内容数</span>
                    <span className="font-medium text-blue-600">
                      {crawlerStatus.totalPosts}
                    </span>
                  </div>
                )}
              </div>
              
              {crawlerStatus.errors && crawlerStatus.errors.length > 0 && (
                <div className="mt-4 p-3 bg-red-50 border border-red-200 rounded">
                  <h4 className="text-sm font-medium text-red-800 mb-2">错误信息</h4>
                  <ul className="text-sm text-red-600 space-y-1">
                    {crawlerStatus.errors.map((error, index) => (
                      <li key={index}>• {error}</li>
                    ))}
                  </ul>
                </div>
              )}
              
              <button
                onClick={loadCrawlerStatus}
                className="w-full mt-4 aws-btn-secondary"
              >
                刷新状态
              </button>
            </div>
          </div>

          {/* 爬虫控制 */}
          <div className="lg:col-span-2">
            <div className="aws-card p-6">
              <div className="flex items-center mb-6">
                <div className="w-8 h-8 bg-orange-500 rounded flex items-center justify-center mr-3">
                  <svg className="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6V4m0 2a2 2 0 100 4m0-4a2 2 0 110 4m-2 8a2 2 0 100-4m0 4a2 2 0 100 4m0-4v2m0-6V4" />
                  </svg>
                </div>
                <h2 className="text-xl font-semibold">触发爬虫任务</h2>
              </div>

              {/* 平台选择 */}
              <div className="mb-6">
                <h3 className="text-lg font-medium mb-3">选择平台（可选）</h3>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                  {platforms.map((platform) => (
                    <label
                      key={platform}
                      className={`flex items-center p-3 border rounded-lg cursor-pointer transition-colors ${
                        selectedPlatforms.includes(platform)
                          ? 'border-orange-500 bg-orange-50'
                          : 'border-gray-200 hover:border-orange-300'
                      }`}
                    >
                      <input
                        type="checkbox"
                        checked={selectedPlatforms.includes(platform)}
                        onChange={() => handlePlatformSelection(platform)}
                        className="sr-only"
                      />
                      <div className="flex items-center space-x-2">
                        <span className="text-lg">{getPlatformIcon(platform)}</span>
                        <span className="text-sm font-medium">{getPlatformName(platform)}</span>
                      </div>
                    </label>
                  ))}
                </div>
                <p className="text-sm text-gray-500 mt-2">
                  不选择任何平台将爬取所有平台的内容
                </p>
              </div>

              {/* 创作者选择 */}
              <div className="mb-6">
                <h3 className="text-lg font-medium mb-3">选择创作者（可选）</h3>
                {creators.length === 0 ? (
                  <div className="text-center py-8 text-gray-500">
                    <svg className="w-12 h-12 text-gray-400 mx-auto mb-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
                    </svg>
                    <p>暂无创作者，请先添加创作者</p>
                  </div>
                ) : (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3 max-h-64 overflow-y-auto">
                    {creators.map((creator) => (
                      <label
                        key={creator.id}
                        className={`flex items-center p-3 border rounded-lg cursor-pointer transition-colors ${
                          selectedCreators.includes(creator.id)
                            ? 'border-orange-500 bg-orange-50'
                            : 'border-gray-200 hover:border-orange-300'
                        }`}
                      >
                        <input
                          type="checkbox"
                          checked={selectedCreators.includes(creator.id)}
                          onChange={() => handleCreatorSelection(creator.id)}
                          className="sr-only"
                        />
                        <div className="flex items-center space-x-3">
                          <div className="w-8 h-8 bg-gradient-to-r from-blue-400 to-blue-600 rounded-full flex items-center justify-center">
                            <span className="text-white text-xs font-semibold">
                              {(creator.displayName || creator.username).charAt(0).toUpperCase()}
                            </span>
                          </div>
                          <div>
                            <div className="font-medium text-gray-900">
                              {creator.displayName || creator.username}
                            </div>
                            <div className="text-sm text-gray-500">
                              {getPlatformName(creator.platform)}
                            </div>
                          </div>
                        </div>
                      </label>
                    ))}
                  </div>
                )}
                <p className="text-sm text-gray-500 mt-2">
                  不选择任何创作者将爬取所有创作者的内容
                </p>
              </div>

              {/* 触发按钮 */}
              <div className="flex items-center justify-between pt-4 border-t border-gray-200">
                <div className="text-sm text-gray-600">
                  {selectedPlatforms.length > 0 && (
                    <span>已选择 {selectedPlatforms.length} 个平台，</span>
                  )}
                  {selectedCreators.length > 0 && (
                    <span>已选择 {selectedCreators.length} 个创作者</span>
                  )}
                  {selectedPlatforms.length === 0 && selectedCreators.length === 0 && (
                    <span>将爬取所有平台的所有创作者内容</span>
                  )}
                </div>
                <button
                  onClick={handleTriggerCrawler}
                  disabled={triggering || crawlerStatus.isRunning}
                  className={`aws-btn-primary ${
                    (triggering || crawlerStatus.isRunning) ? 'opacity-50 cursor-not-allowed' : ''
                  }`}
                >
                  {triggering ? (
                    <span className="flex items-center">
                      <svg className="animate-spin -ml-1 mr-2 h-4 w-4 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                      </svg>
                      触发中...
                    </span>
                  ) : crawlerStatus.isRunning ? (
                    '爬虫运行中'
                  ) : (
                    '开始爬取'
                  )}
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </main>
  );
}