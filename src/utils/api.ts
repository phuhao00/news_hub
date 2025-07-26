const API_BASE_URL = 'http://localhost:8080/api';

// 创作者相关API
export const creatorApi = {
  create: async (data: { username: string; platform: string }) => {
    const response = await fetch(`${API_BASE_URL}/creators`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    if (!response.ok) throw new Error('Failed to create creator');
    return response.json();
  },

  list: async () => {
    const response = await fetch(`${API_BASE_URL}/creators`);
    if (!response.ok) throw new Error('Failed to fetch creators');
    return response.json();
  },

  delete: async (id: string) => {
    const response = await fetch(`${API_BASE_URL}/creators/${id}`, {
      method: 'DELETE',
    });
    if (!response.ok) throw new Error('Failed to delete creator');
    return response.json();
  },
};

// 视频生成相关API
export const videoApi = {
  generate: async (data: { postIds: string[]; style: string; duration: number }) => {
    const response = await fetch(`${API_BASE_URL}/videos/generate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    if (!response.ok) throw new Error('Failed to generate video');
    return response.json();
  },

  list: async () => {
    const response = await fetch(`${API_BASE_URL}/videos`);
    if (!response.ok) throw new Error('Failed to fetch videos');
    return response.json();
  },
};

// 发布任务相关API
export const publishApi = {
  create: async (data: { videoId: string; platforms: string[]; description: string }) => {
    const response = await fetch(`${API_BASE_URL}/publish`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    if (!response.ok) throw new Error('Failed to create publish task');
    return response.json();
  },

  list: async () => {
    const response = await fetch(`${API_BASE_URL}/publish/tasks`);
    if (!response.ok) throw new Error('Failed to fetch publish tasks');
    return response.json();
  },
};

// 爬虫相关API
export const crawlerApi = {
  trigger: async (data: { platform: string; creator_url: string; limit?: number }) => {
    const response = await fetch(`${API_BASE_URL}/crawler/trigger`, {
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
    const response = await fetch(`${API_BASE_URL}/crawler/status`);
    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`Failed to get crawler status: ${errorText}`);
    }
    return response.json();
  },

  platforms: async () => {
    const response = await fetch(`${API_BASE_URL}/crawler/platforms`);
    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`Failed to get crawler platforms: ${errorText}`);
    }
    return response.json();
  },

  // 任务管理相关API
  tasks: {
    create: async (data: { platform: string; creator_url: string; limit?: number }) => {
      const response = await fetch(`${API_BASE_URL}/crawler/tasks`, {
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
      const response = await fetch(`${API_BASE_URL}/crawler/tasks`);
      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`Failed to get crawler tasks: ${errorText}`);
      }
      return response.json();
    },

    get: async (id: string) => {
      const response = await fetch(`${API_BASE_URL}/crawler/tasks/${id}`);
      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`Failed to get crawler task: ${errorText}`);
      }
      return response.json();
    },

    updateStatus: async (id: string, data: { status: string; error?: string }) => {
      const response = await fetch(`${API_BASE_URL}/crawler/tasks/${id}/status`, {
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
      
      const response = await fetch(`${API_BASE_URL}/crawler/contents?${params}`);
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
    
    const response = await fetch(`${API_BASE_URL}/posts?${searchParams}`);
    if (!response.ok) throw new Error('Failed to fetch posts');
    return response.json();
  },

  get: async (id: string) => {
    const response = await fetch(`${API_BASE_URL}/posts/${id}`);
    if (!response.ok) throw new Error('Failed to fetch post');
    return response.json();
  },

  delete: async (id: string) => {
    const response = await fetch(`${API_BASE_URL}/posts/${id}`, {
      method: 'DELETE',
    });
    if (!response.ok) throw new Error('Failed to delete post');
    return response.json();
  },
};