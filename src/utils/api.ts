// API基础配置
const BACKEND_API_URL = 'http://localhost:8081/api';
const CRAWLER_API_URL = 'http://localhost:8001';

// 创作者相关API
export const creatorApi = {
  create: async (data: { username: string; platform: string }) => {
    const response = await fetch(`${BACKEND_API_URL}/creators`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    if (!response.ok) throw new Error('Failed to create creator');
    return response.json();
  },

  list: async () => {
    const response = await fetch(`${BACKEND_API_URL}/creators`);
    if (!response.ok) throw new Error('Failed to fetch creators');
    return response.json();
  },

  delete: async (id: string) => {
    const response = await fetch(`${BACKEND_API_URL}/creators/${id}`, {
      method: 'DELETE',
    });
    if (!response.ok) throw new Error('Failed to delete creator');
    return response.json();
  },
};

// AI助手相关API
export const aiApi = {
  chat: async (data: { message: string; conversationId?: string }) => {
    const response = await fetch(`${CRAWLER_API_URL}/ai/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    if (!response.ok) throw new Error('Failed to send chat message');
    return response.json();
  },

  generateContent: async (data: { prompt: string; type: string; context?: any }) => {
    const response = await fetch(`${CRAWLER_API_URL}/ai/generate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    if (!response.ok) throw new Error('Failed to generate content');
    return response.json();
  },

  optimizeContent: async (data: { content: string; platform: string; goal: string }) => {
    const response = await fetch(`${CRAWLER_API_URL}/ai/optimize`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    if (!response.ok) throw new Error('Failed to optimize content');
    return response.json();
  },

  analyzeSentiment: async (content: string) => {
    const response = await fetch(`${CRAWLER_API_URL}/ai/sentiment`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ content }),
    });
    if (!response.ok) throw new Error('Failed to analyze sentiment');
    return response.json();
  },

  generateTags: async (content: string) => {
    const response = await fetch(`${CRAWLER_API_URL}/ai/tags`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ content }),
    });
    if (!response.ok) throw new Error('Failed to generate tags');
    return response.json();
  },

  predictPerformance: async (data: { content: string; platform: string; timing: string }) => {
    const response = await fetch(`${CRAWLER_API_URL}/ai/predict`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    if (!response.ok) throw new Error('Failed to predict performance');
    return response.json();
  },

  conversations: async () => {
    const response = await fetch(`${CRAWLER_API_URL}/ai/conversations`);
    if (!response.ok) throw new Error('Failed to fetch conversations');
    return response.json();
  },

  deleteConversation: async (id: string) => {
    const response = await fetch(`${CRAWLER_API_URL}/ai/conversations/${id}`, {
      method: 'DELETE',
    });
    if (!response.ok) throw new Error('Failed to delete conversation');
    return response.json();
  },

  getInsights: async () => {
    const response = await fetch(`${CRAWLER_API_URL}/ai/insights`);
    if (!response.ok) throw new Error('Failed to get insights');
    return response.json();
  },
};

// 分析相关API
export const analyticsApi = {
  getOverview: async (timeRange?: string) => {
    const searchParams = new URLSearchParams();
    if (timeRange) searchParams.append('timeRange', timeRange);
    
    const response = await fetch(`${BACKEND_API_URL}/analytics/overview?${searchParams}`);
    if (!response.ok) throw new Error('Failed to fetch analytics overview');
    return response.json();
  },

  overview: async () => {
    const response = await fetch(`${BACKEND_API_URL}/analytics/overview`);
    if (!response.ok) throw new Error('Failed to fetch analytics overview');
    return response.json();
  },

  performance: async (params?: { period?: string; platform?: string }) => {
    const searchParams = new URLSearchParams();
    if (params?.period) searchParams.append('period', params.period);
    if (params?.platform) searchParams.append('platform', params.platform);
    
    const response = await fetch(`${BACKEND_API_URL}/analytics/performance?${searchParams}`);
    if (!response.ok) throw new Error('Failed to fetch performance analytics');
    return response.json();
  },

  engagement: async (params?: { period?: string; contentType?: string }) => {
    const searchParams = new URLSearchParams();
    if (params?.period) searchParams.append('period', params.period);
    if (params?.contentType) searchParams.append('contentType', params.contentType);
    
    const response = await fetch(`${BACKEND_API_URL}/analytics/engagement?${searchParams}`);
    if (!response.ok) throw new Error('Failed to fetch engagement analytics');
    return response.json();
  },
};

