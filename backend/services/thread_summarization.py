"""
Thread Summarization
Structured summarization of conversation threads with action items extraction
"""

import json
import re
from typing import Dict, List, Optional
from .thread_parser import Thread
from .rag import call_llm
from .language_detection import detect_language, get_language_instruction, get_language_name


async def summarize_thread(
    thread: Thread,
    extract_action_items: bool = True,
    extract_decisions: bool = True,
    extract_topics: bool = True,
    focus: Optional[str] = None
) -> Dict:
    """
    Суммаризировать thread с извлечением структурированной информации
    
    Args:
        thread: Thread object with messages
        extract_action_items: Extract action items/tasks
        extract_decisions: Extract decisions made
        extract_topics: Extract discussed topics
        focus: Optional focus area
    
    Returns:
        Dict with summary and extracted information
    """
    
    # 1. Generate structured text representation
    structured_text = thread.to_structured_text()
    
    # 2. Language detection
    detected_lang = detect_language(structured_text)
    lang_instruction = get_language_instruction(detected_lang)
    lang_name = get_language_name(detected_lang)
    
    # 3. Base summary
    base_prompt = f"""{lang_instruction}
Summarize this {thread.thread_type} conversation thread.

Focus on:
- Main discussion points
- Key outcomes
- Important concerns or questions raised
- Final conclusion or next steps

{structured_text}

{'Focus specifically on: ' + focus if focus else ''}

Provide a clear, coherent summary in 2-4 paragraphs.
Remember: USE THE SAME LANGUAGE ({lang_name}) as the messages above!
SUMMARY (in {lang_name}):"""
    
    summary = call_llm(base_prompt)
    
    result = {
        "summary": summary,
        "thread_type": thread.thread_type,
        "participants": thread.participants,
        "message_count": len(thread.messages),
        "start_date": thread.start_date.isoformat(),
        "end_date": thread.end_date.isoformat(),
        "duration_days": thread.duration_days
    }
    
    # 4. Extract action items (tasks, TODOs, assignments)
    if extract_action_items:
        action_prompt = f"""{lang_instruction}
Extract all action items, tasks, and assignments from this conversation.

For each action item, identify:
- Task description (what needs to be done)
- Owner/Assignee (who is responsible) - if mentioned
- Deadline/Due date (when it's due) - if mentioned
- Priority (high/medium/low) - if mentioned

{structured_text}

Return a JSON array of action items. Each item should have:
{{"task": "description", "owner": "name or null", "deadline": "date or null", "priority": "level or null"}}

If no action items found, return empty array: []
Remember: USE THE SAME LANGUAGE ({lang_name}) as the messages!"""
        
        try:
            action_response = call_llm(action_prompt)
            # Try to extract JSON from response
            action_items = extract_json_from_text(action_response)
            if not isinstance(action_items, list):
                action_items = []
        except Exception as e:
            print(f"[Thread] Failed to extract action items: {e}")
            action_items = []
        
        result["action_items"] = action_items
    
    # 5. Extract decisions
    if extract_decisions:
        decision_prompt = f"""{lang_instruction}
List all decisions made in this conversation.

Include:
- Approvals or rejections
- Agreements reached
- Budget allocations
- Timeline commitments
- Resource assignments
- Policy decisions

{structured_text}

List each decision clearly, one per line. Start each with "- ".
If no decisions found, return "No explicit decisions made."
Remember: USE THE SAME LANGUAGE ({lang_name}) as the messages!"""
        
        try:
            decisions_text = call_llm(decision_prompt)
            # Parse decisions (each line starting with "-")
            decisions = [
                line.strip('- ').strip()
                for line in decisions_text.split('\n')
                if line.strip().startswith('-') and len(line.strip()) > 2
            ]
            
            if not decisions and "no" in decisions_text.lower():
                decisions = []
        except Exception as e:
            print(f"[Thread] Failed to extract decisions: {e}")
            decisions = []
        
        result["decisions"] = decisions
    
    # 6. Extract topics
    if extract_topics:
        topic_prompt = f"""{lang_instruction}
Identify the main topics discussed in this conversation.

{structured_text}

List 3-7 key topics. Format as comma-separated list.
Example: Budget Planning, Timeline Discussion, Resource Allocation

Remember: USE THE SAME LANGUAGE ({lang_name}) as the messages!

Topics:"""
        
        try:
            topics_text = call_llm(topic_prompt)
            # Parse topics
            topics = [
                t.strip()
                for t in re.split(r'[,\n]', topics_text)
                if t.strip() and len(t.strip()) > 2
            ][:10]  # Limit to 10 topics
        except Exception as e:
            print(f"[Thread] Failed to extract topics: {e}")
            topics = []
        
        result["topics"] = topics
    
    return result


def extract_json_from_text(text: str) -> any:
    """
    Extract JSON from LLM response
    
    LLM might wrap JSON in markdown code blocks or add explanation
    """
    # Try to find JSON in code blocks
    json_match = re.search(r'```(?:json)?\s*(\[.*?\])\s*```', text, re.DOTALL)
    if json_match:
        json_str = json_match.group(1)
    else:
        # Try to find JSON directly
        json_match = re.search(r'(\[.*?\])', text, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
        else:
            # No JSON found
            return []
    
    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        # Try to clean and parse again
        json_str = json_str.replace("'", '"')  # Replace single quotes
        json_str = re.sub(r',\s*}', '}', json_str)  # Remove trailing commas
        json_str = re.sub(r',\s*\]', ']', json_str)
        try:
            return json.loads(json_str)
        except:
            return []


async def summarize_thread_from_messages(
    messages: List[Dict],
    chat_type: str = "user_chat",
    **kwargs
) -> Dict:
    """
    Summarize thread from raw message dicts
    
    Args:
        messages: List of message dicts with sender, text, timestamp
        chat_type: Type of chat
        **kwargs: Additional args for summarize_thread
    """
    from .thread_parser import Message, Thread
    from datetime import datetime
    
    # Convert dicts to Message objects
    message_objs = []
    for msg in messages:
        timestamp = msg.get("timestamp")
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp)
        elif timestamp is None:
            timestamp = datetime.now()
        
        message_objs.append(Message(
            sender=msg.get("sender", "Unknown"),
            recipients=msg.get("recipients", []),
            date=timestamp,
            text=msg.get("text", ""),
            subject=msg.get("subject"),
            message_id=msg.get("message_id"),
            reply_to=msg.get("reply_to")
        ))
    
    # Create thread
    thread = Thread(message_objs, thread_type=chat_type)
    
    # Summarize
    return await summarize_thread(thread, **kwargs)

