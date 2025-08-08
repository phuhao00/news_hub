package handlers

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"net/http"
	"os"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/golang-jwt/jwt/v5"
	"go.mongodb.org/mongo-driver/bson"
	"go.mongodb.org/mongo-driver/bson/primitive"

	"newshub/config"
	"newshub/models"
)

type registerRequest struct {
	Username string `json:"username"`
	Email    string `json:"email"`
	Password string `json:"password"`
	Role     string `json:"role"` // optional override (admin only normally) - restricted here
}

type loginRequest struct {
	Identity string `json:"identity"` // username or email
	Password string `json:"password"`
}

func hashPassword(pw string) string {
	h := sha256.Sum256([]byte(pw))
	return hex.EncodeToString(h[:])
}

func generateJWT(u models.User) (string, error) {
	secret := os.Getenv("JWT_SECRET")
	if secret == "" { secret = "dev-secret-change-me" }
	claims := jwt.MapClaims{
		"user_id":    u.ID.Hex(),
		"role":       u.Role,
		"permissions": u.Permissions,
		"exp":        time.Now().Add(24 * time.Hour).Unix(),
		"iat":        time.Now().Unix(),
	}
	token := jwt.NewWithClaims(jwt.SigningMethodHS256, claims)
	return token.SignedString([]byte(secret))
}

// Register creates a basic user (role viewer/editor depending on request, default viewer)
func Register(c *gin.Context) {
	var req registerRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}
	if req.Username == "" || req.Email == "" || req.Password == "" {
		c.JSON(http.StatusBadRequest, gin.H{"error": "missing fields"})
		return
	}
	role := req.Role
	if role == "" { role = "viewer" }
	if _, ok := models.DefaultRolePermissions[role]; !ok { role = "viewer" }

	db := config.GetDB()
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	// uniqueness
	count, _ := db.Collection("users").CountDocuments(ctx, bson.M{"$or": []bson.M{{"username": req.Username}, {"email": req.Email}}})
	if count > 0 {
		c.JSON(http.StatusConflict, gin.H{"error": "user exists"})
		return
	}

	u := models.User{
		ID:           primitive.NewObjectID(),
		Username:     req.Username,
		Email:        req.Email,
		PasswordHash: hashPassword(req.Password),
		Role:         role,
		Permissions:  models.DefaultRolePermissions[role],
		CreatedAt:    time.Now(),
		UpdatedAt:    time.Now(),
	}
	if _, err := db.Collection("users").InsertOne(ctx, u); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "create user failed"})
		return
	}
	token, _ := generateJWT(u)
	c.JSON(http.StatusCreated, gin.H{"user": gin.H{"id": u.ID.Hex(), "username": u.Username, "role": u.Role, "permissions": u.Permissions}, "token": token})
}

// Login authenticates user
func Login(c *gin.Context) {
	var req loginRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}
	if req.Identity == "" || req.Password == "" {
		c.JSON(http.StatusBadRequest, gin.H{"error": "missing fields"})
		return
	}
	db := config.GetDB()
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	var user models.User
	err := db.Collection("users").FindOne(ctx, bson.M{"$or": []bson.M{{"username": req.Identity}, {"email": req.Identity}}}).Decode(&user)
	if err != nil || user.PasswordHash != hashPassword(req.Password) {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "invalid credentials"})
		return
	}
	now := time.Now()
	db.Collection("users").UpdateOne(ctx, bson.M{"_id": user.ID}, bson.M{"$set": bson.M{"last_login_at": now}})
	token, _ := generateJWT(user)
	c.JSON(http.StatusOK, gin.H{"user": gin.H{"id": user.ID.Hex(), "username": user.Username, "role": user.Role, "permissions": user.Permissions}, "token": token})
}
