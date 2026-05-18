"""
AutoTeaser - Inbursa Bank Statement Parser
Logic specific to Inbursa bank statements.
"""


def parse(text: str, pages: list[str]) -> dict:
    """
    Parse an Inbursa bank statement.
    
    Args:
        text: Full extracted text from the PDF
        pages: List of text per page
    
    Returns:
        dict with extracted financial data
    """
    # TODO: Implement Inbursa-specific parsing logic
    raise NotImplementedError("Inbursa parser not yet implemented")
