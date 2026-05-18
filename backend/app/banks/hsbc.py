"""
AutoTeaser - HSBC Bank Statement Parser
Logic specific to HSBC bank statements.
"""


def parse(text: str, pages: list[str]) -> dict:
    """
    Parse an HSBC bank statement.
    
    Args:
        text: Full extracted text from the PDF
        pages: List of text per page
    
    Returns:
        dict with extracted financial data
    """
    # TODO: Implement HSBC-specific parsing logic
    raise NotImplementedError("HSBC parser not yet implemented")
