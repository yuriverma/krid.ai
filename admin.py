import json
from datetime import datetime
from typing import List, Optional
from db import db_manager
from models import Action, ActionStatus, ActionHistory
from history_logger import history_logger


class ActionTrackerAdmin:
    def __init__(self):
        self.db = db_manager
    
    def show_dashboard(self):
        print("=" * 60)
        print("ACTION TRACKER - ADMIN DASHBOARD")
        print("=" * 60)
        
        all_actions = self.db.get_actions(limit=1000)
        
        stats = {
            'total_actions': len(all_actions),
            'open_actions': len([a for a in all_actions if a.status == ActionStatus.OPEN]),
            'closed_actions': len([a for a in all_actions if a.status == ActionStatus.CLOSED]),
            'tentative_actions': len([a for a in all_actions if a.status == ActionStatus.TENTATIVE]),
        }
        
        print(f"STATISTICS:")
        print(f"   Total Actions: {stats['total_actions']}")
        print(f"   Open Actions: {stats['open_actions']}")
        print(f"   Closed Actions: {stats['closed_actions']}")
        print(f"   Tentative Actions: {stats['tentative_actions']}")
        
        recent_actions = sorted(all_actions, key=lambda x: x.updated_at, reverse=True)[:5]
        print(f"\nRECENT ACTIONS:")
        for action in recent_actions:
            status_emoji = "OPEN" if action.status == ActionStatus.OPEN else "CLOSED" if action.status == ActionStatus.CLOSED else "TENTATIVE"
            print(f"   {status_emoji} ID:{action.id} | {action.task_type.value.upper()} | {action.task_text[:50]}...")
        
        print("\n" + "=" * 60)
    
    def list_actions(self, status: Optional[ActionStatus] = None, client_id: Optional[str] = None):
        actions = self.db.get_actions(status=status, client_id=client_id, limit=50)
        
        if not actions:
            print("No actions found.")
            return
        
        print(f"\nACTIONS ({len(actions)} found):")
        print("-" * 80)
        print(f"{'ID':<4} {'Status':<10} {'Type':<12} {'Client':<15} {'Task':<30}")
        print("-" * 80)
        
        for action in actions:
            status_emoji = "OPEN" if action.status == ActionStatus.OPEN else "CLOSED" if action.status == ActionStatus.CLOSED else "TENTATIVE"
            print(f"{action.id:<4} {status_emoji:<9} {action.task_type.value:<12} {action.client_id:<15} {action.task_text[:30]:<30}")
    
    def show_action_details(self, action_id: int):
        action = self.db.get_action_by_id(action_id)
        if not action:
            print(f"Action with ID {action_id} not found.")
            return
        
        print(f"\nACTION DETAILS - ID: {action_id}")
        print("=" * 50)
        print(f"Task Type: {action.task_type.value}")
        print(f"Task Text: {action.task_text}")
        print(f"Client ID: {action.client_id}")
        print(f"Conversation ID: {action.conversation_id}")
        print(f"Owner: {action.owner}")
        print(f"Status: {action.status.value}")
        print(f"Created: {action.created_at}")
        print(f"Updated: {action.updated_at}")
        
        if action.metadata:
            print(f"Metadata: {json.dumps(action.metadata, indent=2)}")
        
        history = history_logger.get_action_history(action_id)
        if history:
            print(f"\nHISTORY ({len(history)} entries):")
            for entry in history:
                print(f"   {entry.created_at} | {entry.operation.value} | {entry.actor}")
                if entry.source_text:
                    print(f"      Source: {entry.source_text[:100]}...")
    
    def close_action(self, action_id: int, reason: str = "Closed by admin"):
        action = self.db.get_action_by_id(action_id)
        if not action:
            print(f"Action with ID {action_id} not found.")
            return
        
        if action.status == ActionStatus.CLOSED:
            print(f"Action {action_id} is already closed.")
            return
        
        success = self.db.update_action(action_id, {'status': ActionStatus.CLOSED})
        if success:
            history_logger.log_action_closure(
                action_id=action_id,
                reason=reason,
                actor='admin'
            )
            print(f"Action {action_id} closed successfully.")
        else:
            print(f"Failed to close action {action_id}.")
    
    def merge_actions(self, source_id: int, target_id: int, reason: str = "Merged by admin"):
        source_action = self.db.get_action_by_id(source_id)
        target_action = self.db.get_action_by_id(target_id)
        
        if not source_action:
            print(f"Source action {source_id} not found.")
            return
        if not target_action:
            print(f"Target action {target_id} not found.")
            return
        
        if source_action.client_id != target_action.client_id:
            print(f"Cannot merge actions from different clients.")
            return
        
        from matcher import action_matcher
        merged_metadata = action_matcher._merge_metadata(
            target_action.metadata, 
            source_action.metadata
        )
        
        success = self.db.update_action(target_id, {'metadata': merged_metadata})
        if success:
            self.db.update_action(source_id, {'status': ActionStatus.CLOSED})
            
            history_logger.log_action_merge(
                source_action_id=source_id,
                target_action_id=target_id,
                merge_reason=reason,
                actor='admin'
            )
            
            history_logger.log_action_closure(
                action_id=source_id,
                reason="Merged into another action",
                actor='admin'
            )
            
            print(f"Actions merged successfully: {source_id} -> {target_id}")
        else:
            print(f"Failed to merge actions.")
    
    def show_tentative_actions(self):
        tentative_actions = self.db.get_actions(status=ActionStatus.TENTATIVE, limit=100)
        
        if not tentative_actions:
            print("No tentative actions found.")
            return
        
        print(f"\nTENTATIVE ACTIONS ({len(tentative_actions)} found):")
        print("These actions need manual review due to low confidence matching.")
        print("-" * 80)
        
        for action in tentative_actions:
            print(f"ID: {action.id} | {action.task_type.value} | {action.task_text}")
            print(f"   Client: {action.client_id} | Created: {action.created_at}")
            print()
    
    def show_client_actions(self, client_id: str):
        actions = self.db.get_actions(client_id=client_id, limit=100)
        
        if not actions:
            print(f"No actions found for client: {client_id}")
            return
        
        print(f"\nACTIONS FOR CLIENT: {client_id}")
        print(f"Total: {len(actions)} actions")
        print("-" * 60)
        
        for action in actions:
            status_emoji = "OPEN" if action.status == ActionStatus.OPEN else "CLOSED" if action.status == ActionStatus.CLOSED else "TENTATIVE"
            print(f"{status_emoji} ID:{action.id} | {action.task_type.value} | {action.task_text}")
    
    def interactive_menu(self):
        while True:
            print("\n" + "=" * 50)
            print("ACTION TRACKER - ADMIN MENU")
            print("=" * 50)
            print("1. Show Dashboard")
            print("2. List All Actions")
            print("3. List Open Actions")
            print("4. List Tentative Actions")
            print("5. Show Action Details")
            print("6. Close Action")
            print("7. Merge Actions")
            print("8. Show Client Actions")
            print("9. Exit")
            print("-" * 50)
            
            choice = input("Enter your choice (1-9): ").strip()
            
            if choice == "1":
                self.show_dashboard()
            elif choice == "2":
                self.list_actions()
            elif choice == "3":
                self.list_actions(status=ActionStatus.OPEN)
            elif choice == "4":
                self.show_tentative_actions()
            elif choice == "5":
                try:
                    action_id = int(input("Enter action ID: "))
                    self.show_action_details(action_id)
                except ValueError:
                    print("Invalid action ID.")
            elif choice == "6":
                try:
                    action_id = int(input("Enter action ID to close: "))
                    reason = input("Enter reason (optional): ").strip() or "Closed by admin"
                    self.close_action(action_id, reason)
                except ValueError:
                    print("Invalid action ID.")
            elif choice == "7":
                try:
                    source_id = int(input("Enter source action ID: "))
                    target_id = int(input("Enter target action ID: "))
                    reason = input("Enter reason (optional): ").strip() or "Merged by admin"
                    self.merge_actions(source_id, target_id, reason)
                except ValueError:
                    print("Invalid action ID.")
            elif choice == "8":
                client_id = input("Enter client ID: ").strip()
                if client_id:
                    self.show_client_actions(client_id)
            elif choice == "9":
                print("Goodbye!")
                break
            else:
                print("Invalid choice. Please try again.")


def main():
    admin = ActionTrackerAdmin()
    
    print("Action Tracker Admin Interface")
    print("Initializing database connection...")
    
    admin.show_dashboard()
    admin.interactive_menu()


if __name__ == "__main__":
    main()