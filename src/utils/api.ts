const API_BASE_URL = 'http://localhost:8082/api';

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
  trigger: async (data: { creatorIds?: string[]; platforms?: string[] }) => {
    const response = await fetch(`${API_BASE_URL}/crawler/trigger`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    if (!response.ok) throw new Error('Failed to trigger crawler');
    return response.json();
  },

  status: async () => {
    const response = await fetch(`${API_BASE_URL}/crawler/status`);
    if (!response.ok) throw new Error('Failed to get crawler status');
    return response.json();
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