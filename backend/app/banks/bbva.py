"""
AutoTeaser - BBVA Bank Statement Parser
Logic specific to BBVA (Bancomer) bank statements.
"""


def parse(text: str, pages: list[str]) -> dict:
    """
    Parse a BBVA bank statement.
    
    Args:
        text: Full extracted text from the PDF
        pages: List of text per page
    
    Returns:
        dict with extracted financial data
    """
    # TODO: Implement BBVA-specific parsing logic
    raise NotImplementedError("BBVA parser not yet implemented")
