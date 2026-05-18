"""
AutoTeaser - Sabadell Bank Statement Parser
Logic specific to Banco Sabadell bank statements.
"""


def parse(text: str, pages: list[str]) -> dict:
    """
    Parse a Sabadell bank statement.
    
    Args:
        text: Full extracted text from the PDF
        pages: List of text per page
    
    Returns:
        dict with extracted financial data
    """
    # TODO: Implement Sabadell-specific parsing logic
    raise NotImplementedError("Sabadell parser not yet implemented")
