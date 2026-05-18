"""
AutoTeaser - Banorte Bank Statement Parser
Logic specific to Banorte bank statements.
"""


def parse(text: str, pages: list[str]) -> dict:
    """
    Parse a Banorte bank statement.
    
    Args:
        text: Full extracted text from the PDF
        pages: List of text per page
    
    Returns:
        dict with extracted financial data
    """
    # TODO: Implement Banorte-specific parsing logic
    raise NotImplementedError("Banorte parser not yet implemented")
