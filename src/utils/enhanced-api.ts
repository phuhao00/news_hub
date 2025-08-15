// Enhanced API methods for powerful features
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001/api';

const apiCall = async (url: string, options: RequestInit = {}) => {
  const token = localStorage.getItem('authToken');
  
  const defaultOptions: RequestInit = {
    headers: {
      'Content-Type': 'application/json',
      ...(token && { Authorization: `Bearer ${token}` }),
      ...options.headers,
    },
    ...options,
  };

  const response = await fetch(url, defaultOptions);
  
  if (!response.ok) {
    const error = await response.text();
    throw new Error(error || `HTTP error! status: ${response.status}`);
  }
  
  return response.json();
};

// Advanced Analytics API
export const analyticsApi = {
  getOverview: async (timeRange: string = '7d') => {
    return apiCall(`${API_BASE_URL}/analytics/overview?range=${timeRange}`);
  },

  getPlatformStats: async (platform: string, timeRange: string = '7d') => {
    return apiCall(`${API_BASE_URL}/analytics/platforms/${platform}?range=${timeRange}`);
  },

  getVideoPerformance: async (videoId: string) => {
    return apiCall(`${API_BASE_URL}/analytics/videos/${videoId}`);
  },

  getEngagementTrends: async (timeRange: string = '30d') => {
    return apiCall(`${API_BASE_URL}/analytics/engagement?range=${timeRange}`);
  },

  getAIInsights: async () => {
    return apiCall(`${API_BASE_URL}/analytics/ai-insights`);
  },

  getCompetitorAnalysis: async (competitors: string[]) => {
    return apiCall(`${API_BASE_URL}/analytics/competitors`, {
      method: 'POST',
      body: JSON.stringify({ competitors }),
    });
  },

  getTrendingTopics: async (platform: string) => {
    return apiCall(`${API_BASE_URL}/analytics/trending/${platform}`);
  },

  getAudienceInsights: async (platform: string) => {
    return apiCall(`${API_BASE_URL}/analytics/audience/${platform}`);
  },

  exportReport: async (type: string, timeRange: string) => {
    return apiCall(`${API_BASE_URL}/analytics/export`, {
      method: 'POST',
      body: JSON.stringify({ type, timeRange }),
    });
  },
};

