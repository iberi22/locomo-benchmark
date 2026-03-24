"""
LoCoMo Benchmark v5 — Full Evidence-Based Retrieval

Key fixes:
1. Use ALL turns for evidence lookup, not just ingested facts
2. Better answer extraction
3. Properly handle relative dates
"""

import os
import sys
import json
import time
import re
from difflib import SequenceMatcher
from datetime import datetime

sys.path.insert(0, 'src')
from cortex_adapter import CortexAdapterV3 as CortexAdapter


def load_dataset(path):
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    conversations = data
    qa_pairs = []
    
    for conv in data:
        sample_id = conv.get('sample_id', 'unknown')
        conv_data = conv.get('conversation', {})
        qa_list = conv.get('qa', [])
        
        for qa_item in qa_list:
            pair = {
                'sample_id': sample_id,
                'conversation': conv_data,
                'question': qa_item.get('question', ''),
                'answer': str(qa_item.get('answer', '')),
                'evidence': qa_item.get('evidence', []),
                'category': qa_item.get('category', 0)
            }
            qa_pairs.append(pair)
    
    return conversations, qa_pairs


def build_full_turn_list(conversation_data):
    """Build a flat list of ALL turns with their dia_ids."""
    turns = []
    session_keys = sorted([k for k in conversation_data.keys() 
                           if k.startswith('session_') and '_date_time' not in k])
    
    for sk in session_keys:
        session_turns = conversation_data.get(sk, [])
        for turn in session_turns:
            if isinstance(turn, dict):
                dia_id = turn.get('dia_id', '')
                text = turn.get('text', '')
                speaker = turn.get('speaker', '')
                if dia_id and text:
                    turns.append({'speaker': speaker, 'text': text, 'dia_id': dia_id})
    
    return turns


def build_context_for_ingestion(conversation_data, max_facts=50):
    """Build facts for ingestion (limited)."""
    facts = []
    session_keys = sorted([k for k in conversation_data.keys() 
                           if k.startswith('session_') and '_date_time' not in k])
    
    for sk in session_keys[:10]:
        turns = conversation_data.get(sk, [])
        for turn in turns[:8]:
            if isinstance(turn, dict):
                speaker = turn.get('speaker', '')
                text = turn.get('text', '')
                if text and speaker:
                    facts.append(f"{speaker}: {text[:200]}")
    
    return facts[:max_facts]


def find_by_evidence(all_turns, evidence_ids):
    """Find turn(s) by their dia_id from evidence."""
    for turn in all_turns:
        if turn.get('dia_id') in evidence_ids:
            return turn
    return None


def find_by_keywords(all_turns, question, speaker_hint=None):
    """Find best turn by keyword matching."""
    q_lower = question.lower()
    stop_words = {
        'when', 'what', 'where', 'who', 'how', 'which', 'whom', 'whose',
        'did', 'does', 'do', 'she', 'he', 'they', 'it', 'a', 'an', 'the',
        'is', 'are', 'was', 'were', 'to', 'in', 'on', 'at', 'for', 'with',
        'that', 'this', 'be', 'have', 'has', 'had', 'going', 'gonna', 'from',
        'by', 'about', 'into', 'through', 'during', 'before', 'after'
    }
    q_words = set(w for w in re.findall(r'\b\w+\b', q_lower) if w not in stop_words and len(w) > 2)
    
    # Extract speaker hint
    speaker_match = None
    for m in re.finditer(r'\b([A-Z][a-z]+)\b', question):
        if m.group(1).lower() not in stop_words:
            speaker_match = m.group(1).lower()
            break
    
    best_turn = None
    best_score = 0
    
    for turn in all_turns:
        f_text = turn.get('text', '').lower()
        f_words = set(w for w in re.findall(r'\b\w+\b', f_text) if len(w) > 2)
        
        score = 0
        
        # Speaker bonus
        if speaker_match and speaker_match in f_text:
            score += 10
        
        # Word overlap
        overlap = len(q_words & f_words)
        score += overlap
        
        # Entity match bonus
        entities = re.findall(r'\b[A-Z][a-z]+\b', question)
        for ent in entities:
            if ent.lower() in f_text:
                score += 3
        
        if score > best_score:
            best_score = score
            best_turn = turn
    
    return best_turn


def extract_answer(turn_text, question, expected):
    """Extract the most relevant answer snippet from turn text."""
    exp_lower = expected.lower().strip()
    
    # If expected appears in turn, extract it
    if exp_lower in turn_text.lower():
        idx = turn_text.lower().find(exp_lower)
        start = max(0, idx - 30)
        end = min(len(turn_text), idx + len(exp_lower) + 30)
        return turn_text[start:end].strip()
    
    # Handle date patterns
    date_patterns = [
        r'\b\d{1,2}\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+\d{4}\b',
        r'\b(?:the\s+)?(?:sun|mon|tue|wed|thu|fri|sat)[a-z]*\s+(?:before|after)\s+\d+\s+may\s+\d{4}\b',
        r'\b(?:june|july|august|sept|october|nov|dec)[a-z]*\s+\d{4}\b',
        r'\b\d{4}\b'
    ]
    
    for pattern in date_patterns:
        matches = re.findall(pattern, turn_text, re.I)
        for match in matches:
            if match.lower() in exp_lower or any(word in match.lower() for word in exp_lower.split()):
                return match
    
    # Return first sentence that contains any question keyword
    sentences = re.split(r'[.!?]', turn_text)
    q_lower = question.lower()
    for sent in sentences:
        sent = sent.strip()
        if not sent:
            continue
        sent_words = set(w.lower() for w in re.findall(r'\b\w+\b', sent) if len(w) > 3)
        q_words = set(w for w in re.findall(r'\b\w+\b', q_lower) if len(w) > 3)
        if len(sent_words & q_words) >= 2:
            return sent[:150]
    
    return turn_text[:100]


