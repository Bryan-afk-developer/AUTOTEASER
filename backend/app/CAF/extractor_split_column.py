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

    # Calculate all possible pairs and their y_diff
    possible_matches = []
    for c in concepts:
        for a in amounts:
            y_diff = abs(c["y_center"] - a["y_center"])
            # Relaxed cutoff: within 2.0x of the tallest box
            if y_diff < max(c["height"], a["height"]) * 2.0:
                possible_matches.append((y_diff, c, a))
                
    # Sort by smallest Y difference
    possible_matches.sort(key=lambda x: x[0])
    
    matched_concepts = set()
    matched_amounts = set()
    
    paired_rows = []
    
    # Greedily pick the BEST matches first
    for diff, c, a in possible_matches:
        c_id = id(c)
        a_id = id(a)
        if c_id not in matched_concepts and a_id not in matched_amounts:
            matched_concepts.add(c_id)
            matched_amounts.add(a_id)
            paired_rows.append({
                "concept": c,
                "amount": a,
                "y_center": (c["y_center"] + a["y_center"]) / 2
            })
            
    # Add unmatched concepts
    for c in concepts:
        if id(c) not in matched_concepts:
            paired_rows.append({
                "concept": c,
                "amount": None,
                "y_center": c["y_center"]
            })
            
    # Add unmatched amounts
    for a in amounts:
        if id(a) not in matched_amounts:
            paired_rows.append({
                "concept": None,
                "amount": a,
                "y_center": a["y_center"]
            })
            
    # Sort all rows top-to-bottom
    paired_rows.sort(key=lambda r: r["y_center"])
    
    final_rows = []
    for r in paired_rows:
        row_out = []
        if r["concept"]:
            row_out.append({"text": r["concept"]["text"], "bbox": r["concept"]["bbox"], "is_concept": True})
        if r["amount"]:
            row_out.append({"text": r["amount"]["text"], "bbox": r["amount"]["bbox"], "is_amount": True})
        final_rows.append(row_out)

    return final_rows
