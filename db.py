import sqlite3
import json
from datetime import datetime
from typing import List, Optional, Dict, Any
from contextlib import contextmanager
import os

from models import Action, ActionHistory, Message, ActionStatus, OperationType


class DatabaseManager:
    def __init__(self, db_path: str = "action_tracker.db"):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS actions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    client_id TEXT NOT NULL,
                    conversation_id TEXT NOT NULL,
                    task_type TEXT NOT NULL,
                    task_text TEXT NOT NULL,
                    task_key TEXT NOT NULL,
                    owner TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'open',
                    metadata TEXT NOT NULL DEFAULT '{}',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS actions_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    action_id INTEGER NOT NULL,
                    operation TEXT NOT NULL,
                    payload TEXT NOT NULL DEFAULT '{}',
                    source_message_id TEXT,
                    source_text TEXT,
                    actor TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (action_id) REFERENCES actions (id)
                )
            """)
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    message_id TEXT UNIQUE NOT NULL,
                    conversation_id TEXT NOT NULL,
                    sender TEXT NOT NULL,
                    text TEXT NOT NULL,
                    received_at TIMESTAMP NOT NULL,
                    processed BOOLEAN DEFAULT FALSE
                )
            """)
            
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_actions_client_id ON actions (client_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_actions_status ON actions (status)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_actions_task_key ON actions (task_key)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_actions_history_action_id ON actions_history (action_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_messages_message_id ON messages (message_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_messages_conversation_id ON messages (conversation_id)")
            
            conn.commit()
    
    @contextmanager
    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
    
    def save_message(self, message: Message) -> int:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("""
                    INSERT OR IGNORE INTO messages 
                    (message_id, conversation_id, sender, text, received_at, processed)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    message.message_id,
                    message.conversation_id,
                    message.sender,
                    message.text,
                    message.received_at,
                    message.processed
                ))
                conn.commit()
                return cursor.lastrowid
            except sqlite3.IntegrityError:
                cursor.execute("SELECT id FROM messages WHERE message_id = ?", (message.message_id,))
                result = cursor.fetchone()
                return result['id'] if result else None
    
    def mark_message_processed(self, message_id: str):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE messages SET processed = TRUE WHERE message_id = ?
            """, (message_id,))
            conn.commit()
    
    def get_unprocessed_messages(self, conversation_id: str) -> List[Message]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM messages 
                WHERE conversation_id = ? AND processed = FALSE
                ORDER BY received_at ASC
            """, (conversation_id,))
            
            messages = []
            for row in cursor.fetchall():
                messages.append(Message(
                    id=row['id'],
                    conversation_id=row['conversation_id'],
                    sender=row['sender'],
                    text=row['text'],
                    received_at=datetime.fromisoformat(row['received_at']),
                    processed=bool(row['processed'])
                ))
            return messages
    
    def create_action(self, action: Action) -> int:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO actions 
                (client_id, conversation_id, task_type, task_text, task_key, 
                 owner, status, metadata, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                action.client_id,
                action.conversation_id,
                action.task_type.value,
                action.task_text,
                action.task_key,
                action.owner,
                action.status.value,
                json.dumps(action.metadata),
                action.created_at or datetime.now(),
                action.updated_at or datetime.now()
            ))
            conn.commit()
            return cursor.lastrowid
    
    def get_action_by_id(self, action_id: int) -> Optional[Action]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM actions WHERE id = ?", (action_id,))
            row = cursor.fetchone()
            
            if row:
                return Action(
                    id=row['id'],
                    client_id=row['client_id'],
                    conversation_id=row['conversation_id'],
                    task_type=row['task_type'],
                    task_text=row['task_text'],
                    task_key=row['task_key'],
                    owner=row['owner'],
                    status=ActionStatus(row['status']),
                    metadata=json.loads(row['metadata']),
                    created_at=datetime.fromisoformat(row['created_at']),
                    updated_at=datetime.fromisoformat(row['updated_at'])
                )
            return None
    
    def get_open_actions(self, client_id: str) -> List[Action]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM actions 
                WHERE client_id = ? AND status IN ('open', 'tentative')
                ORDER BY created_at DESC
            """, (client_id,))
            
            actions = []
            for row in cursor.fetchall():
                actions.append(Action(
                    id=row['id'],
                    client_id=row['client_id'],
                    conversation_id=row['conversation_id'],
                    task_type=row['task_type'],
                    task_text=row['task_text'],
                    task_key=row['task_key'],
                    owner=row['owner'],
                    status=ActionStatus(row['status']),
                    metadata=json.loads(row['metadata']),
                    created_at=datetime.fromisoformat(row['created_at']),
                    updated_at=datetime.fromisoformat(row['updated_at'])
                ))
            return actions
    
    def update_action(self, action_id: int, updates: Dict[str, Any]) -> bool:
        if not updates:
            return False
            
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            set_clauses = []
            values = []
            
            for key, value in updates.items():
                if key in ['task_text', 'task_key', 'owner', 'status']:
                    set_clauses.append(f"{key} = ?")
                    values.append(value.value if hasattr(value, 'value') else value)
                elif key == 'metadata':
                    set_clauses.append("metadata = ?")
                    values.append(json.dumps(value))
            
            if not set_clauses:
                return False
            
            set_clauses.append("updated_at = ?")
            values.append(datetime.now())
            values.append(action_id)
            
            query = f"UPDATE actions SET {', '.join(set_clauses)} WHERE id = ?"
            cursor.execute(query, values)
            conn.commit()
            
            return cursor.rowcount > 0
    
    def get_actions(self, client_id: Optional[str] = None, 
                   status: Optional[ActionStatus] = None, 
                   limit: int = 100) -> List[Action]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            where_clauses = []
            values = []
            
            if client_id:
                where_clauses.append("client_id = ?")
                values.append(client_id)
            
            if status:
                where_clauses.append("status = ?")
                values.append(status.value)
            
            where_clause = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""
            values.append(limit)
            
            query = f"""
                SELECT * FROM actions 
                {where_clause}
                ORDER BY updated_at DESC 
                LIMIT ?
            """
            
            cursor.execute(query, values)
            
            actions = []
            for row in cursor.fetchall():
                actions.append(Action(
                    id=row['id'],
                    client_id=row['client_id'],
                    conversation_id=row['conversation_id'],
                    task_type=row['task_type'],
                    task_text=row['task_text'],
                    task_key=row['task_key'],
                    owner=row['owner'],
                    status=ActionStatus(row['status']),
                    metadata=json.loads(row['metadata']),
                    created_at=datetime.fromisoformat(row['created_at']),
                    updated_at=datetime.fromisoformat(row['updated_at'])
                ))
            return actions
    
    def add_action_history(self, history: ActionHistory) -> int:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO actions_history 
                (action_id, operation, payload, source_message_id, source_text, actor, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                history.action_id,
                history.operation.value,
                json.dumps(history.payload),
                history.source_message_id,
                history.source_text,
                history.actor,
                history.created_at or datetime.now()
            ))
            conn.commit()
            return cursor.lastrowid
    
    def get_action_history(self, action_id: int) -> List[ActionHistory]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM actions_history 
                WHERE action_id = ? 
                ORDER BY created_at DESC
            """, (action_id,))
            
            history = []
            for row in cursor.fetchall():
                history.append(ActionHistory(
                    id=row['id'],
                    action_id=row['action_id'],
                    operation=OperationType(row['operation']),
                    payload=json.loads(row['payload']),
                    source_message_id=row['source_message_id'],
                    source_text=row['source_text'],
                    actor=row['actor'],
                    created_at=datetime.fromisoformat(row['created_at'])
                ))
            return history
    
    def get_latest_action_history(self, action_id: int) -> Optional[ActionHistory]:
        history = self.get_action_history(action_id)
        return history[0] if history else None


db_manager = DatabaseManager()