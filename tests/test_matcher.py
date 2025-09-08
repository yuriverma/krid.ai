import unittest
import tempfile
import os
import json
from datetime import datetime
from unittest.mock import patch, MagicMock

import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import (
    ExtractedAction, Action, ActionStatus, TaskType, DeliverableType,
    OperationType, ActionHistory
)
from nlp import RuleBasedExtractor
from matcher import ActionMatcher
from db import DatabaseManager


class TestRuleBasedExtractor(unittest.TestCase):
    def setUp(self):
        self.extractor = RuleBasedExtractor()
    
    def test_pan_card_extraction(self):
        text = "Please send your PAN card document"
        actions = self.extractor.extract_actions(text, "rm")
        
        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0].task_type, TaskType.PAN_CARD)
        self.assertEqual(actions[0].owner, "client")
        self.assertIn("PAN card", actions[0].task_text)
    
    def test_pan_number_extraction(self):
        text = "My PAN number is ABCDE1234F"
        actions = self.extractor.extract_actions(text, "client")
        
        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0].task_type, TaskType.PAN_CARD)
        self.assertEqual(actions[0].metadata['pan_number'], 'ABCDE1234F')
    
    def test_completion_status_hint(self):
        text = "I have received the PAN card document"
        actions = self.extractor.extract_actions(text, "rm")
        
        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0].status_hint, 'closed')
    
    def test_modification_status_hint(self):
        text = "Please update the PAN card with new number"
        actions = self.extractor.extract_actions(text, "rm")
        
        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0].status_hint, 'modify')
    
    def test_url_extraction(self):
        text = "Please upload the document at https://example.com/upload"
        actions = self.extractor.extract_actions(text, "rm")
        
        self.assertEqual(len(actions), 1)
        self.assertIn('urls', actions[0].metadata)
        self.assertIn('https://example.com/upload', actions[0].metadata['urls'])
        self.assertEqual(actions[0].deliverable_type, DeliverableType.URL)
    
    def test_deliverable_type_detection(self):
        text = "Please send a photo of your PAN card"
        actions = self.extractor.extract_actions(text, "rm")
        self.assertEqual(actions[0].deliverable_type, DeliverableType.PHOTO)
        
        text = "Please upload the PDF document"
        actions = self.extractor.extract_actions(text, "rm")
        self.assertEqual(actions[0].deliverable_type, DeliverableType.PDF)
        
        text = "Please provide your PAN number"
        actions = self.extractor.extract_actions(text, "rm")
        self.assertEqual(actions[0].deliverable_type, DeliverableType.NUMBER)
    
    def test_multiple_task_types(self):
        text = "Please send PAN card and Aadhaar card documents"
        actions = self.extractor.extract_actions(text, "rm")
        
        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0].task_type, TaskType.PAN_CARD)
    
    def test_no_action_extraction(self):
        text = "Hello, how are you today?"
        actions = self.extractor.extract_actions(text, "client")
        
        self.assertEqual(len(actions), 0)


