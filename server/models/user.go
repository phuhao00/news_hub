package models

import (
	"time"

	"go.mongodb.org/mongo-driver/bson/primitive"
)

// User represents an application user with role based access control
// Roles: admin, editor, viewer
// Permissions are explicit strings aggregated per role but can also be customized per user
// (simple implementation kept in a single document for now)
type User struct {
	ID          primitive.ObjectID `bson:"_id,omitempty" json:"id"`
	Username    string             `bson:"username" json:"username"`
	Email       string             `bson:"email" json:"email"`
	PasswordHash string            `bson:"password_hash" json:"-"`
	Role        string             `bson:"role" json:"role"`
	Permissions []string           `bson:"permissions" json:"permissions"`
	CreatedAt   time.Time          `bson:"created_at" json:"created_at"`
	UpdatedAt   time.Time          `bson:"updated_at" json:"updated_at"`
	LastLoginAt *time.Time         `bson:"last_login_at,omitempty" json:"last_login_at,omitempty"`
}

// Role -> default permissions (coarse grained for demo)
var DefaultRolePermissions = map[string][]string{
	"admin": {
		"creators:read", "creators:write",
		"videos:read", "videos:generate",
		"publish:read", "publish:write",
		"crawler:read", "crawler:write",
		"jobs:read", "jobs:manage",
		"analytics:read",
	},
	"editor": {
		"creators:read",
		"videos:read", "videos:generate",
		"publish:read", "publish:write",
		"crawler:read", "crawler:write",
		"analytics:read",
	},
	"viewer": {
		"creators:read", "videos:read", "publish:read", "crawler:read", "analytics:read",
	},
}
