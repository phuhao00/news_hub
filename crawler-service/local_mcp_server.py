#!/usr/bin/env python3
"""
本地MCP服务器
提供本地文件系统访问和内容处理功能
"""

import asyncio
import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime

from fastmcp import FastMCP
from pydantic import BaseModel


class LocalMCPServer:
    """本地MCP服务器类"""
    
    def __init__(self, name: str = "local-mcp-server", port: int = 8080):
        self.name = name
        self.port = port
        self.mcp = FastMCP(name)
        self.setup_tools()
        
    def setup_tools(self):
        """设置MCP工具"""
        
        @self.mcp.tool()
        async def read_file(file_path: str) -> Dict[str, Any]:
            """读取本地文件内容
            
            Args:
                file_path: 文件路径
                
            Returns:
                包含文件内容和元数据的字典
            """
            try:
                path = Path(file_path)
                if not path.exists():
                    return {
                        "success": False,
                        "error": f"文件不存在: {file_path}",
                        "content": None
                    }
                    
                if not path.is_file():
                    return {
                        "success": False,
                        "error": f"路径不是文件: {file_path}",
                        "content": None
                    }
                
                # 读取文件内容
                with open(path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    
                # 获取文件信息
                stat = path.stat()
                
                return {
                    "success": True,
                    "content": content,
                    "metadata": {
                        "file_path": str(path.absolute()),
                        "file_size": stat.st_size,
                        "modified_time": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                        "created_time": datetime.fromtimestamp(stat.st_ctime).isoformat()
                    }
                }
                
            except Exception as e:
                return {
                    "success": False,
                    "error": f"读取文件失败: {str(e)}",
                    "content": None
                }
        
        @self.mcp.tool()
        async def write_file(file_path: str, content: str, create_dirs: bool = True) -> Dict[str, Any]:
            """写入文件内容
            
            Args:
                file_path: 文件路径
                content: 文件内容
                create_dirs: 是否创建目录
                
            Returns:
                操作结果
            """
            try:
                path = Path(file_path)
                
                # 创建目录
                if create_dirs:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    
                # 写入文件
                with open(path, 'w', encoding='utf-8') as f:
                    f.write(content)
                    
                return {
                    "success": True,
                    "message": f"文件写入成功: {file_path}",
                    "file_path": str(path.absolute())
                }
                
            except Exception as e:
                return {
                    "success": False,
                    "error": f"写入文件失败: {str(e)}"
                }
        
        @self.mcp.tool()
        async def list_directory(dir_path: str, recursive: bool = False) -> Dict[str, Any]:
            """列出目录内容
            
            Args:
                dir_path: 目录路径
                recursive: 是否递归列出
                
            Returns:
                目录内容列表
            """
            try:
                path = Path(dir_path)
                if not path.exists():
                    return {
                        "success": False,
                        "error": f"目录不存在: {dir_path}",
                        "files": []
                    }
                    
                if not path.is_dir():
                    return {
                        "success": False,
                        "error": f"路径不是目录: {dir_path}",
                        "files": []
                    }
                
                files = []
                
                if recursive:
                    for item in path.rglob('*'):
                        files.append({
                            "name": item.name,
                            "path": str(item.absolute()),
                            "is_file": item.is_file(),
                            "is_dir": item.is_dir(),
                            "size": item.stat().st_size if item.is_file() else 0
                        })
                else:
                    for item in path.iterdir():
                        files.append({
                            "name": item.name,
                            "path": str(item.absolute()),
                            "is_file": item.is_file(),
                            "is_dir": item.is_dir(),
                            "size": item.stat().st_size if item.is_file() else 0
                        })
                
                return {
                    "success": True,
                    "files": files,
                    "total_count": len(files)
                }
                
            except Exception as e:
                return {
                    "success": False,
                    "error": f"列出目录失败: {str(e)}",
                    "files": []
                }
        
        @self.mcp.tool()
        async def get_server_status() -> Dict[str, Any]:
            """获取服务器状态
            
            Returns:
                服务器状态信息
            """
            return {
                "server_name": self.name,
                "server_type": "local_mcp",
                "status": "running",
                "port": self.port,
                "capabilities": [
                    "file_read",
                    "file_write",
                    "directory_list",
                    "file_system_access"
                ],
                "timestamp": datetime.now().isoformat()
            }
    
    def create_http_app(self):
        """创建HTTP应用"""
        from fastapi import FastAPI
        import uvicorn
        
        app = FastAPI(title=f"Local MCP Server - {self.name}", version="1.0.0")
        
        @app.post("/fetch")
        async def fetch_endpoint(request: dict):
            """HTTP端点用于获取网页内容（本地MCP实现简单的HTTP请求）"""
            try:
                import aiohttp
                url = request.get('url')
                if not url:
                    return {'success': False, 'error': 'URL is required'}
                
                async with aiohttp.ClientSession() as session:
                    async with session.get(url) as response:
                        content = await response.text()
                        return {
                            'success': True,
                            'content': content,
                            'status_code': response.status,
                            'headers': dict(response.headers),
                            'url': url
                        }
            except Exception as e:
                return {'success': False, 'error': str(e)}
        
        @app.get("/status")
        async def status_endpoint():
            """获取服务器状态"""
            return {
                "server_name": self.name,
                "server_type": "local_mcp",
                "status": "running",
                "port": self.port,
                "capabilities": [
                    "file_read",
                    "file_write",
                    "directory_list",
                    "file_system_access",
                    "http_fetch"
                ],
                "timestamp": datetime.now().isoformat()
            }
        
        return app
    
    def run(self):
        """运行HTTP服务器"""
        try:
            import uvicorn
            app = self.create_http_app()
            print(f"启动本地MCP HTTP服务器: {self.name} on port {self.port}")
            uvicorn.run(app, host="0.0.0.0", port=self.port, log_level="info")
        except Exception as e:
            print(f"服务器运行错误: {e}")


if __name__ == "__main__":
    server = LocalMCPServer()
    server.run()