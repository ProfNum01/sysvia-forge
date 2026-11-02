# IMG product references v2

Four isolated, unbranded cube references for the local synthetic IMG catalog. These are AI-generated edits guided by the existing synthetic scene, not camera captures or inspection evidence. The generated faces and color shades may differ from source pixels, so they must not be used as ground truth or as proof of a SKU.

Each image shows one complete colored cube on a neutral background and contains no printed SKU. The earlier partial reference PNGs remain in the ignored `data/references/` directory. `scripts/install_img_references.py` copies these versioned images into that local directory, updates only the four IMG product reference paths and descriptions, and writes audit events. It is idempotent. Existing inspections and photo IDs are unchanged.

Generated with the built-in ImageGen tool from the existing local scene, one edit per color. Prompt pattern: isolate one full cube of the specified color, preserve its simple unbranded geometry and three visible faces, center it against a neutral gray background, remove other objects, and add no text, SKU, logos, or borders.
