from datetime import datetime
from typing import List, Optional
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from models import (
    ProcessChatRequest, ProcessChatResponse, GetActionsRequest,
    CloseActionRequest, MergeActionRequest, ActionSummary, Action,
    ActionStatus, ChatMessage, Message
)
from db import db_manager
from nlp import action_extractor
from matcher import action_matcher
from history_logger import history_logger

app = FastAPI(
    title="Action Tracker Service",
    description="Service for extracting and tracking action items from RM-Client chat messages",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_event():
    print("Action Tracker Service starting up...")
    print(f"Database initialized at: {db_manager.db_path}")
    print("Rule-based action extraction enabled")


@app.get("/")
async def root():
    return {
        "service": "Action Tracker Service",
        "version": "1.0.0",
        "status": "running",
        "endpoints": {
            "process_chat": "POST /process_chat",
            "get_actions": "GET /actions",
            "close_action": "PUT /actions/{id}/close",
            "merge_actions": "POST /actions/{id}/merge"
        }
    }


@app.post("/process_chat", response_model=ProcessChatResponse)
async def process_chat(request: ProcessChatRequest):
    try:
        processed_messages = 0
        total_stats = {
            'created': 0,
            'updated': 0,
            'closed': 0,
            'tentative': 0
        }
        
        for chat_message in request.messages:
            message = Message(
                message_id=chat_message.message_id,
                conversation_id=request.conversation_id,
                sender=chat_message.sender,
                text=chat_message.text,
                received_at=chat_message.ts,
                processed=False
            )
            
            message_id = db_manager.save_message(message)
            if message_id:
                processed_messages += 1
                
                extracted_actions = action_extractor.extract_actions(
                    chat_message.text, 
                    chat_message.sender
                )
                
                if extracted_actions:
                    stats = action_matcher.process_extracted_actions(
                        extracted_actions=extracted_actions,
                        client_id=request.client_id,
                        conversation_id=request.conversation_id,
                        source_message_id=chat_message.message_id,
                        source_text=chat_message.text
                    )
                    
                    for key, value in stats.items():
                        total_stats[key] += value
                
                db_manager.mark_message_processed(chat_message.message_id)
        
        summary_parts = []
        if total_stats['created'] > 0:
            summary_parts.append(f"Created {total_stats['created']} new actions")
        if total_stats['updated'] > 0:
            summary_parts.append(f"Updated {total_stats['updated']} existing actions")
        if total_stats['closed'] > 0:
            summary_parts.append(f"Closed {total_stats['closed']} actions")
        if total_stats['tentative'] > 0:
            summary_parts.append(f"Created {total_stats['tentative']} tentative actions for review")
        
        summary = "; ".join(summary_parts) if summary_parts else "No actions processed"
        
        return ProcessChatResponse(
            processed_messages=processed_messages,
            created_actions=total_stats['created'],
            updated_actions=total_stats['updated'],
            closed_actions=total_stats['closed'],
            tentative_actions=total_stats['tentative'],
            summary=summary
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing chat: {str(e)}")


@app.get("/actions", response_model=List[ActionSummary])
async def get_actions(
    client_id: Optional[str] = Query(None, description="Filter by client ID"),
    status: Optional[ActionStatus] = Query(None, description="Filter by status"),
    limit: int = Query(100, description="Maximum number of actions to return")
):
    try:
        actions = db_manager.get_actions(
            client_id=client_id,
            status=status,
            limit=limit
        )
        
        action_summaries = []
        for action in actions:
            latest_history = db_manager.get_latest_action_history(action.id)
            
            summary = ActionSummary(
                id=action.id,
                client_id=action.client_id,
                task_type=action.task_type,
                task_text=action.task_text,
                owner=action.owner,
                status=action.status,
                metadata=action.metadata,
                created_at=action.created_at,
                updated_at=action.updated_at,
                latest_history=latest_history
            )
            action_summaries.append(summary)
        
        return action_summaries
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving actions: {str(e)}")


@app.put("/actions/{action_id}/close")
async def close_action(action_id: int, request: CloseActionRequest):
    try:
        action = db_manager.get_action_by_id(action_id)
        if not action:
            raise HTTPException(status_code=404, detail="Action not found")
        
        success = db_manager.update_action(action_id, {'status': ActionStatus.CLOSED})
        if not success:
            raise HTTPException(status_code=500, detail="Failed to update action")
        
        history_logger.log_action_closure(
            action_id=action_id,
            reason=request.reason,
            source_message_id=request.source_message_id,
            actor='user'
        )
        
        updated_action = db_manager.get_action_by_id(action_id)
        return {
            "message": "Action closed successfully",
            "action": updated_action
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error closing action: {str(e)}")


@app.post("/actions/{source_action_id}/merge")
async def merge_actions(source_action_id: int, request: MergeActionRequest):
    try:
        source_action = db_manager.get_action_by_id(source_action_id)
        target_action = db_manager.get_action_by_id(request.target_action_id)
        
        if not source_action:
            raise HTTPException(status_code=404, detail="Source action not found")
        if not target_action:
            raise HTTPException(status_code=404, detail="Target action not found")
        
        if source_action.client_id != target_action.client_id:
            raise HTTPException(
                status_code=400, 
                detail="Cannot merge actions from different clients"
            )
        
        merged_metadata = action_matcher._merge_metadata(
            target_action.metadata, 
            source_action.metadata
        )
        
        success = db_manager.update_action(
            request.target_action_id, 
            {'metadata': merged_metadata}
        )
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to update target action")
        
        db_manager.update_action(source_action_id, {'status': ActionStatus.CLOSED})
        
        history_logger.log_action_merge(
            source_action_id=source_action_id,
            target_action_id=request.target_action_id,
            merge_reason="Manual merge by user",
            actor='user'
        )
        
        history_logger.log_action_closure(
            action_id=source_action_id,
            reason="Merged into another action",
            actor='user'
        )
        
        updated_target = db_manager.get_action_by_id(request.target_action_id)
        return {
            "message": "Actions merged successfully",
            "source_action_id": source_action_id,
            "target_action_id": request.target_action_id,
            "merged_action": updated_target
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error merging actions: {str(e)}")


@app.get("/actions/{action_id}/history")
async def get_action_history(action_id: int):
    try:
        action = db_manager.get_action_by_id(action_id)
        if not action:
            raise HTTPException(status_code=404, detail="Action not found")
        
        history = history_logger.get_action_history(action_id)
        operation_summary = history_logger.get_operation_summary(action_id)
        
        return {
            "action_id": action_id,
            "history": history,
            "summary": operation_summary
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving action history: {str(e)}")


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "database": "connected",
        "extraction_method": "rule-based"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)