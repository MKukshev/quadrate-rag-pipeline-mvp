"""
Conversation Thread Parser
Parses email threads, chat exports, and user chat messages
"""

import re
from typing import List, Dict, Optional
from datetime import datetime
from dataclasses import dataclass


@dataclass
class Message:
    """Single message in a conversation thread"""
    sender: str
    recipients: List[str]
    date: datetime
    text: str
    subject: Optional[str] = None
    message_id: Optional[str] = None
    reply_to: Optional[str] = None
    
    def to_dict(self) -> Dict:
        return {
            "sender": self.sender,
            "recipients": self.recipients,
            "date": self.date.isoformat(),
            "text": self.text,
            "subject": self.subject,
            "message_id": self.message_id,
            "reply_to": self.reply_to
        }


class Thread:
    """Conversation thread with multiple messages"""
    
    def __init__(self, messages: List[Message], thread_type: str = "general"):
        self.messages = sorted(messages, key=lambda m: m.date)
        self.thread_type = thread_type  # "email", "telegram", "user_chat"
        self.participants = self._extract_participants()
        
    def _extract_participants(self) -> List[str]:
        """Extract unique participants from messages"""
        participants = set()
        for msg in self.messages:
            participants.add(msg.sender)
            participants.update(msg.recipients)
        return sorted(participants)
    
    @property
    def start_date(self) -> datetime:
        return self.messages[0].date if self.messages else datetime.now()
    
    @property
    def end_date(self) -> datetime:
        return self.messages[-1].date if self.messages else datetime.now()
    
    @property
    def duration_days(self) -> int:
        if not self.messages:
            return 0
        return (self.end_date - self.start_date).days
    
    def to_structured_text(self) -> str:
        """
        Convert thread to structured text for LLM summarization
        Maintains conversation flow and context
        """
        result = []
        
        # Header
        result.append(f"# Conversation Thread ({self.thread_type})")
        result.append(f"Participants: {', '.join(self.participants)}")
        result.append(f"Messages: {len(self.messages)}")
        result.append(f"Duration: {self.start_date.strftime('%Y-%m-%d')} to {self.end_date.strftime('%Y-%m-%d')} ({self.duration_days} days)")
        result.append("")
        result.append("---")
        result.append("")
        
        # Messages
        for i, msg in enumerate(self.messages, 1):
            result.append(f"## Message {i}")
            result.append(f"**From:** {msg.sender}")
            
            if msg.recipients:
                result.append(f"**To:** {', '.join(msg.recipients)}")
            
            result.append(f"**Date:** {msg.date.strftime('%Y-%m-%d %H:%M')}")
            
            if msg.subject:
                result.append(f"**Subject:** {msg.subject}")
            
            if msg.reply_to:
                result.append(f"**Reply to:** {msg.reply_to}")
            
            result.append("")
            result.append(msg.text)
            result.append("")
            result.append("---")
            result.append("")
        
        return "\n".join(result)


def parse_email_thread(text: str) -> Thread:
    """
    Parse email thread from text format
    
    Supports standard email format:
    From: Alice <alice@example.com>
    Date: Mon, 10 Jan 2025 10:00:00
    To: Bob <bob@example.com>
    Subject: Project Discussion
    
    Also supports Russian email headers:
    От: Alice <alice@example.com>
    Дата: Mon, 10 Jan 2025 10:00:00
    Кому: Bob <bob@example.com>
    Тема: Project Discussion
    
    Message body...
    """
    messages = []
    
    # Preprocess: Remove file-level headers
    text = re.sub(r'^ПЕРЕПИСКА ПО EMAIL.*?\n', '', text, flags=re.MULTILINE | re.IGNORECASE)
    text = re.sub(r'^Тема:.*?\n', '', text, flags=re.MULTILINE)
    text = re.sub(r'^Период:.*?\n', '', text, flags=re.MULTILINE)
    
    # Split by разделители (═══) СНАЧАЛА
    sections = re.split(r'═+', text)
    sections = [s.strip() for s in sections if s.strip()]
    
    if len(sections) <= 1:
        # If no separators, try splitting by "From:" or "От:"
        email_pattern = r'(?:From|От):.*?(?=\n(?:From|От):|$)'
        raw_emails = re.findall(email_pattern, text, re.DOTALL | re.MULTILINE)
    else:
        raw_emails = sections
    
    for idx, raw in enumerate(raw_emails):
        # Extract sender (supports both English and Russian)
        sender_match = re.search(r'(?:From|От):\s*(.+?)(?:<(.+?)>)?(?:\n|$)', raw, re.IGNORECASE)
        if sender_match:
            sender = sender_match.group(1).strip()
            email = sender_match.group(2)
            if email:
                sender = f"{sender} <{email}>"
        else:
            sender = "Unknown"
        
        # Extract recipients (supports both English and Russian)
        to_match = re.search(r'(?:To|Кому):\s*(.+?)(?:\n|$)', raw, re.IGNORECASE)
        if to_match:
            recipients_str = to_match.group(1).strip()
            recipients = [r.strip() for r in recipients_str.split(',')]
        else:
            recipients = []
        
        # Extract date (supports both English and Russian)
        date_match = re.search(r'(?:Date|Дата):\s*(.+?)(?:\n|$)', raw, re.IGNORECASE)
        if date_match:
            date_str = date_match.group(1).strip()
            # Try multiple date formats
            date = parse_date_flexible(date_str)
        else:
            date = datetime.now()
        
        # Extract subject (supports both English and Russian)
        subject_match = re.search(r'(?:Subject|Тема):\s*(.+?)(?:\n|$)', raw, re.IGNORECASE)
        subject = subject_match.group(1).strip() if subject_match else None
        
        # Extract message ID (optional)
        msgid_match = re.search(r'Message-ID:\s*<(.+?)>', raw)
        message_id = msgid_match.group(1) if msgid_match else f"msg_{idx}"
        
        # Extract reply-to reference
        reply_match = re.search(r'In-Reply-To:\s*<(.+?)>', raw)
        reply_to = reply_match.group(1) if reply_match else None
        
        # Extract body (everything after last header line)
        lines = raw.split('\n')
        body_start = 0
        for i, line in enumerate(lines):
            if re.match(r'^(?:From|От|To|Кому|Date|Дата|Subject|Тема|Message-ID|In-Reply-To):', line, re.IGNORECASE):
                body_start = i + 1
        
        text_raw = '\n'.join(lines[body_start:]).strip()
        
        # Clean up separators and multiple newlines
        text_raw = re.sub(r'═+', '', text_raw)
        text_raw = re.sub(r'\n{3,}', '\n\n', text_raw)
        
        # Clean quoted text and signatures
        text = clean_email_text(text_raw)
        
        messages.append(Message(
            sender=sender,
            recipients=recipients,
            date=date,
            text=text,
            subject=subject,
            message_id=message_id,
            reply_to=reply_to
        ))
    
    return Thread(messages, thread_type="email")


