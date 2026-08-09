import httpx
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

# Define where the independent microservices are running
SERVICE_ROUTES = {
    "mail": "http://127.0.0.1:8000",
    "vision": "http://127.0.0.1:8001",
    "voice": "http://127.0.0.1:8002",
    "social": "http://127.0.0.1:8003",
}

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Use a high timeout (300 seconds) because AI models (especially CPU inference) can take time.
    app.state.client = httpx.AsyncClient(timeout=300.0)
    yield
    await app.state.client.aclose()

app = FastAPI(
    title="NUNM.AI API Gateway",
    description="Reverse Proxy for routing requests to independent NUNM.AI microservices.",
    version="1.1.0",
    lifespan=lifespan
)

# Configure CORS so the React frontend can talk to it
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def health_check():
    return {"status": "ok", "message": "NUNM.AI API Gateway is running on port 8080."}

@app.api_route("/{service_name}/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def reverse_proxy(request: Request, service_name: str, path: str):
    if service_name not in SERVICE_ROUTES:
        raise HTTPException(status_code=404, detail=f"Service '{service_name}' not found.")
        
    client = request.app.state.client
    target_base_url = SERVICE_ROUTES[service_name]
    target_url = httpx.URL(f"{target_base_url}/{path}", query=request.url.query.encode("utf-8"))
    
    headers = dict(request.headers)
    headers.pop("host", None) # Remove host to prevent target server routing conflicts
    
    # Read body into memory. For true gigabyte file streaming we'd use request.stream(), 
    # but for typical video uploads <100MB, awaiting body is safe and avoids chunked-encoding issues with FastAPI.
    body = await request.body()
    
    rp_req = client.build_request(
        request.method, 
        target_url, 
        headers=headers, 
        content=body
    )
    
    try:
        rp_resp = await client.send(rp_req, stream=True)
    except httpx.ConnectError:
        raise HTTPException(
            status_code=502, 
            detail=f"Target service '{service_name}' is down. Ensure it is running on {target_base_url}."
        )
        
    return StreamingResponse(
        rp_resp.aiter_raw(),
        status_code=rp_resp.status_code,
        headers=dict(rp_resp.headers)
    )

if __name__ == "__main__":
    import uvicorn
    print("Starting NUNM.AI API Gateway Proxy on port 8080...")
    # Bind to 0.0.0.0 so it can be accessed externally when hosted
    uvicorn.run(app, host="0.0.0.0", port=8080)
