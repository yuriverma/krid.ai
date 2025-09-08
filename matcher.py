import re
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from difflib import SequenceMatcher
import json

from models import (
    ExtractedAction, Action, ActionStatus, MatchResult, 
    TaskType, DeliverableType
)
from db import db_manager
from nlp import action_extractor


class ActionMatcher:
    def __init__(self):
        self.exact_match_threshold = 1.0
        self.high_confidence_threshold = 0.85
        self.tentative_threshold = 0.6
        self.low_confidence_threshold = 0.6
    
    def process_extracted_actions(self, extracted_actions: List[ExtractedAction],
                                client_id: str, conversation_id: str,
                                source_message_id: str, source_text: str) -> Dict[str, int]:
        stats = {
            'created': 0,
            'updated': 0,
            'closed': 0,
            'tentative': 0
        }
        
        existing_actions = db_manager.get_open_actions(client_id)
        
        for extracted_action in extracted_actions:
            task_key = self._compute_task_key(extracted_action)
            match_result = self._find_best_match(extracted_action, existing_actions, task_key)
            
            if match_result.match_type == 'exact':
                self._update_existing_action(
                    match_result.action_id, extracted_action, 
                    source_message_id, source_text, stats
                )
            elif match_result.match_type == 'fuzzy' and match_result.confidence >= self.high_confidence_threshold:
                self._update_existing_action(
                    match_result.action_id, extracted_action,
                    source_message_id, source_text, stats
                )
            elif match_result.match_type == 'fuzzy' and match_result.confidence >= self.tentative_threshold:
                self._create_tentative_action(
                    extracted_action, client_id, conversation_id,
                    source_message_id, source_text, task_key, stats
                )
            else:
                self._create_new_action(
                    extracted_action, client_id, conversation_id,
                    source_message_id, source_text, task_key, stats
                )
        
        return stats
    
    def _compute_task_key(self, extracted_action: ExtractedAction) -> str:
        base_key = extracted_action.task_type.value
        entities = []
        
        if 'pan_number' in extracted_action.metadata:
            entities.append(f"pan_{extracted_action.metadata['pan_number']}")
        
        if extracted_action.deliverable_type:
            entities.append(extracted_action.deliverable_type.value)
        
        entities.append(extracted_action.owner)
        
        if entities:
            return f"{base_key}_{'_'.join(entities)}"
        else:
            return base_key
    
    def _find_best_match(self, extracted_action: ExtractedAction,
                        existing_actions: List[Action], task_key: str) -> MatchResult:
        best_match = MatchResult()
        
        for existing_action in existing_actions:
            if existing_action.task_key == task_key:
                return MatchResult(
                    action_id=existing_action.id,
                    confidence=1.0,
                    match_type='exact',
                    reason='Exact task key match'
                )
            
            fuzzy_score = self._compute_fuzzy_score(extracted_action, existing_action)
            
            if fuzzy_score > best_match.confidence:
                best_match = MatchResult(
                    action_id=existing_action.id,
                    confidence=fuzzy_score,
                    match_type='fuzzy',
                    reason=f'Fuzzy match: {fuzzy_score:.2f}'
                )
        
        return best_match
    
    def _compute_fuzzy_score(self, extracted_action: ExtractedAction,
                           existing_action: Action) -> float:
        score = 0.0
        
        if extracted_action.task_type.value == existing_action.task_type:
            score += 0.4
        
        existing_metadata = existing_action.metadata if isinstance(existing_action.metadata, dict) else json.loads(existing_action.metadata)
        entity_score = self._compute_entity_match_score(
            extracted_action.metadata, 
            existing_metadata
        )
        score += entity_score * 0.3
        
        text_similarity = SequenceMatcher(
            None, 
            extracted_action.task_text.lower(),
            existing_action.task_text.lower()
        ).ratio()
        score += text_similarity * 0.2
        
        if extracted_action.owner == existing_action.owner:
            score += 0.1
        
        return min(score, 1.0)
    
    def _compute_entity_match_score(self, new_metadata: Dict[str, Any],
                                  existing_metadata: Dict[str, Any]) -> float:
        if not new_metadata and not existing_metadata:
            return 1.0
        
        if not new_metadata or not existing_metadata:
            return 0.0
        
        matches = 0
        total_entities = 0
        
        if 'pan_number' in new_metadata and 'pan_number' in existing_metadata:
            total_entities += 1
            if new_metadata['pan_number'] == existing_metadata['pan_number']:
                matches += 1
        
        new_urls = set(new_metadata.get('urls', []))
        existing_urls = set(existing_metadata.get('urls', []))
        if new_urls or existing_urls:
            total_entities += 1
            if new_urls & existing_urls:
                matches += 1
        
        new_deliverable = new_metadata.get('deliverable_type')
        existing_deliverable = existing_metadata.get('deliverable_type')
        if new_deliverable or existing_deliverable:
            total_entities += 1
            if new_deliverable == existing_deliverable:
                matches += 1
        
        return matches / total_entities if total_entities > 0 else 0.0
    
    def _update_existing_action(self, action_id: int, extracted_action: ExtractedAction,
                              source_message_id: str, source_text: str, stats: Dict[str, int]):
        existing_action = db_manager.get_action_by_id(action_id)
        if not existing_action:
            return
        
        if extracted_action.status_hint == 'closed':
            updates = {'status': ActionStatus.CLOSED}
            operation = 'close'
            stats['closed'] += 1
        elif extracted_action.status_hint == 'modify':
            updates = self._merge_metadata(existing_action.metadata, extracted_action.metadata)
            operation = 'update'
            stats['updated'] += 1
        else:
            updates = self._merge_metadata(existing_action.metadata, extracted_action.metadata)
            operation = 'update'
            stats['updated'] += 1
        
        if updates:
            db_manager.update_action(action_id, updates)
        
        from history_logger import log_action_operation
        log_action_operation(
            action_id=action_id,
            operation=operation,
            payload=updates,
            source_message_id=source_message_id,
            source_text=source_text[:200],
            actor='system'
        )
    
    def _create_tentative_action(self, extracted_action: ExtractedAction,
                               client_id: str, conversation_id: str,
                               source_message_id: str, source_text: str,
                               task_key: str, stats: Dict[str, int]):
        action = Action(
            client_id=client_id,
            conversation_id=conversation_id,
            task_type=extracted_action.task_type,
            task_text=extracted_action.task_text,
            task_key=task_key,
            owner=extracted_action.owner,
            status=ActionStatus.TENTATIVE,
            metadata=extracted_action.metadata,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        
        action_id = db_manager.create_action(action)
        stats['tentative'] += 1
        
        from history_logger import log_action_operation
        log_action_operation(
            action_id=action_id,
            operation='create',
            payload={'status': 'tentative', 'reason': 'Low confidence match'},
            source_message_id=source_message_id,
            source_text=source_text[:200],
            actor='system'
        )
    
    def _create_new_action(self, extracted_action: ExtractedAction,
                         client_id: str, conversation_id: str,
                         source_message_id: str, source_text: str,
                         task_key: str, stats: Dict[str, int]):
        action = Action(
            client_id=client_id,
            conversation_id=conversation_id,
            task_type=extracted_action.task_type,
            task_text=extracted_action.task_text,
            task_key=task_key,
            owner=extracted_action.owner,
            status=ActionStatus.OPEN,
            metadata=extracted_action.metadata,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        
        action_id = db_manager.create_action(action)
        stats['created'] += 1
        
        from history_logger import log_action_operation
        log_action_operation(
            action_id=action_id,
            operation='create',
            payload={'status': 'open'},
            source_message_id=source_message_id,
            source_text=source_text[:200],
            actor='system'
        )
    
    def _merge_metadata(self, existing_metadata: Dict[str, Any],
                       new_metadata: Dict[str, Any]) -> Dict[str, Any]:
        merged = existing_metadata.copy()
        
        for key, value in new_metadata.items():
            if key not in merged:
                merged[key] = value
            elif isinstance(value, list) and isinstance(merged[key], list):
                merged[key] = list(set(merged[key] + value))
            elif key in ['pan_number', 'deliverable_type']:
                merged[key] = value
            elif isinstance(value, dict) and isinstance(merged[key], dict):
                merged[key] = {**merged[key], **value}
            else:
                if len(str(value)) > len(str(merged[key])):
                    merged[key] = value
        
        return merged


action_matcher = ActionMatcher()