"""
FastAPI Agent for AWS Cost Explorer MCP Server.
"""
import asyncio
import json
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse

from models import QueryRequest, QueryResponse, FinopsQueryRequest, FinopsResponse
from agent_orchestrator import AgentOrchestrator
from config import settings

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Lifespan context manager for startup/shutdown
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan."""
    logger.info("Starting FastAPI Agent")
    logger.info(f"Ollama URL: {settings.ollama_base_url}")
    logger.info(f"Ollama Model: {settings.ollama_model}")
    yield
    logger.info("Shutting down FastAPI Agent")


# Create FastAPI app
app = FastAPI(
    title="AWS Cost Explorer Agent",
    description="AI Agent for AWS Cost Analysis using MCP Server and Ollama",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize orchestrator
orchestrator = AgentOrchestrator()


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "AWS Cost Explorer Agent API",
        "version": "1.0.0",
        "docs": "/docs"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "ollama_url": settings.ollama_base_url,
        "ollama_model": settings.ollama_model
    }


@app.post("/query", response_model=FinopsResponse)
async def query_finops(request: FinopsQueryRequest) -> FinopsResponse:
    """
    Process a user query for the TAO Lens frontend.
    
    Args:
        request: FinopsQueryRequest with user's natural language question
        
    Returns:
        FinopsResponse matching the frontend contract
    """
    try:
        logger.info(f"Received finops query: {request.question} from user: {request.username}")
        
        # Process query through orchestrator
        response = await orchestrator.process_finops_query(request.question, request.username)
        
        logger.info("Finops query processed successfully")
        return response
        
    except Exception as e:
        logger.error(f"Error processing finops query: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error processing query: {str(e)}"
        )


@app.post("/query/stream")
async def query_finops_stream(request: FinopsQueryRequest):
    """
    SSE streaming endpoint — sends real-time progress events while
    processing the query, then emits the final result.
    """
    logger.info(f"Received streaming query: {request.question} from user: {request.username}")

    progress_queue: asyncio.Queue = asyncio.Queue()

    async def event_generator():
        # Launch the orchestrator in a background task
        task = asyncio.create_task(
            orchestrator.process_finops_query_stream(
                request.question, request.username, progress_queue
            )
        )

        # Stream progress events as they arrive
        while True:
            event = await progress_queue.get()
            if event is None:  # sentinel — progress done
                break
            yield f"event: progress\ndata: {json.dumps(event)}\n\n"

        # Await final result and send it
        result = await task
        yield f"event: result\ndata: {result.model_dump_json()}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # disable nginx buffering
        },
    )


@app.post("/api/query", response_model=QueryResponse)
async def query(request: QueryRequest) -> QueryResponse:
    """
    Process a user query about AWS costs.
    
    Args:
        request: QueryRequest with user's natural language query
        
    Returns:
        QueryResponse with summary, chart_data, and table_data
    """
    try:
        logger.info(f"Received query: {request.query}")
        
        # Process query through orchestrator
        response = await orchestrator.process_query(request.query)
        
        logger.info("Query processed successfully")
        return response
        
    except Exception as e:
        logger.error(f"Error processing query: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error processing query: {str(e)}"
        )


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler."""
    logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "summary": f"An error occurred: {str(exc)}",
            "chart_data": [],
            "table_data": [],
            "success": False,
            "error": str(exc)
        }
    )


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.api_reload,
        log_level=settings.log_level.lower()
    )
