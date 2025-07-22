package middleware

import (
	"net/http"
	"regexp"
	"strings"

	"github.com/gin-gonic/gin"
	"github.com/gin-gonic/gin/binding"
	"github.com/go-playground/validator/v10"
)

// 自定义验证器
var (
	// 检查URL格式
	isValidURL = regexp.MustCompile(`^https?://[\w\d\-\.]+\.[a-z]{2,}(?:/[\w\d\-\._~:/?#\[\]@!$&'()*+,;=]*)?$`)
	// 检查视频ID格式
	isValidVideoID = regexp.MustCompile(`^[a-zA-Z0-9\-_]{6,}$`)
)

// 注册自定义验证器
func RegisterCustomValidators() {
	if v, ok := binding.Validator.Engine().(*validator.Validate); ok {
		// 注册URL格式验证器
		_ = v.RegisterValidation("validurl", func(fl validator.FieldLevel) bool {
			return isValidURL.MatchString(fl.Field().String())
		})

		// 注册视频ID格式验证器
		_ = v.RegisterValidation("validvideoid", func(fl validator.FieldLevel) bool {
			return isValidVideoID.MatchString(fl.Field().String())
		})

		// 注册平台名称验证器
		_ = v.RegisterValidation("validplatform", func(fl validator.FieldLevel) bool {
			validPlatforms := map[string]bool{
				"youtube":    true,
				"twitter":    true,
				"instagram": true,
				"tiktok":    true,
			}
			return validPlatforms[strings.ToLower(fl.Field().String())]
		})
	}
}

// ValidateRequestBody 验证请求体中的参数
func ValidateRequestBody(model interface{}) gin.HandlerFunc {
	return func(c *gin.Context) {
		if err := c.ShouldBindJSON(model); err != nil {
			var errorMessages []string
			if ve, ok := err.(validator.ValidationErrors); ok {
				for _, e := range ve {
					switch e.Tag() {
					case "required":
						errorMessages = append(errorMessages,
							getFieldName(e.Field())+"是必填项")
					case "validurl":
						errorMessages = append(errorMessages,
							getFieldName(e.Field())+"必须是有效的URL")
					case "validvideoid":
						errorMessages = append(errorMessages,
							getFieldName(e.Field())+"格式不正确")
					case "validplatform":
						errorMessages = append(errorMessages,
							getFieldName(e.Field())+"不是支持的平台")
					default:
						errorMessages = append(errorMessages,
							getFieldName(e.Field())+"验证失败")
					}
				}
			} else {
				errorMessages = append(errorMessages, "请求参数格式错误")
			}

			c.JSON(http.StatusBadRequest, gin.H{
				"error":   "参数验证失败",
				"details": errorMessages,
			})
			c.Abort()
			return
		}
		c.Next()
	}
}

// ValidateQueryParams 验证URL查询参数
func ValidateQueryParams(rules map[string][]string) gin.HandlerFunc {
	return func(c *gin.Context) {
		var errorMessages []string

		for param, validations := range rules {
			value := c.Query(param)

			for _, rule := range validations {
				switch rule {
				case "required":
					if value == "" {
						errorMessages = append(errorMessages,
							param+"是必填项")
					}
				case "validurl":
					if value != "" && !isValidURL.MatchString(value) {
						errorMessages = append(errorMessages,
							param+"必须是有效的URL")
					}
				case "validvideoid":
					if value != "" && !isValidVideoID.MatchString(value) {
						errorMessages = append(errorMessages,
							param+"格式不正确")
					}
				}
			}
		}

		if len(errorMessages) > 0 {
			c.JSON(http.StatusBadRequest, gin.H{
				"error":   "参数验证失败",
				"details": errorMessages,
			})
			c.Abort()
			return
		}

		c.Next()
	}
}

// getFieldName 获取字段的中文名称
func getFieldName(field string) string {
	// 可以根据需要扩展字段映射
	fieldNames := map[string]string{
		"URL":         "链接",
		"VideoID":     "视频ID",
		"Platform":    "平台",
		"Description": "描述",
		"Name":        "名称",
		"Title":       "标题",
	}

	if name, ok := fieldNames[field]; ok {
		return name
	}
	return field
}