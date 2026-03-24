"""
CortexAdapter v3 — Structured Facts for Exact Q&A

Stores facts in a structured format that enables:
1. Speaker-based lookup
2. Date extraction
3. Exact keyword matching
"""

import json
import time
import re
import requests
from typing import List, Dict, Tuple, Optional
from datetime import datetime


class CortexAdapterV3:
    """Enhanced Cortex adapter with structured storage."""

    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        self.api_url = self.config.get('api_url', 'http://localhost:8003')
        self.token = self.config.get('token', 'dev-token')
        self.timeout = self.config.get('timeout', 10)
        self._session = requests.Session()
        self._session.headers.update({
            'Content-Type': 'application/json',
            'X-Cortex-Token': self.token
        })
        # Structured local storage
        self._structured_facts: List[Dict] = []

    def ingest(self, facts: List[str]) -> bool:
        """Ingest facts as structured data."""
        self._structured_facts = []
        
        for i, fact in enumerate(facts):
            # Parse speaker from "Speaker: text" format
            parts = fact.split(': ', 1)
            speaker = parts[0] if len(parts) > 1 else 'unknown'
            text = parts[1] if len(parts) > 1 else fact
            
            # Extract structured info
            structured = {
                'speaker': speaker,
                'text': text,
                'raw': fact,
                'index': i
            }
            
            # Extract dates
            dates = re.findall(r'\b\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4}\b', text, re.I)
            dates.extend(re.findall(r'\b\d{4}-\d{2}-\d{2}\b', text))
            structured['dates'] = dates
            
            # Extract years
            years = re.findall(r'\b(19|20)\d{2}\b', text)
            structured['years'] = list(set(years))
            
            # Extract numbers
            numbers = re.findall(r'\b\d+\b', text)
            structured['numbers'] = [int(n) for n in numbers if len(n) <= 4]
            
            # Extract key entities (capitalized words)
            entities = re.findall(r'\b[A-Z][a-z]+\b', text)
            structured['entities'] = list(set([e for e in entities if len(e) > 2]))
            
            self._structured_facts.append(structured)
            
            # Also store in Cortex with speaker as key
            try:
                payload = json.dumps({
                    'path': f'fact/{speaker.lower()}/{i}',
                    'content': fact,
                    'metadata': {
                        'type': 'structured_fact',
                        'speaker': speaker.lower(),
                        'dates': json.dumps(dates),
                        'text': text[:100]
                    }
                })
                response = self._session.post(
                    f'{self.api_url}/memory/add',
                    data=payload,
                    timeout=self.timeout
                )
            except:
                pass
        
        return True

    def query(self, question: str) -> Tuple[str, float]:
        """Query using structured matching."""
        start_time = time.time()
        
        # Parse question to extract speaker and what we're looking for
        q_lower = question.lower()
        
        # Extract speaker from question (skip question words)
        question_words = {'when', 'what', 'where', 'who', 'how', 'which', 'whom', 'whose'}
        speaker_match = None
        for match in re.finditer(r'\b([A-Z][a-z]+)\b', question):
            if match.group(1).lower() not in question_words:
                speaker_match = match.group(1).lower()
                break
        speaker = speaker_match
        
        # What type of answer do we need?
        has_date = bool(re.search(r'\b(when|date|day|month|year|time)\b', q_lower, re.I))
        has_number = bool(re.search(r'\b(how many|how much|number|count)\b', q_lower, re.I))
        has_name = bool(re.search(r'\b(who|name|person)\b', q_lower, re.I))
        has_place = bool(re.search(r'\b(where|place|location)\b', q_lower, re.I))
        has_what = bool(re.search(r'\b(what|which)\b', q_lower, re.I))
        has_why = bool(re.search(r'\b(why|because|reason)\b', q_lower, re.I))
        
        # Extract dates/numbers from question
        q_dates = re.findall(r'\b\d{1,2}\s+\w+\s+\d{4}\b', question, re.I)
        q_years = re.findall(r'\b(19|20)\d{2}\b', question)
        q_numbers = [int(n) for n in re.findall(r'\b\d+\b', question) if len(n) <= 4]
        
        best_answer = ''
        best_score = 0
        
        # Search structured facts
        for fact in self._structured_facts:
            score = 0
            
            # Speaker match is crucial
            if speaker and fact['speaker'].lower() == speaker:
                score += 10
            elif speaker:
                continue  # Skip facts from other speakers if question mentions someone
            
            # Match dates - if question asks for dates, prefer facts with dates
            if has_date:
                if fact.get('dates'):
                    score += 8  # Strong bonus for having dates
                for d in fact.get('dates', []):
                    if any(d in qd or qd in d for qd in q_dates):
                        score += 5
                for y in fact.get('years', []):
                    if y in q_years:
                        score += 3
            
            # Match numbers
            if has_number:
                if fact.get('numbers'):
                    score += 8
                for n in fact.get('numbers', []):
                    if n in q_numbers:
                        score += 5
            
            # Match entities
            for entity in fact.get('entities', []):
                entity_lower = entity.lower()
                if entity_lower in q_lower:
                    score += 2
            
            # For "what" questions, prefer facts containing action verbs from question
            if has_what:
                # Extract key content words from question (excluding stop words)
                stop_words = {'what', 'did', 'does', 'do', 'she', 'he', 'they', 'it', 'a', 'the', 'an', 'is', 'are', 'was', 'were', 'to', 'in', 'on', 'at', 'for', 'with'}
                q_words = set(w for w in re.findall(r'\b\w+\b', q_lower) if w not in stop_words and len(w) > 2)
                fact_words = set(w for w in re.findall(r'\b\w+\b', fact['text'].lower()) if len(w) > 2)
                
                # Check for word overlap
                overlap = q_words & fact_words
                score += len(overlap) * 2
                
                # Bonus if fact contains a verb (has action)
                if re.search(r'\b(started?|begun|joined?|attending?|going|member)\b', fact['text'], re.I):
                    score += 5
            
            # Bonus for short, direct answers (more likely to be the answer)
            if len(fact['text']) < 100:
                score += 1
            
            # Bonus for answers that seem complete (contain punctuation ending a sentence)
            if fact['text'].strip().endswith(('.', '!', '?')):
                score += 1
            
            # Keyword overlap bonus - how many question words appear in fact
            fact_lower = fact['text'].lower()
            question_words_to_check = []
            
            # Extract key content words from question (excluding common stop words)
            stop_words = {
                'when', 'what', 'where', 'who', 'how', 'which', 'whom', 'whose',
                'did', 'does', 'do', 'she', 'he', 'they', 'it', 'a', 'an', 'the',
                'is', 'are', 'was', 'were', 'to', 'in', 'on', 'at', 'for', 'with',
                'that', 'this', 'these', 'those', 'be', 'been', 'being', 'have', 'has',
                'had', 'going', 'goingto', 'gonna', 'want', 'wanted', 'would', 'could',
                'should', 'from', 'by', 'about', 'into', 'through', 'during', 'before',
                'after', 'above', 'below', 'between', 'under', 'again', 'further', 'then',
                'once', 'here', 'there', 'all', 'each', 'few', 'more', 'most', 'other',
                'some', 'such', 'only', 'own', 'same', 'so', 'than', 'too', 'very',
                'just', 'now', 'and', 'but', 'or', 'because', 'as', 'until', 'while'
            }
            q_words = set(w for w in re.findall(r'\b\w+\b', q_lower) if w not in stop_words and len(w) > 2)
            f_words = set(w for w in re.findall(r'\b\w+\b', fact_lower) if len(w) > 2)
            
            # Check keyword overlap
            overlap = q_words & f_words
            score += len(overlap) * 1.5
            
            if score > best_score:
                best_score = score
                best_answer = fact['text']
        
        latency_ms = (time.time() - start_time) * 1000
        
        # If no good structured match, try semantic
        if best_score < 5:
            try:
                payload = json.dumps({'query': question, 'limit': 5})
                response = self._session.post(
                    f'{self.api_url}/memory/search',
                    data=payload,
                    timeout=self.timeout
                )
                if response.status_code == 200:
                    data = response.json()
                    results = data.get('results', [])
                    if results and results[0].get('content'):
                        # Check if this is actually relevant
                        content = results[0]['content']
                        # Reject if it's clearly unrelated (too long, wrong topic)
                        if speaker and speaker.lower() in content.lower():
                            best_answer = results[0].get('content', '')[:500]
            except:
                pass
        
        return best_answer, latency_ms

    def health_check(self) -> bool:
        try:
            response = self._session.get(f'{self.api_url}/health', timeout=5)
            return response.status_code == 200
        except:
            return False

    def clear(self) -> bool:
        self._structured_facts = []
        return True