class TestActionMatcher(unittest.TestCase):
    def setUp(self):
        self.matcher = ActionMatcher()
        self.temp_db = tempfile.NamedTemporaryFile(delete=False)
        self.temp_db.close()
        
        self.db_manager = DatabaseManager(self.temp_db.name)
        self.db_manager.init_database()
    
    def tearDown(self):
        os.unlink(self.temp_db.name)
    
    def test_task_key_computation(self):
        extracted_action = ExtractedAction(
            task_text="Provide PAN card",
            task_type=TaskType.PAN_CARD,
            owner="client",
            metadata={'pan_number': 'ABCDE1234F'},
            deliverable_type=DeliverableType.PHOTO
        )
        
        task_key = self.matcher._compute_task_key(extracted_action)
        expected_key = "pan_card_pan_ABCDE1234F_photo_client"
        self.assertEqual(task_key, expected_key)
    
    def test_exact_match(self):
        existing_action = Action(
            id=1,
            client_id="test_client",
            conversation_id="test_conv",
            task_type=TaskType.PAN_CARD,
            task_text="Provide PAN card",
            task_key="pan_card_pan_ABCDE1234F_photo_client",
            owner="client",
            status=ActionStatus.OPEN,
            metadata={'pan_number': 'ABCDE1234F'},
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        
        extracted_action = ExtractedAction(
            task_text="Provide PAN card",
            task_type=TaskType.PAN_CARD,
            owner="client",
            metadata={'pan_number': 'ABCDE1234F'},
            deliverable_type=DeliverableType.PHOTO
        )
        
        match_result = self.matcher._find_best_match(
            extracted_action, [existing_action], 
            self.matcher._compute_task_key(extracted_action)
        )
        
        self.assertEqual(match_result.match_type, 'exact')
        self.assertEqual(match_result.confidence, 1.0)
        self.assertEqual(match_result.action_id, 1)
    
    def test_fuzzy_match(self):
        existing_action = Action(
            id=1,
            client_id="test_client",
            conversation_id="test_conv",
            task_type=TaskType.PAN_CARD,
            task_text="Provide PAN card document",
            task_key="pan_card",
            owner="client",
            status=ActionStatus.OPEN,
            metadata={},
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        
        extracted_action = ExtractedAction(
            task_text="Provide PAN card",
            task_type=TaskType.PAN_CARD,
            owner="client",
            metadata={},
            deliverable_type=DeliverableType.PHOTO
        )
        
        match_result = self.matcher._find_best_match(
            extracted_action, [existing_action],
            self.matcher._compute_task_key(extracted_action)
        )
        
        self.assertEqual(match_result.match_type, 'fuzzy')
        self.assertGreater(match_result.confidence, 0.5)
        self.assertEqual(match_result.action_id, 1)
    
    def test_metadata_merge(self):
        existing_metadata = {
            'pan_number': 'ABCDE1234F',
            'deliverable_type': 'photo',
            'priority': 'high'
        }
        
        new_metadata = {
            'pan_number': 'ABCDE1234F',
            'deliverable_type': 'pdf',
            'urls': ['https://example.com']
        }
        
        merged = self.matcher._merge_metadata(existing_metadata, new_metadata)
        
        self.assertEqual(merged['priority'], 'high')
        self.assertEqual(merged['deliverable_type'], 'pdf')
        self.assertIn('urls', merged)
        self.assertEqual(merged['pan_number'], 'ABCDE1234F')
    
    def test_entity_match_score(self):
        new_metadata = {'pan_number': 'ABCDE1234F'}
        existing_metadata = {'pan_number': 'ABCDE1234F'}
        score = self.matcher._compute_entity_match_score(new_metadata, existing_metadata)
        self.assertEqual(score, 1.0)
        
        new_metadata = {'pan_number': 'ABCDE1234F'}
        existing_metadata = {'pan_number': 'XYZDE5678G'}
        score = self.matcher._compute_entity_match_score(new_metadata, existing_metadata)
        self.assertEqual(score, 0.0)
        
        new_metadata = {'urls': ['https://example.com', 'https://test.com']}
        existing_metadata = {'urls': ['https://example.com', 'https://other.com']}
        score = self.matcher._compute_entity_match_score(new_metadata, existing_metadata)
        self.assertEqual(score, 1.0)


class TestEdgeCases(unittest.TestCase):
    def setUp(self):
        self.extractor = RuleBasedExtractor()
        self.matcher = ActionMatcher()
    
    def test_pan_number_to_photo_scenario(self):
        text1 = "Please provide your PAN number"
        actions1 = self.extractor.extract_actions(text1, "rm")
        
        self.assertEqual(len(actions1), 1)
        self.assertEqual(actions1[0].deliverable_type, DeliverableType.NUMBER)
        
        text2 = "My PAN number is ABCDE1234F"
        actions2 = self.extractor.extract_actions(text2, "client")
        
        self.assertEqual(len(actions2), 1)
        self.assertEqual(actions2[0].metadata['pan_number'], 'ABCDE1234F')
        self.assertEqual(actions2[0].status_hint, 'closed')
        
        text3 = "Please send a photo of your PAN card"
        actions3 = self.extractor.extract_actions(text3, "rm")
        
        self.assertEqual(len(actions3), 1)
        self.assertEqual(actions3[0].deliverable_type, DeliverableType.PHOTO)
        
        task_key1 = self.matcher._compute_task_key(actions2[0])
        task_key2 = self.matcher._compute_task_key(actions3[0])
        
        self.assertIn('pan_card', task_key1)
        self.assertIn('pan_card', task_key2)
    
    def test_attachment_url_scenario(self):
        text1 = "Please upload the PAN card document"
        actions1 = self.extractor.extract_actions(text1, "rm")
        
        self.assertEqual(len(actions1), 1)
        self.assertEqual(actions1[0].deliverable_type, DeliverableType.PDF)
        
        text2 = "Here is the document: https://example.com/pan.pdf"
        actions2 = self.extractor.extract_actions(text2, "client")
        
        self.assertEqual(len(actions2), 1)
        self.assertIn('urls', actions2[0].metadata)
        self.assertEqual(actions2[0].status_hint, 'closed')
        
        task_key1 = self.matcher._compute_task_key(actions1[0])
        task_key2 = self.matcher._compute_task_key(actions2[0])
        
        self.assertIn('pan_card', task_key1)
        self.assertIn('other', task_key2)
        self.assertIn('url', task_key2)
    
    def test_different_deliverable_types(self):
        text1 = "Please send a photo of your PAN card"
        actions1 = self.extractor.extract_actions(text1, "rm")
        
        text2 = "Please provide your PAN number"
        actions2 = self.extractor.extract_actions(text2, "rm")
        
        self.assertEqual(actions1[0].deliverable_type, DeliverableType.PHOTO)
        self.assertEqual(actions2[0].deliverable_type, DeliverableType.NUMBER)
        
        task_key1 = self.matcher._compute_task_key(actions1[0])
        task_key2 = self.matcher._compute_task_key(actions2[0])
        
        self.assertNotEqual(task_key1, task_key2)
        self.assertIn('photo', task_key1)
        self.assertIn('number', task_key2)
    
    def test_tentative_action_creation(self):
        extracted_action = ExtractedAction(
            task_text="Provide PAN document",
            task_type=TaskType.PAN_CARD,
            owner="client",
            metadata={},
            deliverable_type=DeliverableType.PDF,
            confidence=0.7
        )
        
        existing_action = Action(
            id=1,
            client_id="test_client",
            conversation_id="test_conv",
            task_type=TaskType.PAN_CARD,
            task_text="Provide PAN card photo",
            task_key="pan_card_photo_client",
            owner="client",
            status=ActionStatus.OPEN,
            metadata={},
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        
        match_result = self.matcher._find_best_match(
            extracted_action, [existing_action],
            self.matcher._compute_task_key(extracted_action)
        )
        
        self.assertEqual(match_result.match_type, 'fuzzy')
        self.assertGreaterEqual(match_result.confidence, 0.6)
        self.assertGreater(match_result.confidence, 0.8)


class TestRuleBasedExtractorAdvanced(unittest.TestCase):
    def setUp(self):
        self.extractor = RuleBasedExtractor()
    
    def test_complex_pan_scenario(self):
        text1 = "Please provide your PAN card document"
        actions1 = self.extractor.extract_actions(text1, "rm")
        self.assertEqual(len(actions1), 1)
        self.assertEqual(actions1[0].task_type, TaskType.PAN_CARD)
        
        text2 = "My PAN number is ABCDE1234F"
        actions2 = self.extractor.extract_actions(text2, "client")
        self.assertEqual(len(actions2), 1)
        self.assertEqual(actions2[0].metadata['pan_number'], 'ABCDE1234F')
        self.assertEqual(actions2[0].status_hint, 'closed')
        
        text3 = "Please send a photo of your PAN card"
        actions3 = self.extractor.extract_actions(text3, "rm")
        self.assertEqual(len(actions3), 1)
        self.assertEqual(actions3[0].task_type, TaskType.PAN_CARD)
        self.assertEqual(actions3[0].deliverable_type, DeliverableType.PHOTO)
    
    def test_multiple_document_types(self):
        text = "Please provide PAN card, Aadhaar card, and bank statement"
        actions = self.extractor.extract_actions(text, "rm")
        
        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0].task_type, TaskType.PAN_CARD)


if __name__ == '__main__':
    unittest.main(verbosity=2)