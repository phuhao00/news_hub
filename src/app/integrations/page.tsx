'use client';

import { useState, useEffect } from 'react';
import { integrationsApi } from '@/utils/enhanced-api';

export default function IntegrationsPage() {
  const [integrations, setIntegrations] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [showConfigModal, setShowConfigModal] = useState(false);
  const [selectedIntegration, setSelectedIntegration] = useState<any>(null);
  const [configData, setConfigData] = useState<any>({});

  const availableIntegrations = [
    {
      id: 'openai',
      name: 'OpenAI GPT',
      description: 'Integrate with OpenAI GPT models for advanced content generation',
      category: 'AI',
      icon: '🤖',
      status: 'connected',
      features: ['Content Generation', 'Text Completion', 'Language Translation', 'Summarization'],
      config: {
        apiKey: '••••••••••••••••',
        model: 'gpt-4',
        maxTokens: 2000
      }
    },
    {
      id: 'claude',
      name: 'Anthropic Claude',
      description: 'Advanced AI assistant for content creation and analysis',
      category: 'AI',
      icon: '🧠',
      status: 'available',
      features: ['Content Analysis', 'Creative Writing', 'Code Generation', 'Research'],
      config: {}
    },
    {
      id: 'google-analytics',
      name: 'Google Analytics',
      description: 'Track and analyze your content performance across platforms',
      category: 'Analytics',
      icon: '📊',
      status: 'connected',
      features: ['Traffic Analysis', 'User Behavior', 'Conversion Tracking', 'Custom Reports'],
      config: {
        trackingId: 'GA-••••••••',
        propertyId: '••••••••'
      }
    },
    {
      id: 'zapier',
      name: 'Zapier',
      description: 'Connect with 5000+ apps through Zapier automation',
      category: 'Automation',
      icon: '⚡',
      status: 'available',
      features: ['Workflow Automation', '5000+ App Integrations', 'Trigger Actions', 'Data Sync'],
      config: {}
    },
    {
      id: 'slack',
      name: 'Slack',
      description: 'Send notifications and updates to your Slack workspace',
      category: 'Communication',
      icon: '💬',
      status: 'connected',
      features: ['Real-time Notifications', 'Team Updates', 'Alert System', 'Custom Channels'],
      config: {
        webhookUrl: '••••••••••••••••',
        channel: '#newsHub-alerts'
      }
    },
    {
      id: 'discord',
      name: 'Discord',
      description: 'Integrate with Discord for community management',
      category: 'Communication',
      icon: '🎮',
      status: 'available',
      features: ['Bot Integration', 'Community Alerts', 'Content Sharing', 'Moderation'],
      config: {}
    },
    {
      id: 'aws-s3',
      name: 'Amazon S3',
      description: 'Store and manage your media files in AWS S3',
      category: 'Storage',
      icon: '☁️',
      status: 'connected',
      features: ['File Storage', 'CDN Integration', 'Backup & Archive', 'Media Processing'],
      config: {
        bucketName: 'newsHub-media',
        region: 'us-east-1'
      }
    },
    {
      id: 'cloudflare',
      name: 'Cloudflare',
      description: 'CDN and security services for your content delivery',
      category: 'Infrastructure',
      icon: '🛡️',
      status: 'available',
      features: ['CDN', 'DDoS Protection', 'SSL/TLS', 'Performance Optimization'],
      config: {}
    },
    {
      id: 'stripe',
      name: 'Stripe',
      description: 'Payment processing for premium features and subscriptions',
      category: 'Payment',
      icon: '💳',
      status: 'available',
      features: ['Payment Processing', 'Subscription Management', 'Invoice Generation', 'Analytics'],
      config: {}
    },
    {
      id: 'sendgrid',
      name: 'SendGrid',
      description: 'Email delivery and marketing automation',
      category: 'Email',
      icon: '📧',
      status: 'connected',
      features: ['Email Delivery', 'Template Management', 'Analytics', 'A/B Testing'],
      config: {
        apiKey: '••••••••••••••••',
        fromEmail: 'noreply@newsHub.com'
      }
    }
  ];

  useEffect(() => {
    loadIntegrations();
  }, []);

  const loadIntegrations = async () => {
    try {
      setLoading(true);
      // In real app, load from API
      setIntegrations(availableIntegrations);
    } catch (error) {
      console.error('Failed to load integrations:', error);
      setIntegrations([]);
    } finally {
      setLoading(false);
    }
  };

  const connectIntegration = async (integrationId: string) => {
    const integration = integrations.find(i => i.id === integrationId);
    if (!integration) return;

    setSelectedIntegration(integration);
    setConfigData(integration.config || {});
    setShowConfigModal(true);
  };

  const saveIntegrationConfig = async () => {
    if (!selectedIntegration) return;

    try {
      // In real app, save to API
      setIntegrations(integrations.map(i => 
        i.id === selectedIntegration.id 
          ? { ...i, status: 'connected', config: configData }
          : i
      ));
      setShowConfigModal(false);
      setSelectedIntegration(null);
      setConfigData({});
      alert('Integration configured successfully!');
    } catch (error) {
      console.error('Failed to save integration config:', error);
      alert('Failed to configure integration');
    }
  };

  const disconnectIntegration = async (integrationId: string) => {
    if (!confirm('Are you sure you want to disconnect this integration?')) return;

    try {
      setIntegrations(integrations.map(i => 
        i.id === integrationId 
          ? { ...i, status: 'available', config: {} }
          : i
      ));
      alert('Integration disconnected successfully!');
    } catch (error) {
      console.error('Failed to disconnect integration:', error);
      alert('Failed to disconnect integration');
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'connected': return 'text-green-600 bg-green-100';
      case 'available': return 'text-gray-600 bg-gray-100';
      case 'error': return 'text-red-600 bg-red-100';
      default: return 'text-gray-600 bg-gray-100';
    }
  };

  const getCategoryColor = (category: string) => {
    switch (category) {
      case 'AI': return 'text-purple-600 bg-purple-100';
      case 'Analytics': return 'text-blue-600 bg-blue-100';
      case 'Automation': return 'text-orange-600 bg-orange-100';
      case 'Communication': return 'text-green-600 bg-green-100';
      case 'Storage': return 'text-indigo-600 bg-indigo-100';
      case 'Infrastructure': return 'text-gray-600 bg-gray-100';
      case 'Payment': return 'text-yellow-600 bg-yellow-100';
      case 'Email': return 'text-red-600 bg-red-100';
      default: return 'text-gray-600 bg-gray-100';
    }
  };

  const categories = [...new Set(integrations.map(i => i.category))];
  const connectedCount = integrations.filter(i => i.status === 'connected').length;

  return (
    <div className="min-h-screen" style={{ backgroundColor: 'var(--aws-gray-50)' }}>
      {/* Header */}
      <div style={{ backgroundColor: 'var(--aws-blue)' }} className="text-white py-8">
        <div className="max-w-7xl mx-auto px-4">
          <div className="flex justify-between items-center">
            <div>
              <h1 className="text-3xl font-bold mb-2">🔗 Integrations Hub</h1>
              <p className="text-gray-300">Connect NewsHub with your favorite tools and services</p>
            </div>
            <div className="text-right">
              <div className="text-2xl font-bold">{connectedCount}</div>
              <div className="text-sm text-gray-300">Connected Services</div>
            </div>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 py-8">
        {loading ? (
          <div className="text-center py-12">
            <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-orange-500"></div>
            <p className="mt-2 text-gray-600">Loading integrations...</p>
          </div>
        ) : (
          <div className="space-y-8">
            {/* Quick Stats */}
            <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
              <div className="aws-card p-6">
                <div className="text-2xl font-bold text-gray-900">{integrations.length}</div>
                <div className="text-sm text-gray-600">Available Integrations</div>
              </div>
              <div className="aws-card p-6">
                <div className="text-2xl font-bold text-green-600">{connectedCount}</div>
                <div className="text-sm text-gray-600">Connected Services</div>
              </div>
              <div className="aws-card p-6">
                <div className="text-2xl font-bold text-blue-600">{categories.length}</div>
                <div className="text-sm text-gray-600">Categories</div>
              </div>
              <div className="aws-card p-6">
                <div className="text-2xl font-bold text-purple-600">24/7</div>
                <div className="text-sm text-gray-600">Monitoring</div>
              </div>
            </div>

            {/* Integrations by Category */}
            {categories.map(category => (
              <div key={category} className="aws-card">
                <div className="p-6 border-b border-gray-200">
                  <div className="flex items-center space-x-3">
                    <span className={`px-3 py-1 rounded-full text-sm font-medium ${getCategoryColor(category)}`}>
                      {category}
                    </span>
                    <h2 className="text-xl font-semibold">{category} Integrations</h2>
                  </div>
                </div>
                
                <div className="p-6">
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                    {integrations
                      .filter(integration => integration.category === category)
                      .map((integration) => (
                        <div key={integration.id} className="border border-gray-200 rounded-lg p-6 hover:shadow-md transition-shadow">
                          <div className="flex items-start justify-between mb-4">
                            <div className="flex items-center space-x-3">
                              <div className="w-12 h-12 bg-gray-100 rounded-lg flex items-center justify-center text-2xl">
                                {integration.icon}
                              </div>
                              <div>
                                <h3 className="font-semibold text-gray-900">{integration.name}</h3>
                                <span className={`px-2 py-1 rounded-full text-xs font-medium ${getStatusColor(integration.status)}`}>
                                  {integration.status}
                                </span>
                              </div>
                            </div>
                          </div>
                          
                          <p className="text-sm text-gray-600 mb-4">{integration.description}</p>
                          
                          <div className="mb-4">
                            <div className="text-xs text-gray-500 mb-2">Features:</div>
                            <div className="flex flex-wrap gap-1">
                              {integration.features.slice(0, 3).map((feature, index) => (
                                <span
                                  key={index}
                                  className="px-2 py-1 bg-blue-100 text-blue-800 text-xs rounded"
                                >
                                  {feature}
                                </span>
                              ))}
                              {integration.features.length > 3 && (
                                <span className="px-2 py-1 bg-gray-100 text-gray-600 text-xs rounded">
                                  +{integration.features.length - 3}
                                </span>
                              )}
                            </div>
                          </div>
                          
                          <div className="flex space-x-2">
                            {integration.status === 'connected' ? (
                              <>
                                <button
                                  onClick={() => connectIntegration(integration.id)}
                                  className="flex-1 px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition-colors text-sm"
                                >
                                  ⚙️ Configure
                                </button>
                                <button
                                  onClick={() => disconnectIntegration(integration.id)}
                                  className="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors text-sm"
                                >
                                  🔌 Disconnect
                                </button>
                              </>
                            ) : (
                              <button
                                onClick={() => connectIntegration(integration.id)}
                                className="flex-1 aws-btn-primary text-sm"
                              >
                                🔗 Connect
                              </button>
                            )}
                          </div>
                        </div>
                      ))}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Configuration Modal */}
      {showConfigModal && selectedIntegration && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg max-w-md w-full mx-4 max-h-[90vh] overflow-y-auto">
            <div className="p-6 border-b border-gray-200">
              <div className="flex items-center space-x-3">
                <span className="text-2xl">{selectedIntegration.icon}</span>
                <h2 className="text-xl font-semibold">Configure {selectedIntegration.name}</h2>
              </div>
            </div>
            
            <div className="p-6 space-y-4">
              <p className="text-sm text-gray-600 mb-4">
                {selectedIntegration.description}
              </p>
              
              {selectedIntegration.id === 'openai' && (
                <>
                  <div>
                    <label className="block text-sm font-medium mb-2">API Key</label>
                    <input
                      type="password"
                      value={configData.apiKey || ''}
                      onChange={(e) => setConfigData({ ...configData, apiKey: e.target.value })}
                      placeholder="Enter your OpenAI API key..."
                      className="aws-input w-full"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium mb-2">Model</label>
                    <select
                      value={configData.model || 'gpt-4'}
                      onChange={(e) => setConfigData({ ...configData, model: e.target.value })}
                      className="aws-input w-full"
                    >
                      <option value="gpt-4">GPT-4</option>
                      <option value="gpt-3.5-turbo">GPT-3.5 Turbo</option>
                      <option value="gpt-4-turbo">GPT-4 Turbo</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-sm font-medium mb-2">Max Tokens</label>
                    <input
                      type="number"
                      value={configData.maxTokens || 2000}
                      onChange={(e) => setConfigData({ ...configData, maxTokens: parseInt(e.target.value) })}
                      className="aws-input w-full"
                    />
                  </div>
                </>
              )}

              {selectedIntegration.id === 'claude' && (
                <>
                  <div>
                    <label className="block text-sm font-medium mb-2">API Key</label>
                    <input
                      type="password"
                      value={configData.apiKey || ''}
                      onChange={(e) => setConfigData({ ...configData, apiKey: e.target.value })}
                      placeholder="Enter your Anthropic API key..."
                      className="aws-input w-full"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium mb-2">Model</label>
                    <select
                      value={configData.model || 'claude-3-opus'}
                      onChange={(e) => setConfigData({ ...configData, model: e.target.value })}
                      className="aws-input w-full"
                    >
                      <option value="claude-3-opus">Claude 3 Opus</option>
                      <option value="claude-3-sonnet">Claude 3 Sonnet</option>
                      <option value="claude-3-haiku">Claude 3 Haiku</option>
                    </select>
                  </div>
                </>
              )}

              {selectedIntegration.id === 'google-analytics' && (
                <>
                  <div>
                    <label className="block text-sm font-medium mb-2">Tracking ID</label>
                    <input
                      type="text"
                      value={configData.trackingId || ''}
                      onChange={(e) => setConfigData({ ...configData, trackingId: e.target.value })}
                      placeholder="GA-XXXXXXXXX"
                      className="aws-input w-full"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium mb-2">Property ID</label>
                    <input
                      type="text"
                      value={configData.propertyId || ''}
                      onChange={(e) => setConfigData({ ...configData, propertyId: e.target.value })}
                      placeholder="Enter your GA4 Property ID..."
                      className="aws-input w-full"
                    />
                  </div>
                </>
              )}

              {selectedIntegration.id === 'slack' && (
                <>
                  <div>
                    <label className="block text-sm font-medium mb-2">Webhook URL</label>
                    <input
                      type="url"
                      value={configData.webhookUrl || ''}
                      onChange={(e) => setConfigData({ ...configData, webhookUrl: e.target.value })}
                      placeholder="https://hooks.slack.com/services/..."
                      className="aws-input w-full"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium mb-2">Channel</label>
                    <input
                      type="text"
                      value={configData.channel || ''}
                      onChange={(e) => setConfigData({ ...configData, channel: e.target.value })}
                      placeholder="#channel-name"
                      className="aws-input w-full"
                    />
                  </div>
                </>
              )}

              {selectedIntegration.id === 'aws-s3' && (
                <>
                  <div>
                    <label className="block text-sm font-medium mb-2">Access Key ID</label>
                    <input
                      type="text"
                      value={configData.accessKeyId || ''}
                      onChange={(e) => setConfigData({ ...configData, accessKeyId: e.target.value })}
                      placeholder="Enter AWS Access Key ID..."
                      className="aws-input w-full"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium mb-2">Secret Access Key</label>
                    <input
                      type="password"
                      value={configData.secretAccessKey || ''}
                      onChange={(e) => setConfigData({ ...configData, secretAccessKey: e.target.value })}
                      placeholder="Enter AWS Secret Access Key..."
                      className="aws-input w-full"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium mb-2">Bucket Name</label>
                    <input
                      type="text"
                      value={configData.bucketName || ''}
                      onChange={(e) => setConfigData({ ...configData, bucketName: e.target.value })}
                      placeholder="your-bucket-name"
                      className="aws-input w-full"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium mb-2">Region</label>
                    <select
                      value={configData.region || 'us-east-1'}
                      onChange={(e) => setConfigData({ ...configData, region: e.target.value })}
                      className="aws-input w-full"
                    >
                      <option value="us-east-1">US East (N. Virginia)</option>
                      <option value="us-west-2">US West (Oregon)</option>
                      <option value="eu-west-1">Europe (Ireland)</option>
                      <option value="ap-southeast-1">Asia Pacific (Singapore)</option>
                    </select>
                  </div>
                </>
              )}

              {selectedIntegration.id === 'sendgrid' && (
                <>
                  <div>
                    <label className="block text-sm font-medium mb-2">API Key</label>
                    <input
                      type="password"
                      value={configData.apiKey || ''}
                      onChange={(e) => setConfigData({ ...configData, apiKey: e.target.value })}
                      placeholder="Enter SendGrid API key..."
                      className="aws-input w-full"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium mb-2">From Email</label>
                    <input
                      type="email"
                      value={configData.fromEmail || ''}
                      onChange={(e) => setConfigData({ ...configData, fromEmail: e.target.value })}
                      placeholder="noreply@yourdomain.com"
                      className="aws-input w-full"
                    />
                  </div>
                </>
              )}

              {/* Generic configuration for other integrations */}
              {!['openai', 'claude', 'google-analytics', 'slack', 'aws-s3', 'sendgrid'].includes(selectedIntegration.id) && (
                <div>
                  <label className="block text-sm font-medium mb-2">API Key / Token</label>
                  <input
                    type="password"
                    value={configData.apiKey || ''}
                    onChange={(e) => setConfigData({ ...configData, apiKey: e.target.value })}
                    placeholder="Enter your API key or token..."
                    className="aws-input w-full"
                  />
                </div>
              )}
            </div>
            
            <div className="p-6 border-t border-gray-200 flex justify-end space-x-3">
              <button
                onClick={() => {
                  setShowConfigModal(false);
                  setSelectedIntegration(null);
                  setConfigData({});
                }}
                className="px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={saveIntegrationConfig}
                className="aws-btn-primary"
              >
                Save Configuration
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
