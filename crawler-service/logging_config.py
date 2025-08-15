#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
日志配置模块
提供统一的日志配置和管理功能
"""

import logging
import logging.config
import os
from datetime import datetime
from pathlib import Path

# 创建日志目录
LOG_DIR = Path(__file__).parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

# 日志配置
LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "detailed": {
            "format": "%(asctime)s [%(levelname)8s] %(name)s:%(lineno)d - %(funcName)s() - %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S"
        },
        "simple": {
            "format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S"
        },
        "json": {
            "format": '{"timestamp": "%(asctime)s", "level": "%(levelname)s", "logger": "%(name)s", "function": "%(funcName)s", "line": %(lineno)d, "message": "%(message)s"}',
            "datefmt": "%Y-%m-%d %H:%M:%S"
        }
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "level": "INFO",
            "formatter": "simple",
            "stream": "ext://sys.stdout"
        },
        "file_info": {
            "class": "logging.handlers.RotatingFileHandler",
            "level": "INFO",
            "formatter": "detailed",
            "filename": str(LOG_DIR / "crawler_service.log"),
            "maxBytes": 10485760,  # 10MB
            "backupCount": 5,
            "encoding": "utf-8"
        },
        "file_error": {
            "class": "logging.handlers.RotatingFileHandler",
            "level": "ERROR",
            "formatter": "detailed",
            "filename": str(LOG_DIR / "crawler_service_error.log"),
            "maxBytes": 10485760,  # 10MB
            "backupCount": 5,
            "encoding": "utf-8"
        },
        "login_state_file": {
            "class": "logging.handlers.RotatingFileHandler",
            "level": "DEBUG",
            "formatter": "detailed",
            "filename": str(LOG_DIR / "login_state.log"),
            "maxBytes": 10485760,  # 10MB
            "backupCount": 3,
            "encoding": "utf-8"
        },
        "browser_manager_file": {
            "class": "logging.handlers.RotatingFileHandler",
            "level": "DEBUG",
            "formatter": "detailed",
            "filename": str(LOG_DIR / "browser_manager.log"),
            "maxBytes": 10485760,  # 10MB
            "backupCount": 3,
            "encoding": "utf-8"
        },
        "session_manager_file": {
            "class": "logging.handlers.RotatingFileHandler",
            "level": "DEBUG",
            "formatter": "detailed",
            "filename": str(LOG_DIR / "session_manager.log"),
            "maxBytes": 5242880,  # 5MB
            "backupCount": 3,
            "encoding": "utf-8"
        },
        "crawl_file": {
            "class": "logging.handlers.RotatingFileHandler",
            "level": "DEBUG",
            "formatter": "detailed",
            "filename": str(LOG_DIR / "crawl_operations.log"),
            "maxBytes": 10485760,  # 10MB
            "backupCount": 5,
            "encoding": "utf-8"
        }
    },
    "loggers": {
        "login_state": {
            "level": "DEBUG",
            "handlers": ["console", "login_state_file", "file_error"],
            "propagate": False
        },
        "login_state.browser_manager": {
            "level": "DEBUG",
            "handlers": ["console", "browser_manager_file", "file_error"],
            "propagate": False
        },
        "login_state.session_manager": {
            "level": "DEBUG",
            "handlers": ["console", "session_manager_file", "file_error"],
            "propagate": False
        },
        "crawl_operations": {
            "level": "DEBUG",
            "handlers": ["console", "crawl_file", "file_error"],
            "propagate": False
        },
        "uvicorn": {
            "level": "INFO",
            "handlers": ["console", "file_info"],
            "propagate": False
        },
        "fastapi": {
            "level": "INFO",
            "handlers": ["console", "file_info"],
            "propagate": False
        }
    },
    "root": {
        "level": "INFO",
        "handlers": ["console", "file_info", "file_error"]
    }
}

def setup_logging(config_dict=None, log_level=None):
    """
    设置日志配置
    
    Args:
        config_dict: 自定义日志配置字典
        log_level: 日志级别 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    if config_dict is None:
        config_dict = LOGGING_CONFIG
    
    # 如果指定了日志级别，更新配置
    if log_level:
        log_level = log_level.upper()
        # 更新所有处理器的级别
        for handler_name, handler_config in config_dict["handlers"].items():
            if handler_name == "console":
                handler_config["level"] = log_level
        
        # 更新所有日志器的级别
        for logger_name, logger_config in config_dict["loggers"].items():
            logger_config["level"] = log_level
        
        config_dict["root"]["level"] = log_level
    
    # 应用日志配置
    logging.config.dictConfig(config_dict)
    
    # 记录日志配置完成
    logger = logging.getLogger(__name__)
    logger.info(f"日志配置已完成，日志目录: {LOG_DIR}")
    logger.info(f"当前日志级别: {log_level or 'INFO'}")

def get_logger(name):
    """
    获取指定名称的日志器
    
    Args:
        name: 日志器名称
    
    Returns:
        logging.Logger: 配置好的日志器
    """
    return logging.getLogger(name)

def log_function_call(func):
    """
    装饰器：记录函数调用
    
    Args:
        func: 被装饰的函数
    
    Returns:
        装饰后的函数
    """
    def wrapper(*args, **kwargs):
        logger = logging.getLogger(func.__module__)
        logger.debug(f"调用函数: {func.__name__}, 参数: args={args}, kwargs={kwargs}")
        try:
            result = func(*args, **kwargs)
            logger.debug(f"函数 {func.__name__} 执行成功")
            return result
        except Exception as e:
            logger.error(f"函数 {func.__name__} 执行失败: {e}", exc_info=True)
            raise
    return wrapper

def log_async_function_call(func):
    """
    装饰器：记录异步函数调用
    
    Args:
        func: 被装饰的异步函数
    
    Returns:
        装饰后的异步函数
    """
    async def wrapper(*args, **kwargs):
        logger = logging.getLogger(func.__module__)
        logger.debug(f"调用异步函数: {func.__name__}, 参数: args={args}, kwargs={kwargs}")
        try:
            result = await func(*args, **kwargs)
            logger.debug(f"异步函数 {func.__name__} 执行成功")
            return result
        except Exception as e:
            logger.error(f"异步函数 {func.__name__} 执行失败: {e}", exc_info=True)
            raise
    return wrapper

class LoggerMixin:
    """
    日志器混入类，为类提供日志功能
    """
    
    @property
    def logger(self):
        """获取当前类的日志器"""
        if not hasattr(self, '_logger'):
            self._logger = logging.getLogger(f"{self.__class__.__module__}.{self.__class__.__name__}")
        return self._logger
    
    def log_method_call(self, method_name, *args, **kwargs):
        """记录方法调用"""
        self.logger.debug(f"调用方法: {method_name}, 参数: args={args}, kwargs={kwargs}")
    
    def log_method_success(self, method_name, result=None):
        """记录方法成功"""
        if result is not None:
            self.logger.debug(f"方法 {method_name} 执行成功，结果: {result}")
        else:
            self.logger.debug(f"方法 {method_name} 执行成功")
    
    def log_method_error(self, method_name, error):
        """记录方法错误"""
        self.logger.error(f"方法 {method_name} 执行失败: {error}", exc_info=True)

if __name__ == "__main__":
    # 测试日志配置
    setup_logging()
    
    logger = get_logger(__name__)
    logger.info("日志配置测试开始")
    logger.debug("这是一条调试信息")
    logger.warning("这是一条警告信息")
    logger.error("这是一条错误信息")
    logger.info("日志配置测试完成")