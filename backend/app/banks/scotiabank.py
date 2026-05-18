"""
AutoTeaser - Scotiabank Bank Statement Parser
Logic specific to Scotiabank bank statements.
"""


def parse(text: str, pages: list[str]) -> dict:
    """
    Parse a Scotiabank bank statement.
    
    Args:
        text: Full extracted text from the PDF
        pages: List of text per page
    
    Returns:
        dict with extracted financial data
    """
    # TODO: Implement Scotiabank-specific parsing logic
    raise NotImplementedError("Scotiabank parser not yet implemented")
