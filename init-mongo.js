db = db.getSiblingDB('newshub');

// 创建集合
db.createCollection('creators');
db.createCollection('posts');
db.createCollection('videos');
db.createCollection('publish_tasks');

// 创建索引
db.creators.createIndex({ "platform": 1, "username": 1 }, { unique: true });
db.posts.createIndex({ "creator_id": 1, "platform": 1, "post_id": 1 }, { unique: true });
db.videos.createIndex({ "created_at": 1 });
db.publish_tasks.createIndex({ "video_id": 1, "platform": 1 }, { unique: true });

// 设置TTL索引，自动清理30天前的数据
db.posts.createIndex({ "created_at": 1 }, { expireAfterSeconds: 2592000 }); // 30天
db.videos.createIndex({ "created_at": 1 }, { expireAfterSeconds: 2592000 }); // 30天
db.publish_tasks.createIndex({ "created_at": 1 }, { expireAfterSeconds: 2592000 }); // 30天