// 自动化相关API
export const automationApi = {
  list: async () => {
    const response = await fetch(`${BACKEND_API_URL}/automation/workflows`);
    if (!response.ok) throw new Error('Failed to fetch workflows');
    return response.json();
  },

  create: async (data: { name: string; description: string; triggers: any[]; actions: any[] }) => {
    const response = await fetch(`${BACKEND_API_URL}/automation/workflows`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    if (!response.ok) throw new Error('Failed to create workflow');
    return response.json();
  },

  update: async (id: string, data: { name?: string; description?: string; triggers?: any[]; actions?: any[]; enabled?: boolean }) => {
    const response = await fetch(`${BACKEND_API_URL}/automation/workflows/${id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    if (!response.ok) throw new Error('Failed to update workflow');
    return response.json();
  },

  delete: async (id: string) => {
    const response = await fetch(`${BACKEND_API_URL}/automation/workflows/${id}`, {
      method: 'DELETE',
    });
    if (!response.ok) throw new Error('Failed to delete workflow');
    return response.json();
  },

  execute: async (id: string) => {
    const response = await fetch(`${BACKEND_API_URL}/automation/workflows/${id}/execute`, {
      method: 'POST',
    });
    if (!response.ok) throw new Error('Failed to execute workflow');
    return response.json();
  },

  workflows: {
    list: async () => {
      const response = await fetch(`${BACKEND_API_URL}/automation/workflows`);
      if (!response.ok) throw new Error('Failed to fetch workflows');
      return response.json();
    },

    create: async (data: { name: string; description: string; triggers: any[]; actions: any[] }) => {
      const response = await fetch(`${BACKEND_API_URL}/automation/workflows`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
      });
      if (!response.ok) throw new Error('Failed to create workflow');
      return response.json();
    },

    update: async (id: string, data: { name?: string; description?: string; triggers?: any[]; actions?: any[]; active?: boolean }) => {
      const response = await fetch(`${BACKEND_API_URL}/automation/workflows/${id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
      });
      if (!response.ok) throw new Error('Failed to update workflow');
      return response.json();
    },

    delete: async (id: string) => {
      const response = await fetch(`${BACKEND_API_URL}/automation/workflows/${id}`, {
        method: 'DELETE',
      });
      if (!response.ok) throw new Error('Failed to delete workflow');
      return response.json();
    },

    execute: async (id: string) => {
      const response = await fetch(`${BACKEND_API_URL}/automation/workflows/${id}/execute`, {
        method: 'POST',
      });
      if (!response.ok) throw new Error('Failed to execute workflow');
      return response.json();
    },
  },

  templates: async () => {
    const response = await fetch(`${BACKEND_API_URL}/automation/templates`);
    if (!response.ok) throw new Error('Failed to fetch workflow templates');
    return response.json();
  },

  executions: async (workflowId?: string) => {
    const searchParams = new URLSearchParams();
    if (workflowId) searchParams.append('workflowId', workflowId);
    
    const response = await fetch(`${BACKEND_API_URL}/automation/executions?${searchParams}`);
    if (!response.ok) throw new Error('Failed to fetch workflow executions');
    return response.json();
  },
};