def parse_telegram_chat(text: str) -> Thread:
    """
    Parse Telegram chat export
    
    Format:
    [10.01.2025, 10:00] Alice: Message text
    [10.01.2025, 10:05] Bob: Reply text
    """
    messages = []
    
    # Pattern for Telegram messages
    pattern = r'\[(.+?)\]\s*(.+?):\s*(.+?)(?=\[|$)'
    matches = re.findall(pattern, text, re.DOTALL)
    
    for idx, (date_str, sender, msg_text) in enumerate(matches):
        # Parse date
        date = parse_date_flexible(date_str)
        
        messages.append(Message(
            sender=sender.strip(),
            recipients=[],  # Group chat, no specific recipients
            date=date,
            text=msg_text.strip(),
            message_id=f"tg_{idx}"
        ))
    
    return Thread(messages, thread_type="telegram")


def parse_whatsapp_chat(text: str) -> Thread:
    """
    Parse WhatsApp chat export
    
    Format:
    10/01/2025, 10:00 - Alice: Message text
    10/01/2025, 10:05 - Bob: Reply text
    """
    messages = []
    
    # Pattern for WhatsApp messages
    pattern = r'(\d{1,2}/\d{1,2}/\d{4},\s*\d{1,2}:\d{2})\s*-\s*(.+?):\s*(.+?)(?=\d{1,2}/\d{1,2}/\d{4}|$)'
    matches = re.findall(pattern, text, re.DOTALL)
    
    for idx, (date_str, sender, msg_text) in enumerate(matches):
        date = parse_date_flexible(date_str)
        
        messages.append(Message(
            sender=sender.strip(),
            recipients=[],
            date=date,
            text=msg_text.strip(),
            message_id=f"wa_{idx}"
        ))
    
    return Thread(messages, thread_type="whatsapp")


def clean_email_text(text: str) -> str:
    """
    Clean email text:
    - Remove quoted replies (lines starting with >, |)
    - Remove email signatures
    - Remove forwarded headers
    """
    lines = text.split('\n')
    cleaned = []
    in_signature = False
    
    for line in lines:
        # Skip quoted lines
        if line.strip().startswith(('>', '|', 'On ', '----', '====', 'From:', 'Sent:', 'To:', 'Subject:')):
            continue
        
        # Detect signature start
        if line.strip() in ('--', '___', 'Best regards', 'Best,', 'Thanks,', 'Regards,'):
            in_signature = True
            continue
        
        if not in_signature:
            cleaned.append(line)
    
    return '\n'.join(cleaned).strip()


def parse_date_flexible(date_str: str) -> datetime:
    """
    Parse date from multiple formats
    """
    formats = [
        '%a, %d %b %Y %H:%M:%S',  # Email: Mon, 10 Jan 2025 10:00:00
        '%d.%m.%Y, %H:%M',         # Telegram: 10.01.2025, 10:00
        '%d/%m/%Y, %H:%M',         # WhatsApp: 10/01/2025, 10:00
        '%Y-%m-%d %H:%M:%S',       # ISO: 2025-01-10 10:00:00
        '%Y-%m-%dT%H:%M:%S',       # ISO with T
    ]
    
    # Clean up timezone info and extra text
    date_str = re.sub(r'\s+\(.*?\)', '', date_str)  # Remove (GMT+0300)
    date_str = re.sub(r'\s+[+-]\d{4}', '', date_str)  # Remove +0300
    date_str = date_str.strip()
    
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    
    # Fallback: try to parse at least the date part
    try:
        date_match = re.search(r'(\d{1,2})[./](\d{1,2})[./](\d{4})', date_str)
        if date_match:
            day, month, year = date_match.groups()
            return datetime(int(year), int(month), int(day))
    except:
        pass
    
    # Final fallback
    return datetime.now()

