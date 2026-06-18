def extract_pairs_split_column(all_tokens, r_concept, r_amount, page_width, page_height):
    """
    Extracts explicit concept and amount pairs based on two explicit regions.
    Instead of relying on horizontal reading, this physically maps tokens from r_concept to r_amount.
    """
    def is_inside(token_bbox, region):
        cx = (token_bbox[0] + token_bbox[2]) / 2 / page_width
        cy = (token_bbox[1] + token_bbox[3]) / 2 / page_height
        return (region["x"] <= cx <= region["x"] + region["w"]) and (region["y"] <= cy <= region["y"] + region["h"])

    concept_tokens = [t for t in all_tokens if is_inside(t["bbox"], r_concept)]
    amount_tokens = [t for t in all_tokens if is_inside(t["bbox"], r_amount)]

    def group_into_lines(tokens):
        if not tokens: return []
        tokens.sort(key=lambda t: t['bbox'][1])
        lines = []
        current_line = []
        for t in tokens:
            if not current_line:
                current_line.append(t)
            else:
                y0_curr = min(c['bbox'][1] for c in current_line)
                y1_curr = max(c['bbox'][3] for c in current_line)
                y0_item = t['bbox'][1]
                y1_item = t['bbox'][3]
                
                overlap = max(0, min(y1_curr, y1_item) - max(y0_curr, y0_item))
                h_item = y1_item - y0_item
                h_curr = y1_curr - y0_curr
                
                if overlap > 0 and overlap > min(h_item, h_curr) * 0.3:
                    current_line.append(t)
                else:
                    current_line.sort(key=lambda c: c['bbox'][0])
                    lines.append(current_line)
                    current_line = [t]
        if current_line:
            current_line.sort(key=lambda c: c['bbox'][0])
            lines.append(current_line)
        return lines

    concept_lines = group_into_lines(concept_tokens)
    amount_lines = group_into_lines(amount_tokens)

    # Convert lines to text + combined bbox
    def line_to_dict(line_tokens):
        text = " ".join([t["text"] for t in line_tokens]).strip()
        x0 = min(t["bbox"][0] for t in line_tokens)
        y0 = min(t["bbox"][1] for t in line_tokens)
        x1 = max(t["bbox"][2] for t in line_tokens)
        y1 = max(t["bbox"][3] for t in line_tokens)
        return {"text": text, "bbox": [x0, y0, x1, y1], "y_center": (y0 + y1) / 2, "height": y1 - y0}

    concepts = [line_to_dict(line) for line in concept_lines]
    amounts = [line_to_dict(line) for line in amount_lines]

    paired_rows = []
    
    # Match amounts to concepts by Y coordinate
    # For every concept, find an amount that falls within its Y range (or close enough)
    for c in concepts:
        matched_amount = None
        best_diff = float('inf')
        
        for a in amounts:
            y_diff = abs(c["y_center"] - a["y_center"])
            # If the amount's center is within half the concept's height, it's a solid match
            if y_diff < max(c["height"], a["height"]) * 0.8:
                if y_diff < best_diff:
                    best_diff = y_diff
                    matched_amount = a
                    
        if matched_amount:
            amounts.remove(matched_amount)
            # Make a single 'row' list with both items for the evidence cropper
            paired_rows.append([
                {"text": c["text"], "bbox": c["bbox"], "is_concept": True},
                {"text": matched_amount["text"], "bbox": matched_amount["bbox"], "is_amount": True}
            ])
        else:
            paired_rows.append([
                {"text": c["text"], "bbox": c["bbox"], "is_concept": True}
            ])

    # Any leftover amounts that didn't match a concept
    for a in amounts:
        paired_rows.append([
            {"text": a["text"], "bbox": a["bbox"], "is_amount": True}
        ])

    return paired_rows