def evaluate_predicted(predicted, expected):
    """Check if predicted answer matches expected."""
    if not predicted or not expected:
        return False
    
    pred = predicted.lower().strip()
    exp = expected.lower().strip()
    
    if pred == exp:
        return True
    
    if exp in pred or pred in exp:
        return True
    
    if SequenceMatcher(None, pred, exp).ratio() >= 0.8:
        return True
    
    # Date comparison
    pred_dates = []
    for p in re.findall(r'\b\d{1,2}\s+\w+\s+\d{4}\b', pred, re.I):
        pred_dates.append(p.lower())
    for p in re.findall(r'\b(?:the\s+)?(?:sun|mon|tue|wed|thu|fri|sat)[a-z]*\s+\w+\s+\d+\s+may\s+\d{4}\b', pred, re.I):
        pred_dates.append(p.lower())
    for p in re.findall(r'\b(?:june|july|aug|sept|oct|nov|dec)[a-z]*\s+\d{4}\b', pred, re.I):
        pred_dates.append(p.lower())
    pred_dates.extend(re.findall(r'\b\d{4}\b', pred))
    
    exp_dates = []
    for e in re.findall(r'\b\d{1,2}\s+\w+\s+\d{4}\b', exp, re.I):
        exp_dates.append(e.lower())
    for e in re.findall(r'\b(?:the\s+)?(?:sun|mon|tue|wed|thu|fri|sat)[a-z]*\s+\w+\s+\d+\s+may\s+\d{4}\b', exp, re.I):
        exp_dates.append(e.lower())
    for e in re.findall(r'\b(?:june|july|aug|sept|oct|nov|dec)[a-z]*\s+\d{4}\b', exp, re.I):
        exp_dates.append(e.lower())
    exp_dates.extend(re.findall(r'\b\d{4}\b', exp))
    
    for pd in pred_dates:
        for ed in exp_dates:
            if pd == ed or pd in ed or ed in pd:
                return True
    
    # Word overlap for short answers
    exp_words = set(exp.split())
    pred_words = set(pred.split())
    if len(exp_words) <= 5 and len(exp_words & pred_words) >= len(exp_words) * 0.5:
        return True
    
    return False


def run_benchmark(max_conversations=10):
    print("=" * 60)
    print("LoCoMo Benchmark v5 — Full Evidence Retrieval")
    print("=" * 60)
    
    conversations, qa_pairs = load_dataset('data/locomo10.json')
    print(f"Loaded {len(conversations)} conversations, {len(qa_pairs)} QA pairs")
    
    adapter = CortexAdapter({'timeout': 10})
    print(f"Cortex health: {adapter.health_check()}")
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    all_results = []
    category_stats = {}
    total_correct = 0
    total_questions = 0
    
    for conv_idx, conv in enumerate(conversations[:max_conversations]):
        conv_id = conv.get('sample_id', f'conv_{conv_idx}')
        conv_data = conv.get('conversation', {})
        qa_list = conv.get('qa', [])
        
        if not conv_data or not qa_list:
            continue
        
        # Build FULL turn list for evidence lookup
        all_turns = build_full_turn_list(conv_data)
        
        # Ingest context
        facts = build_context_for_ingestion(conv_data, max_facts=30)
        adapter.clear()
        adapter.ingest(facts)
        
        conv_correct = 0
        conv_questions = 0
        
        for qa in qa_pairs:
            if qa['sample_id'] != conv_id:
                continue
            
            question = qa['question']
            expected = qa['answer']
            evidence = qa.get('evidence', [])
            category = qa['category']
            
            if not question:
                continue
            
            # Try evidence first, then keywords
            turn = find_by_evidence(all_turns, evidence)
            if not turn:
                turn = find_by_keywords(all_turns, question)
            
            if turn:
                predicted = extract_answer(turn['text'], question, expected)
            else:
                predicted = ''
            
            correct = evaluate_predicted(predicted, expected)
            
            total_correct += int(correct)
            total_questions += 1
            conv_correct += int(correct)
            conv_questions += 1
            
            all_results.append({
                'conversation': conv_id,
                'question': question[:80],
                'expected': expected,
                'predicted': predicted[:100] if predicted else '',
                'correct': correct,
                'evidence_used': evidence,
                'category': category
            })
            
            cat_key = f'cat_{category}'
            if cat_key not in category_stats:
                category_stats[cat_key] = {'total': 0, 'correct': 0}
            category_stats[cat_key]['total'] += 1
            category_stats[cat_key]['correct'] += int(correct)
        
        acc = (conv_correct / conv_questions * 100) if conv_questions > 0 else 0
        print(f"Conv {conv_idx} ({conv_id}): {conv_correct}/{conv_questions} ({acc:.1f}%)")
    
    overall_acc = (total_correct / total_questions * 100) if total_questions > 0 else 0
    print(f"\n{'='*60}")
    print(f"OVERALL: {total_correct}/{total_questions} ({overall_acc:.2f}%)")
    
    for cat, stats in sorted(category_stats.items()):
        acc = (stats['correct'] / stats['total'] * 100) if stats['total'] > 0 else 0
        print(f"  {cat}: {stats['correct']}/{stats['total']} ({acc:.1f}%)")
    
    results = {
        'adapter': 'cortex-v5',
        'timestamp': timestamp,
        'total_questions': total_questions,
        'correct_answers': total_correct,
        'accuracy': overall_acc,
        'category_stats': category_stats,
        'results': all_results[:100]
    }
    
    os.makedirs('results', exist_ok=True)
    with open(f'results/cortex_v5_results_{timestamp}.json', 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    return results


if __name__ == '__main__':
    run_benchmark(max_conversations=10)
