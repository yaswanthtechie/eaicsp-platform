"""
Text preprocessing module for the Supplier Risk NLP pipeline.
"""
import string

def clean_text(text: str) -> str:
    """
    Clean the input text by converting to lowercase, removing punctuation, 
    and removing extra whitespace.
    
    Args:
        text (str): The raw input text.
        
    Returns:
        str: The cleaned text.
    """
    if not isinstance(text, str):
        return ""
    
    # Convert to lowercase
    text = text.lower()
    
    # Remove punctuation
    translator = str.maketrans('', '', string.punctuation)
    text = text.translate(translator)
    
    # Remove extra whitespace
    text = " ".join(text.split())
    
    return text
