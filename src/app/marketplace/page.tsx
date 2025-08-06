'use client';

import { useState, useEffect } from 'react';
import { marketplaceApi } from '@/utils/enhanced-api';

export default function MarketplacePage() {
  const [plugins, setPlugins] = useState<any[]>([]);
  const [templates, setTemplates] = useState<any[]>([]);
  const [activeTab, setActiveTab] = useState('plugins');
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedCategory, setSelectedCategory] = useState('all');

  const categories = [
    { id: 'all', name: 'All Categories', icon: '🌟' },
    { id: 'ai', name: 'AI & Machine Learning', icon: '🤖' },
    { id: 'analytics', name: 'Analytics & Insights', icon: '📊' },
    { id: 'automation', name: 'Automation Tools', icon: '⚡' },
    { id: 'social', name: 'Social Media', icon: '📱' },
    { id: 'video', name: 'Video Processing', icon: '🎬' },
    { id: 'content', name: 'Content Creation', icon: '✍️' }
  ];

  const mockPlugins = [
    {
      id: 1,
      name: 'Advanced AI Content Generator',
      description: 'Generate high-quality content using GPT-4 and Claude AI models',
      category: 'ai',
      price: 29.99,
      rating: 4.8,
      downloads: 15420,
      developer: 'AI Labs Inc.',
      features: ['GPT-4 Integration', 'Multi-language Support', 'Custom Prompts', 'Batch Processing'],
      installed: false,
      premium: true
    },
    {
      id: 2,
      name: 'Real-time Sentiment Monitor',
      description: 'Monitor brand sentiment across all social platforms in real-time',
      category: 'analytics',
      price: 19.99,
      rating: 4.6,
      downloads: 8930,
      developer: 'DataFlow Solutions',
      features: ['Real-time Monitoring', 'Custom Alerts', 'Sentiment Trends', 'Competitor Analysis'],
      installed: true,
      premium: true
    },
    {
      id: 3,
      name: 'Smart Video Optimizer',
      description: 'Automatically optimize videos for different platforms using AI',
      category: 'video',
      price: 0,
      rating: 4.4,
      downloads: 23150,
      developer: 'VideoTech Pro',
      features: ['Auto-resize', 'Quality Enhancement', 'Format Conversion', 'Thumbnail Generation'],
      installed: false,
      premium: false
    },
    {
      id: 4,
      name: 'Advanced Automation Engine',
      description: 'Create complex workflows with conditional logic and API integrations',
      category: 'automation',
      price: 49.99,
      rating: 4.9,
      downloads: 5670,
      developer: 'AutoFlow Systems',
      features: ['Visual Workflow Builder', 'API Integrations', 'Conditional Logic', 'Error Handling'],
      installed: false,
      premium: true
    },
    {
      id: 5,
      name: 'Multi-Platform Scheduler Pro',
      description: 'Schedule content across 20+ social media platforms with optimal timing',
      category: 'social',
      price: 24.99,
      rating: 4.7,
      downloads: 12340,
      developer: 'SocialMax Ltd.',
      features: ['20+ Platforms', 'Optimal Timing', 'Bulk Upload', 'Performance Tracking'],
      installed: true,
      premium: true
    }
  ];

  const mockTemplates = [
    {
      id: 1,
      name: 'Viral Video Template Pack',
      description: 'Professional templates for creating viral social media videos',
      category: 'video',
      price: 15.99,
      rating: 4.8,
      downloads: 18750,
      creator: 'Creative Studio Pro',
      preview: '/api/placeholder/300/200',
      tags: ['Trending', 'Social Media', 'Viral', 'Professional']
    },
    {
      id: 2,
      name: 'E-commerce Content Kit',
      description: 'Complete content templates for e-commerce marketing campaigns',
      category: 'content',
      price: 0,
      rating: 4.5,
      downloads: 9420,
      creator: 'Marketing Experts',
      preview: '/api/placeholder/300/200',
      tags: ['E-commerce', 'Marketing', 'Sales', 'Conversion']
    }
  ];

  useEffect(() => {
    loadMarketplaceData();
  }, []);

  const loadMarketplaceData = async () => {
    try {
      setLoading(true);
      // In real app, load from API
      setPlugins(mockPlugins);
      setTemplates(mockTemplates);
    } catch (error) {
      console.error('Failed to load marketplace data:', error);
    } finally {
      setLoading(false);
    }
  };

  const installPlugin = async (pluginId: number) => {
    try {
      // In real app, call API
      setPlugins(plugins.map(p => 
        p.id === pluginId ? { ...p, installed: true } : p
      ));
      alert('Plugin installed successfully!');
    } catch (error) {
      console.error('Failed to install plugin:', error);
      alert('Failed to install plugin');
    }
  };

  const uninstallPlugin = async (pluginId: number) => {
    if (!confirm('Are you sure you want to uninstall this plugin?')) return;
    
    try {
      setPlugins(plugins.map(p => 
        p.id === pluginId ? { ...p, installed: false } : p
      ));
      alert('Plugin uninstalled successfully!');
    } catch (error) {
      console.error('Failed to uninstall plugin:', error);
      alert('Failed to uninstall plugin');
    }
  };

  const filteredItems = (activeTab === 'plugins' ? plugins : templates).filter(item => {
    const matchesSearch = item.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
                         item.description.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesCategory = selectedCategory === 'all' || item.category === selectedCategory;
    return matchesSearch && matchesCategory;
  });

  return (
    <div className="min-h-screen" style={{ backgroundColor: 'var(--aws-gray-50)' }}>
      {/* Header */}
      <div style={{ backgroundColor: 'var(--aws-blue)' }} className="text-white py-8">
        <div className="max-w-7xl mx-auto px-4">
          <div className="flex justify-between items-center">
            <div>
              <h1 className="text-3xl font-bold mb-2">🛒 Plugin Marketplace</h1>
              <p className="text-gray-300">Extend your NewsHub with powerful plugins and templates</p>
            </div>
            <div className="flex items-center space-x-3">
              <button className="aws-btn-secondary">
                📦 My Plugins
              </button>
              <button className="aws-btn-primary">
                🚀 Publish Plugin
              </button>
            </div>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 py-8">
        {/* Search and Filters */}
        <div className="mb-8 space-y-4">
          <div className="flex flex-col md:flex-row gap-4">
            <div className="flex-1">
              <input
                type="text"
                placeholder="Search plugins and templates..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="aws-input w-full"
              />
            </div>
            <select
              value={selectedCategory}
              onChange={(e) => setSelectedCategory(e.target.value)}
              className="aws-input md:w-64"
            >
              {categories.map(category => (
                <option key={category.id} value={category.id}>
                  {category.icon} {category.name}
                </option>
              ))}
            </select>
          </div>

          {/* Tabs */}
          <div className="flex space-x-1">
            {[
              { id: 'plugins', name: '🔌 Plugins', count: plugins.length },
              { id: 'templates', name: '📋 Templates', count: templates.length }
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
                <span className={`ml-2 px-2 py-1 rounded-full text-xs ${
                  activeTab === tab.id ? 'bg-orange-600' : 'bg-gray-200 text-gray-600'
                }`}>
                  {tab.count}
                </span>
              </button>
            ))}
          </div>
        </div>

        {loading ? (
          <div className="text-center py-12">
            <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-orange-500"></div>
            <p className="mt-2 text-gray-600">Loading marketplace...</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {filteredItems.map((item) => (
              <div key={item.id} className="aws-card overflow-hidden">
                {activeTab === 'templates' && (
                  <div className="h-48 bg-gray-200 flex items-center justify-center">
                    <span className="text-gray-500">Template Preview</span>
                  </div>
                )}
                
                <div className="p-6">
                  <div className="flex items-start justify-between mb-3">
                    <div className="flex-1">
                      <h3 className="text-lg font-semibold text-gray-900 mb-1">{item.name}</h3>
                      <p className="text-sm text-gray-600 mb-2">{item.description}</p>
                      <p className="text-xs text-gray-500">
                        by {activeTab === 'plugins' ? item.developer : item.creator}
                      </p>
                    </div>
                    {item.premium && (
                      <span className="px-2 py-1 bg-yellow-100 text-yellow-800 text-xs font-medium rounded">
                        PRO
                      </span>
                    )}
                  </div>

                  <div className="flex items-center space-x-4 mb-4 text-sm text-gray-600">
                    <div className="flex items-center">
                      <span className="text-yellow-500">⭐</span>
                      <span className="ml-1">{item.rating}</span>
                    </div>
                    <div>📥 {item.downloads.toLocaleString()}</div>
                    <div className="font-semibold text-gray-900">
                      {item.price === 0 ? 'Free' : `$${item.price}`}
                    </div>
                  </div>

                  {activeTab === 'plugins' && item.features && (
                    <div className="mb-4">
                      <div className="flex flex-wrap gap-1">
                        {item.features.slice(0, 3).map((feature, index) => (
                          <span
                            key={index}
                            className="px-2 py-1 bg-blue-100 text-blue-800 text-xs rounded"
                          >
                            {feature}
                          </span>
                        ))}
                        {item.features.length > 3 && (
                          <span className="px-2 py-1 bg-gray-100 text-gray-600 text-xs rounded">
                            +{item.features.length - 3} more
                          </span>
                        )}
                      </div>
                    </div>
                  )}

                  {activeTab === 'templates' && item.tags && (
                    <div className="mb-4">
                      <div className="flex flex-wrap gap-1">
                        {item.tags.map((tag, index) => (
                          <span
                            key={index}
                            className="px-2 py-1 bg-purple-100 text-purple-800 text-xs rounded"
                          >
                            #{tag}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}

                  <div className="flex space-x-2">
                    {activeTab === 'plugins' ? (
                      <>
                        {item.installed ? (
                          <button
                            onClick={() => uninstallPlugin(item.id)}
                            className="flex-1 px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors text-sm font-medium"
                          >
                            🗑️ Uninstall
                          </button>
                        ) : (
                          <button
                            onClick={() => installPlugin(item.id)}
                            className="flex-1 aws-btn-primary text-sm"
                          >
                            📥 Install
                          </button>
                        )}
                        <button className="px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition-colors text-sm">
                          👁️ Preview
                        </button>
                      </>
                    ) : (
                      <>
                        <button className="flex-1 aws-btn-primary text-sm">
                          📥 Download
                        </button>
                        <button className="px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition-colors text-sm">
                          👁️ Preview
                        </button>
                      </>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}

        {filteredItems.length === 0 && !loading && (
          <div className="text-center py-12">
            <svg className="w-16 h-16 text-gray-400 mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
            <p className="text-gray-500 text-lg mb-2">No items found</p>
            <p className="text-gray-400">Try adjusting your search or filters</p>
          </div>
        )}
      </div>
    </div>
  );
}