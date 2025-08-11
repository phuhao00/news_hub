'use client';

import { useState, useEffect } from 'react';
import { automationApi } from '@/utils/api';

export default function AutomationPage() {
  const [workflows, setWorkflows] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [newWorkflow, setNewWorkflow] = useState({
    name: '',
    description: '',
    triggers: [] as string[],
    actions: [] as string[],
    schedule: '',
    enabled: true
  });

  const availableTriggers = [
    { id: 'new_content', name: '📥 New Content Crawled', description: 'Trigger when new content is found' },
    { id: 'high_engagement', name: '🔥 High Engagement Detected', description: 'Trigger when content gets high engagement' },
    { id: 'schedule', name: '⏰ Time-based Schedule', description: 'Trigger at specific times' },
    { id: 'keyword_match', name: '🔍 Keyword Match', description: 'Trigger when specific keywords are found' },
    { id: 'competitor_post', name: '👥 Competitor Activity', description: 'Trigger when competitors post' }
  ];

  const availableActions = [
    { id: 'generate_video', name: '🎬 Generate Video', description: 'Automatically create video from content' },
    { id: 'publish_content', name: '📤 Publish Content', description: 'Auto-publish to selected platforms' },
    { id: 'send_notification', name: '🔔 Send Notification', description: 'Send alerts to team members' },
    { id: 'analyze_sentiment', name: '😊 Analyze Sentiment', description: 'Perform sentiment analysis' },
    { id: 'tag_content', name: '🏷️ Auto-tag Content', description: 'Automatically categorize content' },
    { id: 'backup_content', name: '💾 Backup Content', description: 'Save content to external storage' }
  ];

  useEffect(() => {
    loadWorkflows();
  }, []);

  const loadWorkflows = async () => {
    try {
      setLoading(true);
      const data = await automationApi.list();
      setWorkflows(Array.isArray(data) ? data : []);
    } catch (error) {
      console.error('Failed to load workflows:', error);
      setWorkflows([]);
    } finally {
      setLoading(false);
    }
  };

  const createWorkflow = async () => {
    if (!newWorkflow.name.trim()) {
      alert('Please enter a workflow name');
      return;
    }

    if (newWorkflow.triggers.length === 0) {
      alert('Please select at least one trigger');
      return;
    }

    if (newWorkflow.actions.length === 0) {
      alert('Please select at least one action');
      return;
    }

    try {
      await automationApi.create(newWorkflow);
      setShowCreateModal(false);
      setNewWorkflow({
        name: '',
        description: '',
        triggers: [],
        actions: [],
        schedule: '',
        enabled: true
      });
      loadWorkflows();
    } catch (error) {
      console.error('Failed to create workflow:', error);
      alert('Failed to create workflow');
    }
  };

  const toggleWorkflow = async (id: string, enabled: boolean) => {
    try {
      await automationApi.update(id, { enabled });
      loadWorkflows();
    } catch (error) {
      console.error('Failed to update workflow:', error);
    }
  };

  const deleteWorkflow = async (id: string) => {
    if (!confirm('Are you sure you want to delete this workflow?')) return;

    try {
      await automationApi.delete(id);
      loadWorkflows();
    } catch (error) {
      console.error('Failed to delete workflow:', error);
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'active': return 'text-green-600 bg-green-100';
      case 'paused': return 'text-yellow-600 bg-yellow-100';
      case 'error': return 'text-red-600 bg-red-100';
      default: return 'text-gray-600 bg-gray-100';
    }
  };

  return (
    <div className="min-h-screen" style={{ backgroundColor: 'var(--aws-gray-50)' }}>
      {/* Header */}
      <div style={{ backgroundColor: 'var(--aws-blue)' }} className="text-white py-8">
        <div className="max-w-7xl mx-auto px-4">
          <div className="flex justify-between items-center">
            <div>
              <h1 className="text-3xl font-bold mb-2">🤖 Automation Hub</h1>
              <p className="text-gray-300">Create intelligent workflows to automate your content operations</p>
            </div>
            <button
              onClick={() => setShowCreateModal(true)}
              className="aws-btn-primary"
            >
              ➕ Create Workflow
            </button>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 py-8">
        {loading ? (
          <div className="text-center py-12">
            <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-orange-500"></div>
            <p className="mt-2 text-gray-600">Loading workflows...</p>
          </div>
        ) : (
          <div className="space-y-6">
            {/* Quick Stats */}
            <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
              <div className="aws-card p-6">
                <div className="text-2xl font-bold text-gray-900">{workflows.length}</div>
                <div className="text-sm text-gray-600">Total Workflows</div>
              </div>
              <div className="aws-card p-6">
                <div className="text-2xl font-bold text-green-600">
                  {workflows.filter(w => w.status === 'active').length}
                </div>
                <div className="text-sm text-gray-600">Active Workflows</div>
              </div>
              <div className="aws-card p-6">
                <div className="text-2xl font-bold text-blue-600">
                  {workflows.reduce((sum, w) => sum + (w.executionCount || 0), 0)}
                </div>
                <div className="text-sm text-gray-600">Total Executions</div>
              </div>
              <div className="aws-card p-6">
                <div className="text-2xl font-bold text-purple-600">
                  {workflows.reduce((sum, w) => sum + (w.timeSaved || 0), 0)}h
                </div>
                <div className="text-sm text-gray-600">Time Saved</div>
              </div>
            </div>

            {/* Workflows List */}
            <div className="aws-card">
              <div className="p-6 border-b border-gray-200">
                <h2 className="text-xl font-semibold">Automation Workflows</h2>
              </div>
              
              {workflows.length === 0 ? (
                <div className="text-center py-12">
                  <svg className="w-16 h-16 text-gray-400 mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                  </svg>
                  <p className="text-gray-500 text-lg mb-2">No workflows created yet</p>
                  <p className="text-gray-400 mb-4">Create your first automation workflow to get started</p>
                  <button
                    onClick={() => setShowCreateModal(true)}
                    className="aws-btn-primary"
                  >
                    Create Your First Workflow
                  </button>
                </div>
              ) : (
                <div className="divide-y divide-gray-200">
                  {workflows.map((workflow) => (
                    <div key={workflow.id} className="p-6">
                      <div className="flex items-start justify-between">
                        <div className="flex-1">
                          <div className="flex items-center space-x-3 mb-2">
                            <h3 className="text-lg font-semibold text-gray-900">{workflow.name}</h3>
                            <span className={`px-2 py-1 rounded-full text-xs font-medium ${getStatusColor(workflow.status)}`}>
                              {workflow.status}
                            </span>
                          </div>
                          
                          <p className="text-gray-600 mb-3">{workflow.description}</p>
                          
                          <div className="flex flex-wrap gap-4 text-sm text-gray-500">
                            <div>
                              <span className="font-medium">Triggers:</span> {workflow.triggers?.length || 0}
                            </div>
                            <div>
                              <span className="font-medium">Actions:</span> {workflow.actions?.length || 0}
                            </div>
                            <div>
                              <span className="font-medium">Executions:</span> {workflow.executionCount || 0}
                            </div>
                            <div>
                              <span className="font-medium">Last run:</span> {
                                workflow.lastRun ? new Date(workflow.lastRun).toLocaleString() : 'Never'
                              }
                            </div>
                          </div>
                        </div>
                        
                        <div className="flex items-center space-x-2 ml-4">
                          <label className="flex items-center">
                            <input
                              type="checkbox"
                              checked={workflow.enabled}
                              onChange={(e) => toggleWorkflow(workflow.id, e.target.checked)}
                              className="text-orange-500 focus:ring-orange-500"
                            />
                            <span className="ml-2 text-sm text-gray-600">Enabled</span>
                          </label>
                          
                          <button
                            onClick={() => deleteWorkflow(workflow.id)}
                            className="p-2 text-red-600 hover:bg-red-50 rounded-lg transition-colors"
                          >
                            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                            </svg>
                          </button>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Create Workflow Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg max-w-2xl w-full mx-4 max-h-[90vh] overflow-y-auto">
            <div className="p-6 border-b border-gray-200">
              <h2 className="text-xl font-semibold">Create New Workflow</h2>
            </div>
            
            <div className="p-6 space-y-6">
              {/* Basic Info */}
              <div>
                <label className="block text-sm font-medium mb-2">Workflow Name</label>
                <input
                  type="text"
                  value={newWorkflow.name}
                  onChange={(e) => setNewWorkflow({ ...newWorkflow, name: e.target.value })}
                  placeholder="Enter workflow name..."
                  className="aws-input w-full"
                />
              </div>
              
              <div>
                <label className="block text-sm font-medium mb-2">Description</label>
                <textarea
                  value={newWorkflow.description}
                  onChange={(e) => setNewWorkflow({ ...newWorkflow, description: e.target.value })}
                  placeholder="Describe what this workflow does..."
                  rows={3}
                  className="aws-input w-full resize-none"
                />
              </div>

              {/* Triggers */}
              <div>
                <label className="block text-sm font-medium mb-3">Triggers (When to run)</label>
                <div className="space-y-2">
                  {availableTriggers.map((trigger) => (
                    <label key={trigger.id} className="flex items-start p-3 border rounded-lg cursor-pointer hover:bg-gray-50">
                      <input
                        type="checkbox"
                        checked={newWorkflow.triggers.includes(trigger.id)}
                        onChange={(e) => {
                          if (e.target.checked) {
                            setNewWorkflow({
                              ...newWorkflow,
                              triggers: [...newWorkflow.triggers, trigger.id]
                            });
                          } else {
                            setNewWorkflow({
                              ...newWorkflow,
                              triggers: newWorkflow.triggers.filter(t => t !== trigger.id)
                            });
                          }
                        }}
                        className="text-orange-500 focus:ring-orange-500 mt-1"
                      />
                      <div className="ml-3">
                        <div className="font-medium text-sm">{trigger.name}</div>
                        <div className="text-xs text-gray-600">{trigger.description}</div>
                      </div>
                    </label>
                  ))}
                </div>
              </div>

              {/* Actions */}
              <div>
                <label className="block text-sm font-medium mb-3">Actions (What to do)</label>
                <div className="space-y-2">
                  {availableActions.map((action) => (
                    <label key={action.id} className="flex items-start p-3 border rounded-lg cursor-pointer hover:bg-gray-50">
                      <input
                        type="checkbox"
                        checked={newWorkflow.actions.includes(action.id)}
                        onChange={(e) => {
                          if (e.target.checked) {
                            setNewWorkflow({
                              ...newWorkflow,
                              actions: [...newWorkflow.actions, action.id]
                            });
                          } else {
                            setNewWorkflow({
                              ...newWorkflow,
                              actions: newWorkflow.actions.filter(a => a !== action.id)
                            });
                          }
                        }}
                        className="text-orange-500 focus:ring-orange-500 mt-1"
                      />
                      <div className="ml-3">
                        <div className="font-medium text-sm">{action.name}</div>
                        <div className="text-xs text-gray-600">{action.description}</div>
                      </div>
                    </label>
                  ))}
                </div>
              </div>

              {/* Schedule */}
              <div>
                <label className="block text-sm font-medium mb-2">Schedule (Optional)</label>
                <input
                  type="text"
                  value={newWorkflow.schedule}
                  onChange={(e) => setNewWorkflow({ ...newWorkflow, schedule: e.target.value })}
                  placeholder="e.g., 0 9 * * * (daily at 9 AM)"
                  className="aws-input w-full"
                />
                <div className="text-xs text-gray-500 mt-1">
                  Use cron format for scheduled triggers
                </div>
              </div>
            </div>
            
            <div className="p-6 border-t border-gray-200 flex justify-end space-x-3">
              <button
                onClick={() => setShowCreateModal(false)}
                className="aws-btn-secondary"
              >
                Cancel
              </button>
              <button
                onClick={createWorkflow}
                className="aws-btn-primary"
              >
                Create Workflow
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}