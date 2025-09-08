import re
from typing import List, Dict, Any, Optional

from models import ExtractedAction, TaskType, DeliverableType


class RuleBasedExtractor:
    def __init__(self):
        self.task_patterns = {
            TaskType.PAN_CARD: [
                r'pan\s+card', r'pan\s+number', r'permanent\s+account\s+number',
                r'pan\s+document', r'pan\s+copy'
            ],
            TaskType.AADHAAR: [
                r'aadhaar', r'aadhar', r'uid', r'unique\s+identification',
                r'aadhaar\s+card', r'aadhaar\s+number'
            ],
            TaskType.BANK_STATEMENT: [
                r'bank\s+statement', r'bank\s+statement\s+pdf', r'bank\s+details',
                r'account\s+statement', r'banking\s+statement'
            ],
            TaskType.INCOME_PROOF: [
                r'income\s+proof', r'salary\s+certificate', r'income\s+certificate',
                r'pay\s+slip', r'salary\s+slip', r'income\s+document'
            ],
            TaskType.ADDRESS_PROOF: [
                r'address\s+proof', r'address\s+document', r'residence\s+proof',
                r'utility\s+bill', r'address\s+certificate'
            ],
            TaskType.PHOTO: [
                r'photo', r'photograph', r'picture', r'passport\s+size\s+photo',
                r'profile\s+picture', r'headshot'
            ],
            TaskType.SIGNATURE: [
                r'signature', r'sign', r'digital\s+signature', r'wet\s+signature'
            ]
        }
        
        self.action_verbs = {
            'request': ['send', 'provide', 'upload', 'share', 'submit', 'give', 'furnish'],
            'completion': ['received', 'collected', 'got', 'obtained', 'submitted', 'uploaded', 'here is', 'here are'],
            'modification': ['update', 'change', 'modify', 'revise', 'correct']
        }
        
        self.deliverable_patterns = {
            DeliverableType.PHOTO: [r'photo', r'image', r'picture', r'photograph'],
            DeliverableType.PDF: [r'pdf', r'document', r'file'],
            DeliverableType.NUMBER: [r'number', r'no\.', r'#'],
            DeliverableType.URL: [r'url', r'link', r'http', r'www'],
            DeliverableType.ATTACHMENT: [r'attachment', r'attached', r'file']
        }
        
        self.pan_pattern = r'[A-Z]{5}[0-9]{4}[A-Z]{1}'
        self.url_pattern = r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
    
    def extract_actions(self, text: str, sender: str) -> List[ExtractedAction]:
        text_lower = text.lower()
        actions = []
        
        is_request = any(verb in text_lower for verb in self.action_verbs['request'])
        is_completion = any(verb in text_lower for verb in self.action_verbs['completion'])
        is_modification = any(verb in text_lower for verb in self.action_verbs['modification'])
        
        if re.search(self.pan_pattern, text.upper()) and ('is' in text_lower or 'are' in text_lower):
            is_completion = True
        
        status_hint = None
        if is_completion:
            status_hint = 'closed'
        elif is_modification:
            status_hint = 'modify'
        
        matched_types = []
        for task_type, patterns in self.task_patterns.items():
            for pattern in patterns:
                if re.search(pattern, text_lower):
                    matched_types.append(task_type)
                    break
        
        if matched_types:
            task_type = matched_types[0]
            action = self._create_action(
                text=text,
                task_type=task_type,
                sender=sender,
                status_hint=status_hint
            )
            if action:
                actions.append(action)
        
        if not actions and (is_request or is_completion):
            general_doc_patterns = [
                r'document', r'paper', r'certificate', r'proof', r'copy'
            ]
            has_url = bool(re.search(self.url_pattern, text))
            
            if any(re.search(pattern, text_lower) for pattern in general_doc_patterns) or has_url:
                action = self._create_action(
                    text=text,
                    task_type=TaskType.OTHER,
                    sender=sender,
                    status_hint=status_hint
                )
                if action:
                    actions.append(action)
        
        return actions
    
    def _create_action(self, text: str, task_type: TaskType, 
                      sender: str, status_hint: Optional[str]) -> Optional[ExtractedAction]:
        metadata = {}
        deliverable_type = None
        
        pan_match = re.search(self.pan_pattern, text.upper())
        if pan_match:
            metadata['pan_number'] = pan_match.group()
        
        urls = re.findall(self.url_pattern, text)
        if urls:
            metadata['urls'] = urls
        
        text_lower = text.lower()
        if urls:
            deliverable_type = DeliverableType.URL
        else:
            for deliverable, patterns in self.deliverable_patterns.items():
                if any(re.search(pattern, text_lower) for pattern in patterns):
                    deliverable_type = deliverable
                    break
        
        owner = 'client' if sender == 'rm' else 'rm'
        task_text = self._generate_task_text(text, task_type)
        
        return ExtractedAction(
            task_text=task_text,
            task_type=task_type,
            owner=owner,
            status_hint=status_hint,
            metadata=metadata,
            deliverable_type=deliverable_type,
            confidence=0.8
        )
    
    def _generate_task_text(self, original_text: str, task_type: TaskType) -> str:
        task_templates = {
            TaskType.PAN_CARD: "Provide PAN card document",
            TaskType.AADHAAR: "Provide Aadhaar card document",
            TaskType.BANK_STATEMENT: "Provide bank statement",
            TaskType.INCOME_PROOF: "Provide income proof document",
            TaskType.ADDRESS_PROOF: "Provide address proof document",
            TaskType.PHOTO: "Provide photograph",
            TaskType.SIGNATURE: "Provide signature",
            TaskType.OTHER: "Provide requested document"
        }
        
        base_text = task_templates.get(task_type, "Provide requested document")
        
        if 'photo' in original_text.lower():
            base_text += " (photo required)"
        elif 'pdf' in original_text.lower():
            base_text += " (PDF required)"
        elif 'number' in original_text.lower():
            base_text += " (number required)"
        
        return base_text


action_extractor = RuleBasedExtractor()