// 视频生成相关API
export const videoApi = {
  generate: async (data: { postIds: string[]; style: string; duration: number }) => {
    const response = await fetch(`${BACKEND_API_URL}/videos/generate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    if (!response.ok) throw new Error('Failed to generate video');
    return response.json();
  },

  list: async () => {
    const response = await fetch(`${BACKEND_API_URL}/videos`);
    if (!response.ok) throw new Error('Failed to fetch videos');
    return response.json();
  },
};

// 发布任务相关API
export const publishApi = {
  create: async (data: { videoId: string; platforms: string[]; description: string }) => {
    const response = await fetch(`${BACKEND_API_URL}/publish`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    if (!response.ok) throw new Error('Failed to create publish task');
    return response.json();
  },

  list: async () => {
    const response = await fetch(`${BACKEND_API_URL}/publish/tasks`);
    if (!response.ok) throw new Error('Failed to fetch publish tasks');
    return response.json();
  },
};

// 爬虫相关API
export const crawlerApi = {
  trigger: async (data: { platform: string; creator_url: string; limit?: number }) => {
    const response = await fetch(`${CRAWLER_API_URL}/crawler/trigger`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`Failed to trigger crawler: ${errorText}`);
    }
    return response.json();
  },

  status: async () => {
    const response = await fetch(`${CRAWLER_API_URL}/crawler/status`);
    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`Failed to get crawler status: ${errorText}`);
    }
    return response.json();
  },

  platforms: async () => {
    const response = await fetch(`${CRAWLER_API_URL}/crawler/platforms`);
    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`Failed to get crawler platforms: ${errorText}`);
    }
    return response.json();
  },

  // 任务管理相关API
  tasks: {
    create: async (data: { platform: string; creator_url: string; limit?: number }) => {
      const response = await fetch(`${BACKEND_API_URL}/crawler/tasks`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
      });
      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`Failed to create crawler task: ${errorText}`);
      }
      return response.json();
    },

    list: async () => {
      const response = await fetch(`${BACKEND_API_URL}/crawler/tasks`);
      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`Failed to get crawler tasks: ${errorText}`);
      }
      return response.json();
    },

    get: async (id: string) => {
      const response = await fetch(`${BACKEND_API_URL}/crawler/tasks/${id}`);
      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`Failed to get crawler task: ${errorText}`);
      }
      return response.json();
    },

    updateStatus: async (id: string, data: { status: string; error?: string }) => {
      const response = await fetch(`${BACKEND_API_URL}/crawler/tasks/${id}/status`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
      });
      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`Failed to update task status: ${errorText}`);
      }
      return response.json();
    },
  },

  // 内容管理相关API
  contents: {
    list: async (taskId?: string) => {
      const params = new URLSearchParams();
      if (taskId) params.append('task_id', taskId);
      
      const response = await fetch(`${BACKEND_API_URL}/crawler/contents?${params}`);
      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`Failed to get crawler contents: ${errorText}`);
      }
      return response.json();
    },
  },
};

// 内容相关API
export const postApi = {
  list: async (params?: { creatorId?: string; platform?: string; limit?: number }) => {
    const searchParams = new URLSearchParams();
    if (params?.creatorId) searchParams.append('creatorId', params.creatorId);
    if (params?.platform) searchParams.append('platform', params.platform);
    if (params?.limit) searchParams.append('limit', params.limit.toString());
    
    const response = await fetch(`${BACKEND_API_URL}/posts?${searchParams}`);
    if (!response.ok) throw new Error('Failed to fetch posts');
    return response.json();
  },

  get: async (id: string) => {
    const response = await fetch(`${BACKEND_API_URL}/posts/${id}`);
    if (!response.ok) throw new Error('Failed to fetch post');
    return response.json();
  },

  delete: async (id: string) => {
    const response = await fetch(`${BACKEND_API_URL}/posts/${id}`, {
      method: 'DELETE',
    });
    if (!response.ok) throw new Error('Failed to delete post');
    return response.json();
  },
};