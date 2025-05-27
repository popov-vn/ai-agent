from typing import TypedDict, Annotated, List, Dict, Any, Union

class AgentContext:
    """Состояние"""
    person_info: str                    # Информация о человеке
    photos: List[Dict[str, bytes]]  # Сгенерированные подарки    
    