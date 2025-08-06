'use client';

import { useState, useEffect, useRef } from 'react';
import { aiApi } from '@/utils/api';

export default function AIAssistantPage() {
  const [messages, setMessages] = useState<any[]>([
    {
      id: 1,
      type: 'assistant',
      content: 'Hello! I\'m your AI assistant for NewsHub. I can help you with content optimization, performance predictions, sentiment analysis, and much more. What would you like to work on today?',
      timestamp: new Date(),
    }
  ]);
  const [inputMessage, setInputMessage] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [activeFeature, setActiveFeature] = useState('chat');
  const [contentToOptimize, setContentToOptimize] = useState('');
  const [selectedPlatform, setSelectedPlatform] = useState('weibo');
  const [optimizationGoal, setOptimizationGoal] = useState('engagement');
  const [analysisResults, setAnalysisResults] = useState<any>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const aiFeatures = [
    { id: 'chat', name: '💬 AI Chat', description: 'General AI assistance' },
    { id: 'optimize', name: '🚀 Content Optimizer', description: 'Optimize content for platforms' },
    { id: 'sentiment', name: '😊 Sentiment Analysis', description: 'Analyze content sentiment' },
    { id: 'tags', name: '🏷️ Smart Tags', description: 'Generate relevant tags' },
    { id: 'predict', name: '📈 Performance Predictor', description: 'Predict content performance' },
    { id: 'generate', name: '✨ Content Generator', description: 'Generate new content ideas' }
  ];

  const platforms = [
    { id: 'weibo', name: '🐦 Weibo', color: 'bg-red-100 text-red-800' },
    { id: 'bilibili', name: '📺 Bilibili', color: 'bg-pink-100 text-pink-800' },
    { id: 'xiaohongshu', name: '📖 Xiaohongshu', color: 'bg-red-100 text-red-800' },
    { id: 'douyin', name: '🎵 Douyin', color: 'bg-black text-white' },
    { id: 'youtube', name: '📹 YouTube', color: 'bg-red-100 text-red-800' },
    { id: 'tiktok', name: '🎬 TikTok', color: 'bg-black text-white' }
  ];

  const optimizationGoals = [
    { id: 'engagement', name: '💝 Maximize Engagement' },
    { id: 'reach', name: '📢 Increase Reach' },
    { id: 'conversion', name: '🎯 Drive Conversions' },
    { id: 'brand', name: '🏢 Build Brand Awareness' }
  ];

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  const sendMessage = async () => {
    if (!inputMessage.trim() || isLoading) return;

    const userMessage = {
      id: Date.now(),
      type: 'user',
      content: inputMessage,
      timestamp: new Date(),
    };

    setMessages(prev => [...prev, userMessage]);
    setInputMessage('');
    setIsLoading(true);

    try {
      const response = await aiApi.generateContent({
        prompt: inputMessage,
        type: 'chat',
        context: { previousMessages: messages.slice(-5) }
      });

      const assistantMessage = {
        id: Date.now() + 1,
        type: 'assistant',
        content: response.content || 'I apologize, but I couldn\'t process your request at the moment. Please try again.',
        timestamp: new Date(),
      };

      setMessages(prev => [...prev, assistantMessage]);
    } catch (error) {
      console.error('Failed to send message:', error);
      const errorMessage = {
        id: Date.now() + 1,
        type: 'assistant',
        content: 'I\'m sorry, I encountered an error. Please try again later.',
        timestamp: new Date(),
      };
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  const optimizeContent = async () => {
    if (!contentToOptimize.trim()) {
      alert('Please enter content to optimize');
      return;
    }

    setIsLoading(true);
    try {
      const result = await aiApi.optimizeContent({
        content: contentToOptimize,
        platform: selectedPlatform,
        goal: optimizationGoal
      });

      setAnalysisResults({
        type: 'optimization',
        original: contentToOptimize,
        optimized: result.optimizedContent,
        suggestions: result.suggestions,
        score: result.score,
        platform: selectedPlatform,
        goal: optimizationGoal
      });
    } catch (error) {
      console.error('Failed to optimize content:', error);
      alert('Failed to optimize content. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  const analyzeSentiment = async () => {
    if (!contentToOptimize.trim()) {
      alert('Please enter content to analyze');
      return;
    }

    setIsLoading(true);
    try {
      const result = await aiApi.analyzeSentiment(contentToOptimize);
      
      setAnalysisResults({
        type: 'sentiment',
        content: contentToOptimize,
        sentiment: result.sentiment,
        confidence: result.confidence,
        emotions: result.emotions,
        keywords: result.keywords
      });
    } catch (error) {
      console.error('Failed to analyze sentiment:', error);
      alert('Failed to analyze sentiment. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  const generateTags = async () => {
    if (!contentToOptimize.trim()) {
      alert('Please enter content to generate tags');
      return;
    }

    setIsLoading(true);
    try {
      const result = await aiApi.generateTags(contentToOptimize);
      
      setAnalysisResults({
        type: 'tags',
        content: contentToOptimize,
        tags: result.tags,
        categories: result.categories,
        trending: result.trendingTags
      });
    } catch (error) {
      console.error('Failed to generate tags:', error);
      alert('Failed to generate tags. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  const predictPerformance = async () => {
    if (!contentToOptimize.trim()) {
      alert('Please enter content to predict performance');
      return;
    }

    setIsLoading(true);
    try {
      const result = await aiApi.predictPerformance({
        content: contentToOptimize,
        platform: selectedPlatform,
        timing: 'optimal'
      });
      
      setAnalysisResults({
        type: 'prediction',
        content: contentToOptimize,
        platform: selectedPlatform,
        predictedViews: result.predictedViews,
        predictedEngagement: result.predictedEngagement,
        confidence: result.confidence,
        factors: result.factors,
        recommendations: result.recommendations
      });
    } catch (error) {
      console.error('Failed to predict performance:', error);
      alert('Failed to predict performance. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  const generateContent = async () => {
    const prompt = `Generate creative content ideas for ${selectedPlatform} platform focusing on ${optimizationGoal}`;
    
    setIsLoading(true);
    try {
      const result = await aiApi.generateContent({
        prompt,
        type: 'content_ideas',
        context: { platform: selectedPlatform, goal: optimizationGoal }
      });
      
      setAnalysisResults({
        type: 'generation',
        platform: selectedPlatform,
        goal: optimizationGoal,
        ideas: result.ideas,
        trends: result.trends,
        hashtags: result.hashtags
      });
    } catch (error) {
      console.error('Failed to generate content:', error);
      alert('Failed to generate content. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  const executeFeature = () => {
    switch (activeFeature) {
      case 'optimize':
        optimizeContent();
        break;
      case 'sentiment':
        analyzeSentiment();
        break;
      case 'tags':
        generateTags();
        break;
      case 'predict':
        predictPerformance();
        break;
      case 'generate':
        generateContent();
        break;
      default:
        break;
    }
  };

  const getSentimentColor = (sentiment: string) => {
    switch (sentiment?.toLowerCase()) {
      case 'positive': return 'text-green-600 bg-green-100';
      case 'negative': return 'text-red-600 bg-red-100';
      case 'neutral': return 'text-gray-600 bg-gray-100';
      default: return 'text-blue-600 bg-blue-100';
    }
  };

  return (
    <div className="min-h-screen" style={{ backgroundColor: 'var(--aws-gray-50)' }}>
      {/* Header */}
      <div style={{ backgroundColor: 'var(--aws-blue)' }} className="text-white py-8">
        <div className="max-w-7xl mx-auto px-4">
          <h1 className="text-3xl font-bold mb-2">🤖 AI Assistant</h1>
          <p className="text-gray-300">Your intelligent companion for content optimization and analysis</p>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 py-8">
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-8">
          {/* Feature Selection */}
          <div className="lg:col-span-1">
            <div className="aws-card p-6">
              <h2 className="text-lg font-semibold mb-4">AI Features</h2>
              <div className="space-y-2">
                {aiFeatures.map((feature) => (
                  <button
                    key={feature.id}
                    onClick={() => setActiveFeature(feature.id)}
                    className={`w-full text-left p-3 rounded-lg transition-colors ${
                      activeFeature === feature.id
                        ? 'bg-orange-100 border-orange-500 border-2'
                        : 'bg-gray-50 hover:bg-gray-100 border border-gray-200'
                    }`}
                  >
                    <div className="font-medium text-sm">{feature.name}</div>
                    <div className="text-xs text-gray-600 mt-1">{feature.description}</div>
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* Main Content */}
          <div className="lg:col-span-3">
            {activeFeature === 'chat' ? (
              /* Chat Interface */
              <div className="aws-card h-[600px] flex flex-col">
                <div className="p-4 border-b border-gray-200">
                  <h2 className="text-lg font-semibold">AI Chat Assistant</h2>
                </div>
                
                <div className="flex-1 overflow-y-auto p-4 space-y-4">
                  {messages.map((message) => (
                    <div
                      key={message.id}
                      className={`flex ${message.type === 'user' ? 'justify-end' : 'justify-start'}`}
                    >
                      <div
                        className={`max-w-[80%] p-3 rounded-lg ${
                          message.type === 'user'
                            ? 'bg-orange-500 text-white'
                            : 'bg-gray-100 text-gray-900'
                        }`}
                      >
                        <div className="text-sm">{message.content}</div>
                        <div className={`text-xs mt-1 ${
                          message.type === 'user' ? 'text-orange-100' : 'text-gray-500'
                        }`}>
                          {message.timestamp.toLocaleTimeString()}
                        </div>
                      </div>
                    </div>
                  ))}
                  {isLoading && (
                    <div className="flex justify-start">
                      <div className="bg-gray-100 p-3 rounded-lg">
                        <div className="flex space-x-1">
                          <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"></div>
                          <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0.1s' }}></div>
                          <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0.2s' }}></div>
                        </div>
                      </div>
                    </div>
                  )}
                  <div ref={messagesEndRef} />
                </div>
                
                <div className="p-4 border-t border-gray-200">
                  <div className="flex space-x-2">
                    <input
                      type="text"
                      value={inputMessage}
                      onChange={(e) => setInputMessage(e.target.value)}
                      onKeyPress={(e) => e.key === 'Enter' && sendMessage()}
                      placeholder="Ask me anything about your content..."
                      className="flex-1 aws-input"
                      disabled={isLoading}
                    />
                    <button
                      onClick={sendMessage}
                      disabled={isLoading || !inputMessage.trim()}
                      className="aws-btn-primary px-6"
                    >
                      Send
                    </button>
                  </div>
                </div>
              </div>
            ) : (
              /* Feature Interface */
              <div className="space-y-6">
                <div className="aws-card p-6">
                  <h2 className="text-lg font-semibold mb-4">
                    {aiFeatures.find(f => f.id === activeFeature)?.name}
                  </h2>
                  
                  {/* Content Input */}
                  {activeFeature !== 'generate' && (
                    <div className="mb-4">
                      <label className="block text-sm font-medium mb-2">Content to Analyze</label>
                      <textarea
                        value={contentToOptimize}
                        onChange={(e) => setContentToOptimize(e.target.value)}
                        placeholder="Enter your content here..."
                        rows={4}
                        className="aws-input w-full resize-none"
                      />
                    </div>
                  )}

                  {/* Platform Selection */}
                  {(activeFeature === 'optimize' || activeFeature === 'predict' || activeFeature === 'generate') && (
                    <div className="mb-4">
                      <label className="block text-sm font-medium mb-2">Target Platform</label>
                      <div className="grid grid-cols-3 gap-2">
                        {platforms.map((platform) => (
                          <button
                            key={platform.id}
                            onClick={() => setSelectedPlatform(platform.id)}
                            className={`p-2 rounded-lg text-sm font-medium transition-colors ${
                              selectedPlatform === platform.id
                                ? 'bg-orange-500 text-white'
                                : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                            }`}
                          >
                            {platform.name}
                          </button>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Optimization Goal */}
                  {(activeFeature === 'optimize' || activeFeature === 'generate') && (
                    <div className="mb-4">
                      <label className="block text-sm font-medium mb-2">Optimization Goal</label>
                      <select
                        value={optimizationGoal}
                        onChange={(e) => setOptimizationGoal(e.target.value)}
                        className="aws-input w-full"
                      >
                        {optimizationGoals.map((goal) => (
                          <option key={goal.id} value={goal.id}>
                            {goal.name}
                          </option>
                        ))}
                      </select>
                    </div>
                  )}

                  <button
                    onClick={executeFeature}
                    disabled={isLoading || (activeFeature !== 'generate' && !contentToOptimize.trim())}
                    className={`aws-btn-primary w-full ${
                      isLoading ? 'opacity-50 cursor-not-allowed' : ''
                    }`}
                  >
                    {isLoading ? (
                      <span className="flex items-center justify-center">
                        <svg className="animate-spin -ml-1 mr-3 h-4 w-4 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                        </svg>
                        Processing...
                      </span>
                    ) : (
                      `Execute ${aiFeatures.find(f => f.id === activeFeature)?.name}`
                    )}
                  </button>
                </div>

                {/* Results */}
                {analysisResults && (
                  <div className="aws-card p-6">
                    <h3 className="text-lg font-semibold mb-4">Analysis Results</h3>
                    
                    {analysisResults.type === 'optimization' && (
                      <div className="space-y-4">
                        <div>
                          <h4 className="font-medium mb-2">Original Content</h4>
                          <div className="p-3 bg-gray-50 rounded-lg text-sm">
                            {analysisResults.original}
                          </div>
                        </div>
                        <div>
                          <h4 className="font-medium mb-2">Optimized Content</h4>
                          <div className="p-3 bg-green-50 border border-green-200 rounded-lg text-sm">
                            {analysisResults.optimized}
                          </div>
                        </div>
                        <div>
                          <h4 className="font-medium mb-2">Optimization Score</h4>
                          <div className="flex items-center space-x-2">
                            <div className="flex-1 bg-gray-200 rounded-full h-2">
                              <div
                                className="bg-green-500 h-2 rounded-full"
                                style={{ width: `${analysisResults.score}%` }}
                              ></div>
                            </div>
                            <span className="text-sm font-medium">{analysisResults.score}%</span>
                          </div>
                        </div>
                        {analysisResults.suggestions && (
                          <div>
                            <h4 className="font-medium mb-2">Suggestions</h4>
                            <ul className="space-y-1">
                              {analysisResults.suggestions.map((suggestion: string, index: number) => (
                                <li key={index} className="text-sm text-gray-600 flex items-start">
                                  <span className="text-orange-500 mr-2">•</span>
                                  {suggestion}
                                </li>
                              ))}
                            </ul>
                          </div>
                        )}
                      </div>
                    )}

                    {analysisResults.type === 'sentiment' && (
                      <div className="space-y-4">
                        <div className="flex items-center space-x-4">
                          <div>
                            <span className="text-sm text-gray-600">Sentiment:</span>
                            <span className={`ml-2 px-3 py-1 rounded-full text-sm font-medium ${getSentimentColor(analysisResults.sentiment)}`}>
                              {analysisResults.sentiment}
                            </span>
                          </div>
                          <div>
                            <span className="text-sm text-gray-600">Confidence:</span>
                            <span className="ml-2 font-medium">{(analysisResults.confidence * 100).toFixed(1)}%</span>
                          </div>
                        </div>
                        
                        {analysisResults.emotions && (
                          <div>
                            <h4 className="font-medium mb-2">Detected Emotions</h4>
                            <div className="flex flex-wrap gap-2">
                              {Object.entries(analysisResults.emotions).map(([emotion, score]: [string, any]) => (
                                <span
                                  key={emotion}
                                  className="px-2 py-1 bg-blue-100 text-blue-800 rounded-full text-xs"
                                >
                                  {emotion}: {(score * 100).toFixed(0)}%
                                </span>
                              ))}
                            </div>
                          </div>
                        )}

                        {analysisResults.keywords && (
                          <div>
                            <h4 className="font-medium mb-2">Key Topics</h4>
                            <div className="flex flex-wrap gap-2">
                              {analysisResults.keywords.map((keyword: string, index: number) => (
                                <span
                                  key={index}
                                  className="px-2 py-1 bg-gray-100 text-gray-700 rounded-full text-xs"
                                >
                                  {keyword}
                                </span>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                    )}

                    {analysisResults.type === 'tags' && (
                      <div className="space-y-4">
                        <div>
                          <h4 className="font-medium mb-2">Recommended Tags</h4>
                          <div className="flex flex-wrap gap-2">
                            {analysisResults.tags?.map((tag: string, index: number) => (
                              <span
                                key={index}
                                className="px-3 py-1 bg-orange-100 text-orange-800 rounded-full text-sm"
                              >
                                #{tag}
                              </span>
                            ))}
                          </div>
                        </div>

                        {analysisResults.trending && (
                          <div>
                            <h4 className="font-medium mb-2">Trending Tags</h4>
                            <div className="flex flex-wrap gap-2">
                              {analysisResults.trending?.map((tag: string, index: number) => (
                                <span
                                  key={index}
                                  className="px-3 py-1 bg-red-100 text-red-800 rounded-full text-sm"
                                >
                                  🔥 #{tag}
                                </span>
                              ))}
                            </div>
                          </div>
                        )}

                        {analysisResults.categories && (
                          <div>
                            <h4 className="font-medium mb-2">Content Categories</h4>
                            <div className="flex flex-wrap gap-2">
                              {analysisResults.categories?.map((category: string, index: number) => (
                                <span
                                  key={index}
                                  className="px-3 py-1 bg-blue-100 text-blue-800 rounded-full text-sm"
                                >
                                  {category}
                                </span>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                    )}

                    {analysisResults.type === 'prediction' && (
                      <div className="space-y-4">
                        <div className="grid grid-cols-2 gap-4">
                          <div className="p-4 bg-blue-50 rounded-lg">
                            <div className="text-2xl font-bold text-blue-600">
                              {analysisResults.predictedViews?.toLocaleString()}
                            </div>
                            <div className="text-sm text-blue-800">Predicted Views</div>
                          </div>
                          <div className="p-4 bg-green-50 rounded-lg">
                            <div className="text-2xl font-bold text-green-600">
                              {analysisResults.predictedEngagement?.toFixed(1)}%
                            </div>
                            <div className="text-sm text-green-800">Predicted Engagement</div>
                          </div>
                        </div>

                        <div>
                          <h4 className="font-medium mb-2">Confidence Level</h4>
                          <div className="flex items-center space-x-2">
                            <div className="flex-1 bg-gray-200 rounded-full h-2">
                              <div
                                className="bg-blue-500 h-2 rounded-full"
                                style={{ width: `${analysisResults.confidence * 100}%` }}
                              ></div>
                            </div>
                            <span className="text-sm font-medium">{(analysisResults.confidence * 100).toFixed(1)}%</span>
                          </div>
                        </div>

                        {analysisResults.factors && (
                          <div>
                            <h4 className="font-medium mb-2">Performance Factors</h4>
                            <ul className="space-y-1">
                              {analysisResults.factors.map((factor: string, index: number) => (
                                <li key={index} className="text-sm text-gray-600 flex items-start">
                                  <span className="text-blue-500 mr-2">•</span>
                                  {factor}
                                </li>
                              ))}
                            </ul>
                          </div>
                        )}

                        {analysisResults.recommendations && (
                          <div>
                            <h4 className="font-medium mb-2">Recommendations</h4>
                            <ul className="space-y-1">
                              {analysisResults.recommendations.map((rec: string, index: number) => (
                                <li key={index} className="text-sm text-gray-600 flex items-start">
                                  <span className="text-green-500 mr-2">✓</span>
                                  {rec}
                                </li>
                              ))}
                            </ul>
                          </div>
                        )}
                      </div>
                    )}

                    {analysisResults.type === 'generation' && (
                      <div className="space-y-4">
                        <div>
                          <h4 className="font-medium mb-2">Content Ideas</h4>
                          <div className="space-y-3">
                            {analysisResults.ideas?.map((idea: any, index: number) => (
                              <div key={index} className="p-3 bg-gray-50 rounded-lg">
                                <div className="font-medium text-sm mb-1">{idea.title}</div>
                                <div className="text-sm text-gray-600">{idea.description}</div>
                                {idea.tags && (
                                  <div className="flex flex-wrap gap-1 mt-2">
                                    {idea.tags.map((tag: string, tagIndex: number) => (
                                      <span
                                        key={tagIndex}
                                        className="px-2 py-1 bg-orange-100 text-orange-800 rounded text-xs"
                                      >
                                        #{tag}
                                      </span>
                                    ))}
                                  </div>
                                )}
                              </div>
                            ))}
                          </div>
                        </div>

                        {analysisResults.trends && (
                          <div>
                            <h4 className="font-medium mb-2">Current Trends</h4>
                            <div className="flex flex-wrap gap-2">
                              {analysisResults.trends?.map((trend: string, index: number) => (
                                <span
                                  key={index}
                                  className="px-3 py-1 bg-purple-100 text-purple-800 rounded-full text-sm"
                                >
                                  📈 {trend}
                                </span>
                              ))}
                            </div>
                          </div>
                        )}

                        {analysisResults.hashtags && (
                          <div>
                            <h4 className="font-medium mb-2">Suggested Hashtags</h4>
                            <div className="flex flex-wrap gap-2">
                              {analysisResults.hashtags?.map((hashtag: string, index: number) => (
                                <span
                                  key={index}
                                  className="px-2 py-1 bg-blue-100 text-blue-800 rounded text-sm"
                                >
                                  #{hashtag}
                                </span>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}