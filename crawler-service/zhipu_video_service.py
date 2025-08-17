from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from zhipuai import ZhipuAI
import os

app = FastAPI(title="Zhipu Video Service", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class GenerateReq(BaseModel):
    prompt: Optional[str] = None

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.post("/video/generate")
async def video_generate(req: GenerateReq):
    api_key = os.getenv("ZHIPU_API_KEY", "")
    if not api_key:
        raise HTTPException(status_code=500, detail="ZHIPU_API_KEY 未配置")
    prompt = req.prompt or "基于社媒内容生成一段约6秒的视频"
    try:
        client = ZhipuAI(api_key=api_key)
        resp = client.videos.generations(model="cogvideox", prompt=prompt)
        task_id = None
        # 兼容对象/字典
        try:
            task_id = getattr(resp, 'id', None)
        except Exception:
            pass
        if not task_id and isinstance(resp, dict):
            data = resp.get('data') or resp
            task_id = data.get('id') or data.get('task_id')
        if not task_id:
            raise HTTPException(status_code=502, detail=f"未获取到任务ID: {resp}")
        return {"task_id": task_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"智谱任务创建失败: {e}")

@app.get("/video/status/{task_id}")
async def video_status(task_id: str):
    api_key = os.getenv("ZHIPU_API_KEY", "")
    if not api_key:
        raise HTTPException(status_code=500, detail="ZHIPU_API_KEY 未配置")
    try:
        client = ZhipuAI(api_key=api_key)
        resp = client.videos.retrieve_videos_result(id=task_id)
        status = None
        url = None
        try:
            status = getattr(resp, 'task_status', None)
            vr = getattr(resp, 'video_result', None)
            if isinstance(vr, list) and vr:
                url = vr[0].get('url') if isinstance(vr[0], dict) else None
        except Exception:
            pass
        if not status and isinstance(resp, dict):
            data = resp.get('data') or resp
            status = data.get('task_status')
            vr = data.get('video_result') or []
            if isinstance(vr, list) and vr and isinstance(vr[0], dict):
                url = vr[0].get('url')
        return {"task_status": status, "video_result": [{"url": url}] if url else []}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"智谱任务查询失败: {e}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8010)
