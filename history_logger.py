from datetime import datetime
from typing import Dict, Any, Optional, List
from models import OperationType, ActionHistory
from db import db_manager


class HistoryLogger:
    def __init__(self):
        pass
    
    def log_action_operation(self, action_id: int, operation: OperationType,
                           payload: Dict[str, Any], source_message_id: Optional[str] = None,
                           source_text: Optional[str] = None, actor: str = 'system') -> int:
        history_entry = ActionHistory(
            action_id=action_id,
            operation=operation,
            payload=payload,
            source_message_id=source_message_id,
            source_text=source_text,
            actor=actor,
            created_at=datetime.now()
        )
        
        return db_manager.add_action_history(history_entry)
    
    def log_action_creation(self, action_id: int, action_data: Dict[str, Any],
                          source_message_id: Optional[str] = None,
                          source_text: Optional[str] = None) -> int:
        return self.log_action_operation(
            action_id=action_id,
            operation=OperationType.CREATE,
            payload={
                'action_data': action_data,
                'created_at': datetime.now().isoformat()
            },
            source_message_id=source_message_id,
            source_text=source_text,
            actor='system'
        )
    
    def log_action_update(self, action_id: int, updates: Dict[str, Any],
                        source_message_id: Optional[str] = None,
                        source_text: Optional[str] = None,
                        actor: str = 'system') -> int:
        return self.log_action_operation(
            action_id=action_id,
            operation=OperationType.UPDATE,
            payload={
                'updates': updates,
                'updated_at': datetime.now().isoformat()
            },
            source_message_id=source_message_id,
            source_text=source_text,
            actor=actor
        )
    
    def log_action_closure(self, action_id: int, reason: Optional[str] = None,
                         source_message_id: Optional[str] = None,
                         source_text: Optional[str] = None,
                         actor: str = 'system') -> int:
        return self.log_action_operation(
            action_id=action_id,
            operation=OperationType.CLOSE,
            payload={
                'reason': reason,
                'closed_at': datetime.now().isoformat()
            },
            source_message_id=source_message_id,
            source_text=source_text,
            actor=actor
        )
    
    def log_action_merge(self, source_action_id: int, target_action_id: int,
                        merge_reason: str, actor: str = 'system') -> int:
        return self.log_action_operation(
            action_id=target_action_id,
            operation=OperationType.MERGE,
            payload={
                'source_action_id': source_action_id,
                'merge_reason': merge_reason,
                'merged_at': datetime.now().isoformat()
            },
            actor=actor
        )
    
    def get_action_history(self, action_id: int) -> List[ActionHistory]:
        return db_manager.get_action_history(action_id)
    
    def get_latest_action_history(self, action_id: int) -> Optional[ActionHistory]:
        return db_manager.get_latest_action_history(action_id)
    
    def get_operation_summary(self, action_id: int) -> Dict[str, Any]:
        history = self.get_action_history(action_id)
        
        summary = {
            'total_operations': len(history),
            'operation_counts': {},
            'first_operation': None,
            'last_operation': None,
            'source_messages': set(),
            'actors': set()
        }
        
        for entry in history:
            op_type = entry.operation.value
            summary['operation_counts'][op_type] = summary['operation_counts'].get(op_type, 0) + 1
            
            if entry.source_message_id:
                summary['source_messages'].add(entry.source_message_id)
            
            summary['actors'].add(entry.actor)
            
            if not summary['first_operation']:
                summary['first_operation'] = entry
            summary['last_operation'] = entry
        
        summary['source_messages'] = list(summary['source_messages'])
        summary['actors'] = list(summary['actors'])
        
        return summary


history_logger = HistoryLogger()


def log_action_operation(action_id: int, operation: OperationType,
                        payload: Dict[str, Any], source_message_id: Optional[str] = None,
                        source_text: Optional[str] = None, actor: str = 'system') -> int:
    return history_logger.log_action_operation(
        action_id, operation, payload, source_message_id, source_text, actor
    )


def log_action_creation(action_id: int, action_data: Dict[str, Any],
                       source_message_id: Optional[str] = None,
                       source_text: Optional[str] = None) -> int:
    return history_logger.log_action_creation(
        action_id, action_data, source_message_id, source_text
    )


def log_action_update(action_id: int, updates: Dict[str, Any],
                     source_message_id: Optional[str] = None,
                     source_text: Optional[str] = None,
                     actor: str = 'system') -> int:
    return history_logger.log_action_update(
        action_id, updates, source_message_id, source_text, actor
    )


def log_action_closure(action_id: int, reason: Optional[str] = None,
                      source_message_id: Optional[str] = None,
                      source_text: Optional[str] = None,
                      actor: str = 'system') -> int:
    return history_logger.log_action_closure(
        action_id, reason, source_message_id, source_text, actor
    )


def log_action_merge(source_action_id: int, target_action_id: int,
                    merge_reason: str, actor: str = 'system') -> int:
    return history_logger.log_action_merge(
        source_action_id, target_action_id, merge_reason, actor
    )