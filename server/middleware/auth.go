package middleware

import (
	"net/http"
	"os"
	"strings"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/golang-jwt/jwt/v5"
)

type JWTClaims struct {
	UserID      string   `json:"user_id"`
	Role        string   `json:"role"`
	Permissions []string `json:"permissions"`
	jwt.RegisteredClaims
}

// AuthMiddleware validates JWT and injects claims into context
func AuthMiddleware() gin.HandlerFunc {
	secret := os.Getenv("JWT_SECRET")
	if secret == "" {
		secret = "dev-secret-change-me"
	}
	return func(c *gin.Context) {
		auth := c.GetHeader("Authorization")
		if auth == "" || !strings.HasPrefix(auth, "Bearer ") {
			c.AbortWithStatusJSON(http.StatusUnauthorized, gin.H{"error": "missing bearer token"})
			return
		}
		tokenString := strings.TrimPrefix(auth, "Bearer ")
		claims := &JWTClaims{}
		token, err := jwt.ParseWithClaims(tokenString, claims, func(t *jwt.Token) (interface{}, error) {
			return []byte(secret), nil
		})
		if err != nil || !token.Valid || claims.ExpiresAt == nil || time.Until(claims.ExpiresAt.Time) < 0 {
			c.AbortWithStatusJSON(http.StatusUnauthorized, gin.H{"error": "invalid token"})
			return
		}
		c.Set("user_id", claims.UserID)
		c.Set("role", claims.Role)
		c.Set("permissions", claims.Permissions)
		c.Next()
	}
}

// RequirePermissions ensures the user has ALL required permissions
func RequirePermissions(perms ...string) gin.HandlerFunc {
	permSet := map[string]struct{}{}
	for _, p := range perms { permSet[p] = struct{}{} }
	return func(c *gin.Context) {
		val, ok := c.Get("permissions")
		if !ok {
			c.AbortWithStatusJSON(http.StatusForbidden, gin.H{"error": "no permissions"})
			return
		}
		userPerms, _ := val.([]string)
		userSet := map[string]struct{}{}
		for _, p := range userPerms { userSet[p] = struct{}{} }
		for p := range permSet {
			if _, ok := userSet[p]; !ok {
				c.AbortWithStatusJSON(http.StatusForbidden, gin.H{"error": "permission denied", "missing": p})
				return
			}
		}
		c.Next()
	}
}