// Automation API
export const automationApi = {
  list: async () => {
    return apiCall(`${API_BASE_URL}/automation/workflows`);
  },

  create: async (data: any) => {
    return apiCall(`${API_BASE_URL}/automation/workflows`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

  update: async (id: string, data: any) => {
    return apiCall(`${API_BASE_URL}/automation/workflows/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  },

  delete: async (id: string) => {
    return apiCall(`${API_BASE_URL}/automation/workflows/${id}`, {
      method: 'DELETE',
    });
  },

  execute: async (id: string) => {
    return apiCall(`${API_BASE_URL}/automation/workflows/${id}/execute`, {
      method: 'POST',
    });
  },

  getLogs: async (id: string) => {
    return apiCall(`${API_BASE_URL}/automation/workflows/${id}/logs`);
  },

  getTemplates: async () => {
    return apiCall(`${API_BASE_URL}/automation/templates`);
  },

  createFromTemplate: async (templateId: string, config: any) => {
    return apiCall(`${API_BASE_URL}/automation/workflows/from-template`, {
      method: 'POST',
      body: JSON.stringify({ templateId, config }),
    });
  },
};

// AI API
export const aiApi = {
  generateContent: async (data: { prompt: string; type: string; context?: any }) => {
    return apiCall(`${API_BASE_URL}/ai/generate-content`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

  optimizeContent: async (data: { content: string; platform: string; goal: string }) => {
    return apiCall(`${API_BASE_URL}/ai/optimize-content`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

  analyzeSentiment: async (content: string) => {
    return apiCall(`${API_BASE_URL}/ai/analyze-sentiment`, {
      method: 'POST',
      body: JSON.stringify({ content }),
    });
  },

  generateTags: async (content: string) => {
    return apiCall(`${API_BASE_URL}/ai/generate-tags`, {
      method: 'POST',
      body: JSON.stringify({ content }),
    });
  },

  predictPerformance: async (data: { content: string; platform: string; timing: string }) => {
    return apiCall(`${API_BASE_URL}/ai/predict-performance`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

  generateThumbnail: async (data: { videoId: string; style: string; text?: string }) => {
    return apiCall(`${API_BASE_URL}/ai/generate-thumbnail`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

  translateContent: async (data: { content: string; targetLanguage: string; platform: string }) => {
    return apiCall(`${API_BASE_URL}/ai/translate`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

  generateScript: async (data: { topic: string; duration: number; style: string; audience: string }) => {
    return apiCall(`${API_BASE_URL}/ai/generate-script`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

  enhanceVideo: async (data: { videoId: string; enhancements: string[] }) => {
    return apiCall(`${API_BASE_URL}/ai/enhance-video`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

  generateVoiceover: async (data: { script: string; voice: string; language: string }) => {
    return apiCall(`${API_BASE_URL}/ai/generate-voiceover`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },
};

// Team Collaboration API
export const teamApi = {
  getMembers: async () => {
    return apiCall(`${API_BASE_URL}/team/members`);
  },

  inviteMember: async (data: { email: string; role: string; permissions: string[] }) => {
    return apiCall(`${API_BASE_URL}/team/invite`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

  updateMemberRole: async (memberId: string, role: string) => {
    return apiCall(`${API_BASE_URL}/team/members/${memberId}/role`, {
      method: 'PUT',
      body: JSON.stringify({ role }),
    });
  },

  removeMember: async (memberId: string) => {
    return apiCall(`${API_BASE_URL}/team/members/${memberId}`, {
      method: 'DELETE',
    });
  },

  getProjects: async () => {
    return apiCall(`${API_BASE_URL}/team/projects`);
  },

  createProject: async (data: { name: string; description: string; members: string[] }) => {
    return apiCall(`${API_BASE_URL}/team/projects`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

  assignTask: async (data: { projectId: string; assigneeId: string; task: any }) => {
    return apiCall(`${API_BASE_URL}/team/tasks`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

  getNotifications: async () => {
    return apiCall(`${API_BASE_URL}/team/notifications`);
  },

  markNotificationRead: async (notificationId: string) => {
    return apiCall(`${API_BASE_URL}/team/notifications/${notificationId}/read`, {
      method: 'PUT',
    });
  },
};

// Advanced Content API
export const advancedContentApi = {
  bulkImport: async (data: { source: string; filters: any; schedule?: string }) => {
    return apiCall(`${API_BASE_URL}/content/bulk-import`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

  duplicateDetection: async () => {
    return apiCall(`${API_BASE_URL}/content/duplicates`);
  },

  contentModeration: async (contentId: string) => {
    return apiCall(`${API_BASE_URL}/content/${contentId}/moderate`, {
      method: 'POST',
    });
  },

  generateVariations: async (contentId: string, count: number) => {
    return apiCall(`${API_BASE_URL}/content/${contentId}/variations`, {
      method: 'POST',
      body: JSON.stringify({ count }),
    });
  },

  scheduleContent: async (data: { contentId: string; platforms: string[]; scheduleTime: string }) => {
    return apiCall(`${API_BASE_URL}/content/schedule`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

  getContentCalendar: async (month: string, year: string) => {
    return apiCall(`${API_BASE_URL}/content/calendar?month=${month}&year=${year}`);
  },

  archiveContent: async (contentIds: string[]) => {
    return apiCall(`${API_BASE_URL}/content/archive`, {
      method: 'POST',
      body: JSON.stringify({ contentIds }),
    });
  },

  exportContent: async (filters: any, format: string) => {
    return apiCall(`${API_BASE_URL}/content/export`, {
      method: 'POST',
      body: JSON.stringify({ filters, format }),
    });
  },
};

// Advanced Video API
export const advancedVideoApi = {
  batchGenerate: async (data: { contentIds: string[]; style: string; settings: any }) => {
    return apiCall(`${API_BASE_URL}/videos/batch-generate`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

  addSubtitles: async (videoId: string, language: string) => {
    return apiCall(`${API_BASE_URL}/videos/${videoId}/subtitles`, {
      method: 'POST',
      body: JSON.stringify({ language }),
    });
  },

  generateClips: async (videoId: string, clipCount: number) => {
    return apiCall(`${API_BASE_URL}/videos/${videoId}/clips`, {
      method: 'POST',
      body: JSON.stringify({ clipCount }),
    });
  },

  addWatermark: async (videoId: string, watermarkConfig: any) => {
    return apiCall(`${API_BASE_URL}/videos/${videoId}/watermark`, {
      method: 'POST',
      body: JSON.stringify(watermarkConfig),
    });
  },

  optimizeForPlatform: async (videoId: string, platform: string) => {
    return apiCall(`${API_BASE_URL}/videos/${videoId}/optimize/${platform}`, {
      method: 'POST',
    });
  },

  getVideoAnalytics: async (videoId: string, timeRange: string) => {
    return apiCall(`${API_BASE_URL}/videos/${videoId}/analytics?range=${timeRange}`);
  },

  createTemplate: async (videoId: string, templateName: string) => {
    return apiCall(`${API_BASE_URL}/videos/templates`, {
      method: 'POST',
      body: JSON.stringify({ videoId, templateName }),
    });
  },

  getTemplates: async () => {
    return apiCall(`${API_BASE_URL}/videos/templates`);
  },
};

// Integration API
export const integrationApi = {
  getConnectedPlatforms: async () => {
    return apiCall(`${API_BASE_URL}/integrations/platforms`);
  },

  connectPlatform: async (platform: string, credentials: any) => {
    return apiCall(`${API_BASE_URL}/integrations/connect`, {
      method: 'POST',
      body: JSON.stringify({ platform, credentials }),
    });
  },

  disconnectPlatform: async (platform: string) => {
    return apiCall(`${API_BASE_URL}/integrations/disconnect`, {
      method: 'POST',
      body: JSON.stringify({ platform }),
    });
  },

  testConnection: async (platform: string) => {
    return apiCall(`${API_BASE_URL}/integrations/test/${platform}`, {
      method: 'POST',
    });
  },

  syncPlatformData: async (platform: string) => {
    return apiCall(`${API_BASE_URL}/integrations/sync/${platform}`, {
      method: 'POST',
    });
  },

  getWebhooks: async () => {
    return apiCall(`${API_BASE_URL}/integrations/webhooks`);
  },

  createWebhook: async (data: { url: string; events: string[]; platform: string }) => {
    return apiCall(`${API_BASE_URL}/integrations/webhooks`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },
};

// Settings API
export const settingsApi = {
  getProfile: async () => {
    return apiCall(`${API_BASE_URL}/settings/profile`);
  },

  updateProfile: async (data: any) => {
    return apiCall(`${API_BASE_URL}/settings/profile`, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  },

  getPreferences: async () => {
    return apiCall(`${API_BASE_URL}/settings/preferences`);
  },

  updatePreferences: async (data: any) => {
    return apiCall(`${API_BASE_URL}/settings/preferences`, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  },

  getBilling: async () => {
    return apiCall(`${API_BASE_URL}/settings/billing`);
  },

  updateBilling: async (data: any) => {
    return apiCall(`${API_BASE_URL}/settings/billing`, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  },

  getUsageStats: async () => {
    return apiCall(`${API_BASE_URL}/settings/usage`);
  },

  exportData: async (dataTypes: string[]) => {
    return apiCall(`${API_BASE_URL}/settings/export`, {
      method: 'POST',
      body: JSON.stringify({ dataTypes }),
    });
  },

  deleteAccount: async (confirmation: string) => {
    return apiCall(`${API_BASE_URL}/settings/delete-account`, {
      method: 'DELETE',
      body: JSON.stringify({ confirmation }),
    });
  },
};

// Marketplace API
export const marketplaceApi = {
  getPlugins: async (category?: string) => {
    const url = category 
      ? `${API_BASE_URL}/marketplace/plugins?category=${category}`
      : `${API_BASE_URL}/marketplace/plugins`;
    return apiCall(url);
  },

  getTemplates: async (category?: string) => {
    const url = category 
      ? `${API_BASE_URL}/marketplace/templates?category=${category}`
      : `${API_BASE_URL}/marketplace/templates`;
    return apiCall(url);
  },

  installPlugin: async (pluginId: string) => {
    return apiCall(`${API_BASE_URL}/marketplace/plugins/${pluginId}/install`, {
      method: 'POST',
    });
  },

  uninstallPlugin: async (pluginId: string) => {
    return apiCall(`${API_BASE_URL}/marketplace/plugins/${pluginId}/uninstall`, {
      method: 'DELETE',
    });
  },

  downloadTemplate: async (templateId: string) => {
    return apiCall(`${API_BASE_URL}/marketplace/templates/${templateId}/download`, {
      method: 'POST',
    });
  },

  getInstalledPlugins: async () => {
    return apiCall(`${API_BASE_URL}/marketplace/installed`);
  },

  ratePlugin: async (pluginId: string, rating: number, review?: string) => {
    return apiCall(`${API_BASE_URL}/marketplace/plugins/${pluginId}/rate`, {
      method: 'POST',
      body: JSON.stringify({ rating, review }),
    });
  },
};

// Integrations API
export const integrationsApi = {
  list: async () => {
    return apiCall(`${API_BASE_URL}/integrations`);
  },

  connect: async (integrationId: string, config: any) => {
    return apiCall(`${API_BASE_URL}/integrations/${integrationId}/connect`, {
      method: 'POST',
      body: JSON.stringify(config),
    });
  },

  disconnect: async (integrationId: string) => {
    return apiCall(`${API_BASE_URL}/integrations/${integrationId}/disconnect`, {
      method: 'DELETE',
    });
  },

  updateConfig: async (integrationId: string, config: any) => {
    return apiCall(`${API_BASE_URL}/integrations/${integrationId}/config`, {
      method: 'PUT',
      body: JSON.stringify(config),
    });
  },

  testConnection: async (integrationId: string) => {
    return apiCall(`${API_BASE_URL}/integrations/${integrationId}/test`, {
      method: 'POST',
    });
  },

  getStatus: async (integrationId: string) => {
    return apiCall(`${API_BASE_URL}/integrations/${integrationId}/status`);
  },
};

// Monitoring API
export const monitoringApi = {
  getSystemHealth: async () => {
    return apiCall(`${API_BASE_URL}/monitoring/health`);
  },

  getMetrics: async (timeRange: string = '1h') => {
    return apiCall(`${API_BASE_URL}/monitoring/metrics?range=${timeRange}`);
  },

  getAlerts: async () => {
    return apiCall(`${API_BASE_URL}/monitoring/alerts`);
  },

  createAlert: async (data: any) => {
    return apiCall(`${API_BASE_URL}/monitoring/alerts`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

  updateAlert: async (alertId: string, data: any) => {
    return apiCall(`${API_BASE_URL}/monitoring/alerts/${alertId}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  },

  deleteAlert: async (alertId: string) => {
    return apiCall(`${API_BASE_URL}/monitoring/alerts/${alertId}`, {
      method: 'DELETE',
    });
  },

  acknowledgeAlert: async (alertId: string) => {
    return apiCall(`${API_BASE_URL}/monitoring/alerts/${alertId}/acknowledge`, {
      method: 'POST',
    });
  },

  resolveAlert: async (alertId: string) => {
    return apiCall(`${API_BASE_URL}/monitoring/alerts/${alertId}/resolve`, {
      method: 'POST',
    });
  },

  getPerformanceMetrics: async (service: string, timeRange: string = '1h') => {
    return apiCall(`${API_BASE_URL}/monitoring/performance/${service}?range=${timeRange}`);
  },

  getLogs: async (service: string, level: string = 'all', limit: number = 100) => {
    return apiCall(`${API_BASE_URL}/monitoring/logs/${service}?level=${level}&limit=${limit}`);
  },
};
