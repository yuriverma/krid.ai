from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from enum import Enum


class TaskType(str, Enum):
    PAN_CARD = "pan_card"
    AADHAAR = "aadhaar"
    BANK_STATEMENT = "bank_statement"
    INCOME_PROOF = "income_proof"
    ADDRESS_PROOF = "address_proof"
    PHOTO = "photo"
    SIGNATURE = "signature"
    OTHER = "other"


class ActionStatus(str, Enum):
    OPEN = "open"
    CLOSED = "closed"
    TENTATIVE = "tentative"


class DeliverableType(str, Enum):
    PHOTO = "photo"
    PDF = "pdf"
    NUMBER = "number"
    TEXT = "text"
    URL = "url"
    ATTACHMENT = "attachment"


class OperationType(str, Enum):
    CREATE = "create"
    UPDATE = "update"
    CLOSE = "close"
    MERGE = "merge"


class ChatMessage(BaseModel):
    message_id: str = Field(..., description="Unique message identifier")
    sender: str = Field(..., description="Sender identifier (client/rm)")
    text: str = Field(..., description="Message text content")
    ts: datetime = Field(..., description="Message timestamp")


class ProcessChatRequest(BaseModel):
    client_id: str = Field(..., description="Client identifier")
    conversation_id: str = Field(..., description="Conversation identifier")
    messages: List[ChatMessage] = Field(..., description="List of messages to process")


class ProcessChatResponse(BaseModel):
    processed_messages: int = Field(..., description="Number of messages processed")
    created_actions: int = Field(..., description="Number of new actions created")
    updated_actions: int = Field(..., description="Number of existing actions updated")
    closed_actions: int = Field(..., description="Number of actions closed")
    tentative_actions: int = Field(..., description="Number of tentative actions created")
    summary: str = Field(..., description="Human-readable summary")


class GetActionsRequest(BaseModel):
    client_id: Optional[str] = Field(None, description="Filter by client ID")
    status: Optional[ActionStatus] = Field(None, description="Filter by status")
    limit: Optional[int] = Field(100, description="Maximum number of actions to return")


class CloseActionRequest(BaseModel):
    source_message_id: Optional[str] = Field(None, description="Message ID that triggered closure")
    reason: Optional[str] = Field(None, description="Reason for closing the action")


class MergeActionRequest(BaseModel):
    target_action_id: int = Field(..., description="ID of the action to merge into")


class Action(BaseModel):
    id: Optional[int] = Field(None, description="Action ID")
    client_id: str = Field(..., description="Client identifier")
    conversation_id: str = Field(..., description="Conversation identifier")
    task_type: TaskType = Field(..., description="Type of task")
    task_text: str = Field(..., description="Task description text")
    task_key: str = Field(..., description="Normalized task key for matching")
    owner: str = Field(..., description="Task owner (client/rm)")
    status: ActionStatus = Field(ActionStatus.OPEN, description="Action status")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    created_at: Optional[datetime] = Field(None, description="Creation timestamp")
    updated_at: Optional[datetime] = Field(None, description="Last update timestamp")


class ActionHistory(BaseModel):
    id: Optional[int] = Field(None, description="History entry ID")
    action_id: int = Field(..., description="Associated action ID")
    operation: OperationType = Field(..., description="Operation type")
    payload: Dict[str, Any] = Field(default_factory=dict, description="Operation payload")
    source_message_id: Optional[str] = Field(None, description="Source message ID")
    source_text: Optional[str] = Field(None, description="Source text snippet")
    actor: str = Field(..., description="Actor who performed the operation")
    created_at: Optional[datetime] = Field(None, description="Operation timestamp")


class Message(BaseModel):
    id: Optional[int] = Field(None, description="Message ID")
    message_id: str = Field(..., description="Unique message identifier")
    conversation_id: str = Field(..., description="Conversation identifier")
    sender: str = Field(..., description="Sender identifier")
    text: str = Field(..., description="Message text")
    received_at: datetime = Field(..., description="Message timestamp")
    processed: bool = Field(False, description="Whether message has been processed")


class ExtractedAction(BaseModel):
    task_text: str = Field(..., description="Extracted task text")
    task_type: TaskType = Field(..., description="Detected task type")
    owner: str = Field(..., description="Task owner")
    status_hint: Optional[str] = Field(None, description="Status hint from text")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Extracted metadata")
    deliverable_type: Optional[DeliverableType] = Field(None, description="Expected deliverable type")
    confidence: float = Field(1.0, description="Extraction confidence score")


class MatchResult(BaseModel):
    action_id: Optional[int] = Field(None, description="Matched action ID")
    confidence: float = Field(0.0, description="Match confidence score")
    match_type: str = Field("none", description="Type of match (exact/fuzzy/tentative/none)")
    reason: str = Field("", description="Match reasoning")


class ActionSummary(BaseModel):
    id: int
    client_id: str
    task_type: TaskType
    task_text: str
    owner: str
    status: ActionStatus
    metadata: Dict[str, Any]
    created_at: datetime
    updated_at: datetime
    latest_history: Optional[ActionHistory] = None