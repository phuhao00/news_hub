// 初始化 MongoDB 数据库和集合
db = db.getSiblingDB('newshub');

// 创建集合和索引
print('创建集合和索引...');

// 创作者集合索引
db.creators.createIndex({ "username": 1, "platform": 1 }, { unique: true });
print('创建 creators 索引完成');

// 帖子集合索引  
db.posts.createIndex({ "creator_id": 1, "post_id": 1 }, { unique: true });
db.posts.createIndex({ "platform": 1 });
db.posts.createIndex({ "created_at": -1 });
print('创建 posts 索引完成');

// 爬虫任务集合索引
db.crawler_tasks.createIndex({ "platform": 1, "creator_url": 1, "status": 1 });
db.crawler_tasks.createIndex({ "created_at": -1 });
db.crawler_tasks.createIndex({ "status": 1 });
// 为按完成时间倒序查询最近完成任务提供支持
db.crawler_tasks.createIndex({ "platform": 1, "creator_url": 1, "status": 1, "completed_at": -1 });
// 任务结果中的标题（嵌套字段）+平台+完成时间，用于按标题分析或排查
db.crawler_tasks.createIndex({ "result.title": 1, "platform": 1, "completed_at": -1 });
print('创建 crawler_tasks 索引完成');

// 爬虫内容集合索引 - 重要的去重索引
db.crawler_contents.createIndex({ "content_hash": 1 }, { unique: true });
db.crawler_contents.createIndex({ "url": 1, "platform": 1 }, { unique: true, sparse: true });
db.crawler_contents.createIndex({ "origin_id": 1, "platform": 1 }, { unique: true, sparse: true });
// 标题+平台+时间，便于在 24h 时间窗口内做标题重复判定
db.crawler_contents.createIndex({ "title": 1, "platform": 1, "created_at": -1 });
// 标题+作者+平台+时间，支持更精细的去重（若存在）
db.crawler_contents.createIndex({ "title": 1, "author": 1, "platform": 1, "created_at": -1 });
db.crawler_contents.createIndex({ "platform": 1 });
db.crawler_contents.createIndex({ "published_at": -1 });
db.crawler_contents.createIndex({ "created_at": -1 });
db.crawler_contents.createIndex({ "task_id": 1 });
print('创建 crawler_contents 索引完成');

// 视频集合索引
db.videos.createIndex({ "post_ids": 1 });
db.videos.createIndex({ "status": 1 });
db.videos.createIndex({ "created_at": -1 });
print('创建 videos 索引完成');

// 发布任务集合索引
db.publish_tasks.createIndex({ "video_id": 1 });
db.publish_tasks.createIndex({ "status": 1 });
db.publish_tasks.createIndex({ "created_at": -1 });
print('创建 publish_tasks 索引完成');

print('所有索引创建完成！');

// 输出索引信息
print('\n=== 索引信息 ===');
print('creators 索引:');
printjson(db.creators.getIndexes());

print('\nposts 索引:');
printjson(db.posts.getIndexes());

print('\ncrawler_tasks 索引:');
printjson(db.crawler_tasks.getIndexes());

print('\ncrawler_contents 索引:');
printjson(db.crawler_contents.getIndexes());

print('\nvideos 索引:');
printjson(db.videos.getIndexes());

print('\npublish_tasks 索引:');
printjson(db.publish_tasks.getIndexes());

print('\n数据库初始化完成！');