import json
import time
from datetime import datetime
from models import ProcessChatRequest, ChatMessage, Message
from nlp import action_extractor
from matcher import action_matcher
from db import db_manager

def print_header(title):
    print("\n" + "=" * 60)
    print(f"{title}")
    print("=" * 60)

def print_step(step_num, description):
    print(f"\nSTEP {step_num}: {description}")
    print("-" * 40)

def demo_action_extraction():
    print_header("ACTION EXTRACTION DEMO")
    
    print_step(1, "RM requests PAN card document")
    text1 = "Please send your PAN card document"
    print(f"Input: '{text1}'")
    
    actions1 = action_extractor.extract_actions(text1, "rm")
    print(f"Extracted {len(actions1)} action(s):")
    for action in actions1:
        print(f"   Task: {action.task_text}")
        print(f"   Type: {action.task_type.value}")
        print(f"   Owner: {action.owner}")
        print(f"   Deliverable: {action.deliverable_type.value if action.deliverable_type else 'None'}")
    
    time.sleep(2)
    
    print_step(2, "Client provides PAN number")
    text2 = "My PAN number is ABCDE1234F"
    print(f"Input: '{text2}'")
    
    actions2 = action_extractor.extract_actions(text2, "client")
    print(f"Extracted {len(actions2)} action(s):")
    for action in actions2:
        print(f"   Task: {action.task_text}")
        print(f"   Status: {action.status_hint}")
        print(f"   PAN Number: {action.metadata.get('pan_number', 'None')}")
    
    time.sleep(2)
    
    print_step(3, "Client provides document URL")
    text3 = "Here is the document: https://example.com/pan.pdf"
    print(f"Input: '{text3}'")
    
    actions3 = action_extractor.extract_actions(text3, "client")
    print(f"Extracted {len(actions3)} action(s):")
    for action in actions3:
        print(f"   Task: {action.task_text}")
        print(f"   Status: {action.status_hint}")
        print(f"   URL: {action.metadata.get('urls', ['None'])[0]}")
        print(f"   Deliverable: {action.deliverable_type.value if action.deliverable_type else 'None'}")

def demo_action_processing():
    print_header("ACTION PROCESSING & MATCHING")
    
    client_id = "demo_client"
    conversation_id = "demo_conv"
    
    print("Clearing previous demo data...")
    
    print_step(1, "Processing RM request for PAN card")
    text1 = "Please send your PAN card document"
    actions1 = action_extractor.extract_actions(text1, "rm")
    stats1 = action_matcher.process_extracted_actions(
        actions1, client_id, conversation_id, "msg_001", text1
    )
    print(f"Result: {stats1}")
    
    time.sleep(1)
    
    print_step(2, "Processing client response with PAN number")
    text2 = "My PAN number is ABCDE1234F"
    actions2 = action_extractor.extract_actions(text2, "client")
    stats2 = action_matcher.process_extracted_actions(
        actions2, client_id, conversation_id, "msg_002", text2
    )
    print(f"Result: {stats2}")
    
    time.sleep(1)
    
    print_step(3, "Processing RM request for PAN photo")
    text3 = "Please send a photo of your PAN card"
    actions3 = action_extractor.extract_actions(text3, "rm")
    stats3 = action_matcher.process_extracted_actions(
        actions3, client_id, conversation_id, "msg_003", text3
    )
    print(f"Result: {stats3}")
    
    print_step(4, "Final Actions in Database")
    actions = db_manager.get_actions(client_id=client_id)
    print(f"Total actions created: {len(actions)}")
    for action in actions:
        status_emoji = "OPEN" if action.status.value == "open" else "CLOSED" if action.status.value == "closed" else "TENTATIVE"
        print(f"   {status_emoji} ID:{action.id} | {action.task_type.value} | {action.status.value}")

def demo_api_usage():
    print_header("API USAGE DEMO")
    
    print_step(1, "Example API Request")
    request_data = {
        "client_id": "api_demo_client",
        "conversation_id": "api_demo_conv",
        "messages": [
            {
                "message_id": "api_msg_001",
                "sender": "rm",
                "text": "Please provide your PAN card document",
                "ts": datetime.now().isoformat()
            },
            {
                "message_id": "api_msg_002", 
                "sender": "client",
                "text": "Here is my PAN card: ABCDE1234F",
                "ts": datetime.now().isoformat()
            }
        ]
    }
    
    print("API Request JSON:")
    print(json.dumps(request_data, indent=2))
    
    print_step(2, "Processing API Request")
    request = ProcessChatRequest(**request_data)
    
    total_stats = {'created': 0, 'updated': 0, 'closed': 0, 'tentative': 0}
    
    for chat_message in request.messages:
        message = Message(
            message_id=chat_message.message_id,
            conversation_id=request.conversation_id,
            sender=chat_message.sender,
            text=chat_message.text,
            received_at=chat_message.ts,
            processed=False
        )
        db_manager.save_message(message)
        
        actions = action_extractor.extract_actions(message.text, message.sender)
        if actions:
            stats = action_matcher.process_extracted_actions(
                actions, request.client_id, request.conversation_id,
                message.message_id, message.text
            )
            for key, value in stats.items():
                total_stats[key] += value
        
        db_manager.mark_message_processed(message.message_id)
    
    print(f"Processing Result: {total_stats}")
    
    actions = db_manager.get_actions(client_id=request.client_id)
    print(f"Created {len(actions)} action(s) in database")

def main():
    print("This demo shows the core functionality of the Action Tracker service.")
    
    db_manager.init_database()
    
    demo_action_extraction()
    time.sleep(3)
    
    demo_action_processing()
    time.sleep(3)
    
    demo_api_usage()
    
if __name__ == "__main__":
    main()