import json
from datetime import datetime
from models import ProcessChatRequest, ChatMessage, Message
from nlp import action_extractor
from matcher import action_matcher
from db import db_manager

def demo_action_extraction():
    print("=" * 60)
    print("ACTION EXTRACTION DEMO")
    print("=" * 60)
    
    messages = [
        "Please send your PAN card document",
        "My PAN number is ABCDE1234F",
        "Here is the document: https://example.com/pan.pdf",
        "Please provide your Aadhaar card photo"
    ]
    
    for i, text in enumerate(messages, 1):
        print(f"\nMessage {i}: '{text}'")
        actions = action_extractor.extract_actions(text, "rm" if i % 2 == 1 else "client")
        
        for j, action in enumerate(actions, 1):
            print(f"  Action {j}:")
            print(f"    Task Type: {action.task_type}")
            print(f"    Task Text: {action.task_text}")
            print(f"    Owner: {action.owner}")
            print(f"    Status Hint: {action.status_hint}")
            print(f"    Deliverable Type: {action.deliverable_type}")
            print(f"    Metadata: {action.metadata}")

def demo_action_matching():
    print("\n" + "=" * 60)
    print("ACTION PROCESSING & MATCHING")
    print("=" * 60)
    
    client_id = "demo_client"
    conversation_id = "demo_conv"
    
    print("\n1. RM requests PAN card:")
    text1 = "Please send your PAN card document"
    actions1 = action_extractor.extract_actions(text1, "rm")
    print(f"   Extracted: {len(actions1)} action(s)")
    
    stats1 = action_matcher.process_extracted_actions(
        actions1, client_id, conversation_id, "msg_001", text1
    )
    print(f"   Result: {stats1}")
    
    print("\n2. Client provides PAN number:")
    text2 = "My PAN number is ABCDE1234F"
    actions2 = action_extractor.extract_actions(text2, "client")
    print(f"   Extracted: {len(actions2)} action(s)")
    
    stats2 = action_matcher.process_extracted_actions(
        actions2, client_id, conversation_id, "msg_002", text2
    )
    print(f"   Result: {stats2}")
    
    print("\n3. RM requests PAN photo:")
    text3 = "Please send a photo of your PAN card"
    actions3 = action_extractor.extract_actions(text3, "rm")
    print(f"   Extracted: {len(actions3)} action(s)")
    
    stats3 = action_matcher.process_extracted_actions(
        actions3, client_id, conversation_id, "msg_003", text3
    )
    print(f"   Result: {stats3}")
    
    print("\nFinal actions in database:")
    actions = db_manager.get_actions(client_id=client_id)
    for action in actions:
        print(f"  ID: {action.id}, Type: {action.task_type}, Status: {action.status}")
        print(f"    Text: {action.task_text}")
        print(f"    Metadata: {action.metadata}")

def demo_api_usage():
    print("\n" + "=" * 60)
    print("API USAGE DEMO")
    print("=" * 60)
    
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
    
    print("Example API Request:")
    print(json.dumps(request_data, indent=2))
    
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
    
    print(f"\nProcessing Result: {total_stats}")
    
    actions = db_manager.get_actions(client_id=request.client_id)
    print(f"\nCreated {len(actions)} action(s):")
    for action in actions:
        print(f"  - {action.task_type}: {action.task_text} (Status: {action.status})")

def main():
    print("Action Tracker Service Demo")
    print("=" * 50)
    
    db_manager.init_database()
    
    demo_action_extraction()
    demo_action_matching()
    demo_api_usage()
    
    print("\n" + "=" * 50)
    print("Demo completed successfully!")
    print("\nTo start the FastAPI server, run:")
    print("  uvicorn main:app --reload")
    print("\nThen visit http://localhost:8000/docs for the API documentation")

if __name__ == "__main__":
    main()