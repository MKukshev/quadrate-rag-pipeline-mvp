"""
Language Detection Utility
Simple and fast language detection for prompting
"""

import re
from typing import Optional


def detect_language(text: str) -> str:
    """
    Простое определение языка текста
    
    Args:
        text: Текст для анализа
        
    Returns:
        Код языка: 'ru', 'en', 'unknown'
    """
    if not text or len(text) < 10:
        return 'unknown'
    
    # Удалить код, ссылки, спецсимволы
    clean_text = re.sub(r'[^а-яА-ЯёЁa-zA-Z\s]', ' ', text)
    clean_text = clean_text.lower()
    
    # Подсчет кириллицы и латиницы
    cyrillic_count = len(re.findall(r'[а-яё]', clean_text))
    latin_count = len(re.findall(r'[a-z]', clean_text))
    
    total = cyrillic_count + latin_count
    if total == 0:
        return 'unknown'
    
    cyrillic_ratio = cyrillic_count / total
    
    # Если > 30% кириллицы - считаем русским
    if cyrillic_ratio > 0.3:
        return 'ru'
    elif latin_count > 20:  # Минимум 20 латинских букв
        return 'en'
    
    return 'unknown'


def get_language_instruction(detected_lang: str) -> str:
    """
    Получить инструкцию о языке для промпта
    
    Args:
        detected_lang: Определенный язык ('ru', 'en', 'unknown')
        
    Returns:
        Инструкция для LLM
    """
    instructions = {
        'ru': "ВАЖНО: Отвечай на РУССКОМ ЯЗЫКЕ. Входной текст на русском - твой ответ тоже должен быть на русском.",
        'en': "IMPORTANT: Respond in ENGLISH. The input text is in English - your response must also be in English.",
        'unknown': "Respond in the same language as the input text."
    }
    
    return instructions.get(detected_lang, instructions['unknown'])


def get_language_name(lang_code: str) -> str:
    """Получить название языка"""
    names = {
        'ru': 'Русский',
        'en': 'English',
        'unknown': 'Unknown'
    }
    return names.get(lang_code, 'Unknown')


# Few-shot примеры для подкрепления
FEW_SHOT_EXAMPLES = {
    'ru': """
Пример 1:
Текст: "Проект начался в марте 2025 года с бюджетом $200K."
Summary: "Проект стартовал в марте 2025, бюджет составляет $200K."

Пример 2:
Текст: "Команда состоит из 5 инженеров: Алиса, Боб, Чарли, Дэвид и Ева."
Summary: "В команде 5 инженеров: Алиса (тимлид), Боб (backend), Чарли (frontend), Дэвид (DevOps), Ева (QA)."
""",
    'en': """
Example 1:
Text: "The project started in March 2025 with a $200K budget."
Summary: "Project launched March 2025, budget $200K."

Example 2:
Text: "The team consists of 5 engineers: Alice, Bob, Charlie, David, and Eva."
Summary: "Team of 5: Alice (lead), Bob (backend), Charlie (frontend), David (DevOps), Eva (QA)."
"""
}


def build_language_aware_prompt(
    text: str, 
    instruction: str,
    include_examples: bool = False
) -> str:
    """
    Построить промпт с учетом языка
    
    Args:
        text: Текст для обработки
        instruction: Основная инструкция
        include_examples: Включить few-shot примеры
        
    Returns:
        Промпт с языковыми инструкциями
    """
    detected_lang = detect_language(text)
    lang_instruction = get_language_instruction(detected_lang)
    lang_name = get_language_name(detected_lang)
    
    prompt_parts = [lang_instruction, ""]
    
    if include_examples and detected_lang in FEW_SHOT_EXAMPLES:
        prompt_parts.append("Примеры качественных суммаризаций:" if detected_lang == 'ru' else "Examples of good summaries:")
        prompt_parts.append(FEW_SHOT_EXAMPLES[detected_lang])
    
    prompt_parts.append(instruction)
    prompt_parts.append(f"\nTEXT (Language detected: {lang_name}):")
    prompt_parts.append(text)
    prompt_parts.append("\nSUMMARY:")
    
    return "\n".join(prompt_parts)

