"""
AutoTeaser - Santander Bank Statement Parser
Logic specific to Santander bank statements.
"""


def parse(text: str, pages: list[str]) -> dict:
    """
    Parse a Santander bank statement.
    
    Args:
        text: Full extracted text from the PDF
        pages: List of text per page
    
    Returns:
        dict with extracted financial data
    """
    # TODO: Implement Santander-specific parsing logic
    raise NotImplementedError("Santander parser not yet implemented")
