'use client';

import { useState, useEffect } from 'react';
import { teamApi } from '@/utils/enhanced-api';

export default function TeamPage() {
  const [members, setMembers] = useState<any[]>([]);
  const [projects, setProjects] = useState<any[]>([]);
  const [notifications, setNotifications] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('members');
  const [showInviteModal, setShowInviteModal] = useState(false);
  const [showProjectModal, setShowProjectModal] = useState(false);
  const [inviteData, setInviteData] = useState({
    email: '',
    role: 'editor',
    permissions: [] as string[]
  });
  const [projectData, setProjectData] = useState({
    name: '',
    description: '',
    members: [] as string[]
  });

  const roles = [
    { id: 'admin', name: '👑 Admin', description: 'Full access to all features' },
    { id: 'manager', name: '📊 Manager', description: 'Manage projects and team members' },
    { id: 'editor', name: '✏️ Editor', description: 'Create and edit content' },
    { id: 'viewer', name: '👀 Viewer', description: 'View-only access' }
  ];

  const permissions = [
    { id: 'create_content', name: 'Create Content' },
    { id: 'edit_content', name: 'Edit Content' },
    { id: 'delete_content', name: 'Delete Content' },
    { id: 'publish_content', name: 'Publish Content' },
    { id: 'manage_videos', name: 'Manage Videos' },
    { id: 'view_analytics', name: 'View Analytics' },
    { id: 'manage_automation', name: 'Manage Automation' },
    { id: 'invite_members', name: 'Invite Members' }
  ];

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      setLoading(true);
      const [membersData, projectsData, notificationsData] = await Promise.all([
        teamApi.getMembers(),
        teamApi.getProjects(),
        teamApi.getNotifications()
      ]);
      
      setMembers(Array.isArray(membersData) ? membersData : []);
      setProjects(Array.isArray(projectsData) ? projectsData : []);
      setNotifications(Array.isArray(notificationsData) ? notificationsData : []);
    } catch (error) {
      console.error('Failed to load team data:', error);
      setMembers([]);
      setProjects([]);
      setNotifications([]);
    } finally {
      setLoading(false);
    }
  };

  const inviteMember = async () => {
    if (!inviteData.email.trim()) {
      alert('Please enter an email address');
      return;
    }

    try {
      await teamApi.inviteMember(inviteData);
      setShowInviteModal(false);
      setInviteData({ email: '', role: 'editor', permissions: [] });
      loadData();
      alert('Invitation sent successfully!');
    } catch (error) {
      console.error('Failed to invite member:', error);
      alert('Failed to send invitation');
    }
  };

  const createProject = async () => {
    if (!projectData.name.trim()) {
      alert('Please enter a project name');
      return;
    }

    try {
      await teamApi.createProject(projectData);
      setShowProjectModal(false);
      setProjectData({ name: '', description: '', members: [] });
      loadData();
      alert('Project created successfully!');
    } catch (error) {
      console.error('Failed to create project:', error);
      alert('Failed to create project');
    }
  };

  const updateMemberRole = async (memberId: string, newRole: string) => {
    try {
      await teamApi.updateMemberRole(memberId, newRole);
      loadData();
    } catch (error) {
      console.error('Failed to update member role:', error);
      alert('Failed to update member role');
    }
  };

  const removeMember = async (memberId: string) => {
    if (!confirm('Are you sure you want to remove this member?')) return;

    try {
      await teamApi.removeMember(memberId);
      loadData();
    } catch (error) {
      console.error('Failed to remove member:', error);
      alert('Failed to remove member');
    }
  };

  const markNotificationRead = async (notificationId: string) => {
    try {
      await teamApi.markNotificationRead(notificationId);
      loadData();
    } catch (error) {
      console.error('Failed to mark notification as read:', error);
    }
  };

  const getRoleColor = (role: string) => {
    switch (role) {
      case 'admin': return 'text-red-600 bg-red-100';
      case 'manager': return 'text-blue-600 bg-blue-100';
      case 'editor': return 'text-green-600 bg-green-100';
      case 'viewer': return 'text-gray-600 bg-gray-100';
      default: return 'text-gray-600 bg-gray-100';
    }
  };

  const getProjectStatusColor = (status: string) => {
    switch (status) {
      case 'active': return 'text-green-600 bg-green-100';
      case 'paused': return 'text-yellow-600 bg-yellow-100';
      case 'completed': return 'text-blue-600 bg-blue-100';
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
              <h1 className="text-3xl font-bold mb-2">👥 Team Collaboration</h1>
              <p className="text-gray-300">Manage your team, projects, and collaborate effectively</p>
            </div>
            <div className="flex space-x-3">
              <button
                onClick={() => setShowInviteModal(true)}
                className="aws-btn-primary"
              >
                ➕ Invite Member
              </button>
              <button
                onClick={() => setShowProjectModal(true)}
                className="aws-btn-secondary"
              >
                📁 New Project
              </button>
            </div>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 py-8">
        {/* Tabs */}
        <div className="flex space-x-1 mb-8">
          {[
            { id: 'members', name: '👥 Team Members', count: members.length },
            { id: 'projects', name: '📁 Projects', count: projects.length },
            { id: 'notifications', name: '🔔 Notifications', count: notifications.filter(n => !n.read).length }
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
              {tab.count > 0 && (
                <span className={`ml-2 px-2 py-1 rounded-full text-xs ${
                  activeTab === tab.id ? 'bg-orange-600' : 'bg-gray-200 text-gray-600'
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
            <p className="mt-2 text-gray-600">Loading team data...</p>
          </div>
                ) : (
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                    {projects.map((project) => (
                      <div key={project.id} className="aws-card p-6">
                        <div className="flex items-start justify-between mb-4">
                          <div>
                            <h3 className="text-lg font-semibold text-gray-900 mb-1">
                              {project.name}
                            </h3>
                            <p className="text-gray-600 text-sm">{project.description}</p>
                          </div>
                          <span className={`px-2 py-1 rounded-full text-xs font-medium ${getProjectStatusColor(project.status)}`}>
                            {project.status}
                          </span>
                        </div>
                        
                        <div className="space-y-3">
                          <div className="flex items-center justify-between text-sm">
                            <span className="text-gray-600">Progress</span>
                            <span className="font-medium">{project.progress || 0}%</span>
                          </div>
                          <div className="w-full bg-gray-200 rounded-full h-2">
                            <div
                              className="bg-orange-500 h-2 rounded-full"
                              style={{ width: `${project.progress || 0}%` }}
                            ></div>
                          </div>
                          
                          <div className="flex items-center justify-between text-sm">
                            <span className="text-gray-600">Team Members</span>
                            <div className="flex -space-x-2">
                              {project.members?.slice(0, 3).map((memberId: string, index: number) => {
                                const member = members.find(m => m.id === memberId);
                                return (
                                  <div
                                    key={index}
                                    className="w-6 h-6 bg-gray-300 rounded-full border-2 border-white flex items-center justify-center"
                                    title={member?.name || member?.email}
                                  >
                                    <span className="text-xs text-gray-600">
                                      {member?.name?.charAt(0) || member?.email?.charAt(0) || '?'}
                                    </span>
                                  </div>
                                );
                              })}
                              {project.members?.length > 3 && (
                                <div className="w-6 h-6 bg-gray-400 rounded-full border-2 border-white flex items-center justify-center">
                                  <span className="text-xs text-white">+{project.members.length - 3}</span>
                                </div>
                              )}
                            </div>
                          </div>
                          
                          <div className="flex items-center justify-between text-sm text-gray-500">
                            <span>Created: {new Date(project.createdAt).toLocaleDateString()}</span>
                            <span>Due: {project.dueDate ? new Date(project.dueDate).toLocaleDateString() : 'No deadline'}</span>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* Notifications Tab */}
            {activeTab === 'notifications' && (
              <div className="aws-card">
                <div className="p-6 border-b border-gray-200">
                  <h2 className="text-xl font-semibold">Team Notifications</h2>
                </div>
                
                {notifications.length === 0 ? (
                  <div className="text-center py-12">
                    <svg className="w-16 h-16 text-gray-400 mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 17h5l-5 5v-5zM11 17H6l5 5v-5zM7 8a3 3 0 016 0v3.5a1.5 1.5 0 01-1.5 1.5h-3A1.5 1.5 0 017 11.5V8z" />
                    </svg>
                    <p className="text-gray-500 text-lg mb-2">No notifications</p>
                    <p className="text-gray-400">You're all caught up!</p>
                  </div>
                ) : (
                  <div className="divide-y divide-gray-200">
                    {notifications.map((notification) => (
                      <div
                        key={notification.id}
                        className={`p-6 ${!notification.read ? 'bg-blue-50' : ''}`}
                      >
                        <div className="flex items-start justify-between">
                          <div className="flex-1">
                            <div className="flex items-center space-x-2 mb-2">
                              <span className="text-lg">
                                {notification.type === 'invite' && '👋'}
                                {notification.type === 'project' && '📁'}
                                {notification.type === 'task' && '✅'}
                                {notification.type === 'mention' && '💬'}
                                {notification.type === 'system' && '⚙️'}
                              </span>
                              <h3 className="font-semibold text-gray-900">
                                {notification.title}
                              </h3>
                              {!notification.read && (
                                <span className="w-2 h-2 bg-blue-500 rounded-full"></span>
                              )}
                            </div>
                            
                            <p className="text-gray-600 mb-2">{notification.message}</p>
                            
                            <div className="text-sm text-gray-500">
                              {new Date(notification.createdAt).toLocaleString()}
                            </div>
                          </div>
                          
                          <div className="flex items-center space-x-2 ml-4">
                            {!notification.read && (
                              <button
                                onClick={() => markNotificationRead(notification.id)}
                                className="text-blue-600 hover:text-blue-800 text-sm"
                              >
                                Mark as read
                              </button>
                            )}
                            
                            {notification.actionUrl && (
                              <a
                                href={notification.actionUrl}
                                className="aws-btn-primary text-sm px-3 py-1"
                              >
                                View
                              </a>
                            )}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </>
        )}
      </div>

      {/* Invite Member Modal */}
      {showInviteModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg max-w-md w-full mx-4">
            <div className="p-6 border-b border-gray-200">
              <h2 className="text-xl font-semibold">Invite Team Member</h2>
            </div>
            
            <div className="p-6 space-y-4">
              <div>
                <label className="block text-sm font-medium mb-2">Email Address</label>
                <input
                  type="email"
                  value={inviteData.email}
                  onChange={(e) => setInviteData({ ...inviteData, email: e.target.value })}
                  placeholder="Enter email address..."
                  className="aws-input w-full"
                />
              </div>
              
              <div>
                <label className="block text-sm font-medium mb-2">Role</label>
                <select
                  value={inviteData.role}
                  onChange={(e) => setInviteData({ ...inviteData, role: e.target.value })}
                  className="aws-input w-full"
                >
                  {roles.map((role) => (
                    <option key={role.id} value={role.id}>
                      {role.name} - {role.description}
                    </option>
                  ))}
                </select>
              </div>
              
              <div>
                <label className="block text-sm font-medium mb-2">Permissions</label>
                <div className="space-y-2 max-h-40 overflow-y-auto">
                  {permissions.map((permission) => (
                    <label key={permission.id} className="flex items-center">
                      <input
                        type="checkbox"
                        checked={inviteData.permissions.includes(permission.id)}
                        onChange={(e) => {
                          if (e.target.checked) {
                            setInviteData({
                              ...inviteData,
                              permissions: [...inviteData.permissions, permission.id]
                            });
                          } else {
                            setInviteData({
                              ...inviteData,
                              permissions: inviteData.permissions.filter(p => p !== permission.id)
                            });
                          }
                        }}
                        className="text-orange-500 focus:ring-orange-500 mr-2"
                      />
                      <span className="text-sm">{permission.name}</span>
                    </label>
                  ))}
                </div>
              </div>
            </div>
            
            <div className="p-6 border-t border-gray-200 flex justify-end space-x-3">
              <button
                onClick={() => setShowInviteModal(false)}
                className="aws-btn-secondary"
              >
                Cancel
              </button>
              <button
                onClick={inviteMember}
                className="aws-btn-primary"
              >
                Send Invitation
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Create Project Modal */}
      {showProjectModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg max-w-md w-full mx-4">
            <div className="p-6 border-b border-gray-200">
              <h2 className="text-xl font-semibold">Create New Project</h2>
            </div>
            
            <div className="p-6 space-y-4">
              <div>
                <label className="block text-sm font-medium mb-2">Project Name</label>
                <input
                  type="text"
                  value={projectData.name}
                  onChange={(e) => setProjectData({ ...projectData, name: e.target.value })}
                  placeholder="Enter project name..."
                  className="aws-input w-full"
                />
              </div>
              
              <div>
                <label className="block text-sm font-medium mb-2">Description</label>
                <textarea
                  value={projectData.description}
                  onChange={(e) => setProjectData({ ...projectData, description: e.target.value })}
                  placeholder="Describe the project..."
                  rows={3}
                  className="aws-input w-full resize-none"
                />
              </div>
              
              <div>
                <label className="block text-sm font-medium mb-2">Team Members</label>
                <div className="space-y-2 max-h-40 overflow-y-auto">
                  {members.map((member) => (
                    <label key={member.id} className="flex items-center">
                      <input
                        type="checkbox"
                        checked={projectData.members.includes(member.id)}
                        onChange={(e) => {
                          if (e.target.checked) {
                            setProjectData({
                              ...projectData,
                              members: [...projectData.members, member.id]
                            });
                          } else {
                            setProjectData({
                              ...projectData,
                              members: projectData.members.filter(m => m !== member.id)
                            });
                          }
                        }}
                        className="text-orange-500 focus:ring-orange-500 mr-2"
                      />
                      <span className="text-sm">{member.name || member.email}</span>
                    </label>
                  ))}
                </div>
              </div>
            </div>
            
            <div className="p-6 border-t border-gray-200 flex justify-end space-x-3">
              <button
                onClick={() => setShowProjectModal(false)}
                className="aws-btn-secondary"
              >
                Cancel
              </button>
              <button
                onClick={createProject}
                className="aws-btn-primary"
              >
                Create Project
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
          <>
            {/* Team Members Tab */}
            {activeTab === 'members' && (
              <div className="aws-card">
                <div className="p-6 border-b border-gray-200">
                  <h2 className="text-xl font-semibold">Team Members</h2>
                </div>
                
                {members.length === 0 ? (
                  <div className="text-center py-12">
                    <svg className="w-16 h-16 text-gray-400 mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197m13.5-9a2.5 2.5 0 11-5 0 2.5 2.5 0 015 0z" />
                    </svg>
                    <p className="text-gray-500 text-lg mb-2">No team members yet</p>
                    <p className="text-gray-400 mb-4">Invite your first team member to get started</p>
                    <button
                      onClick={() => setShowInviteModal(true)}
                      className="aws-btn-primary"
                    >
                      Invite Team Member
                    </button>
                  </div>
                ) : (
                  <div className="divide-y divide-gray-200">
                    {members.map((member) => (
                      <div key={member.id} className="p-6">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center space-x-4">
                            <div className="w-12 h-12 bg-gray-200 rounded-full flex items-center justify-center">
                              {member.avatar ? (
                                <img
                                  src={member.avatar}
                                  alt={member.name}
                                  className="w-12 h-12 rounded-full object-cover"
                                />
                              ) : (
                                <span className="text-gray-600 font-medium text-lg">
                                  {member.name?.charAt(0) || member.email?.charAt(0)}
                                </span>
                              )}
                            </div>
                            
                            <div>
                              <h3 className="text-lg font-semibold text-gray-900">
                                {member.name || member.email}
                              </h3>
                              <p className="text-gray-600">{member.email}</p>
                              <div className="flex items-center space-x-4 mt-1 text-sm text-gray-500">
                                <span>Joined: {new Date(member.joinedAt).toLocaleDateString()}</span>
                                <span>Last active: {new Date(member.lastActive).toLocaleDateString()}</span>
                              </div>
                            </div>
                          </div>
                          
                          <div className="flex items-center space-x-3">
                            <span className={`px-3 py-1 rounded-full text-sm font-medium ${getRoleColor(member.role)}`}>
                              {roles.find(r => r.id === member.role)?.name || member.role}
                            </span>
                            
                            <select
                              value={member.role}
                              onChange={(e) => updateMemberRole(member.id, e.target.value)}
                              className="text-sm border border-gray-300 rounded px-2 py-1"
                            >
                              {roles.map((role) => (
                                <option key={role.id} value={role.id}>
                                  {role.name}
                                </option>
                              ))}
                            </select>
                            
                            <button
                              onClick={() => removeMember(member.id)}
                              className="p-2 text-red-600 hover:bg-red-50 rounded-lg transition-colors"
                            >
                              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                              </svg>
                            </button>
                          </div>
                        </div>
                        
                        {member.permissions && member.permissions.length > 0 && (
                          <div className="mt-3">
                            <div className="text-sm text-gray-600 mb-2">Permissions:</div>
                            <div className="flex flex-wrap gap-2">
                              {member.permissions.map((permission: string) => (
                                <span
                                  key={permission}
                                  className="px-2 py-1 bg-blue-100 text-blue-800 rounded text-xs"
                                >
                                  {permissions.find(p => p.id === permission)?.name || permission}
                                </span>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* Projects Tab */}
            {activeTab === 'projects' && (
              <div className="space-y-6">
                {projects.length === 0 ? (
                  <div className="aws-card text-center py-12">
                    <svg className="w-16 h-16 text-gray-400 mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
                    </svg>
                    <p className="text-gray-500 text-lg mb-2">No projects yet</p>
                    <p className="text-gray-400 mb-4">Create your first project to organize your work</p>
                    <button
                      onClick={() => setShowProjectModal(true)}
                      className="aws-btn-primary"
                    >
                      Create Project
                    </button>
                  </div>
                ) : (